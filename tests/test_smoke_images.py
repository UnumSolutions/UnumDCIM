import json
import subprocess

import pytest

from deploy import smoke_images


@pytest.fixture
def docker(monkeypatch):
    commands = []
    responses = {
        "run": (0, "container-id\n", ""),
        "probe": (0, "", ""),
        "verify": (0, json.dumps({"module": "inventory", "health": "ok", "ready": "ok",
                                  "auth": "ok", "domain_isolation": "ok", "uid": 10001}), ""),
        "logs": (0, "startup output", "application error"),
        "rm": (0, "container-id\n", ""),
    }

    def run(args, **kwargs):
        commands.append(args)
        assert kwargs["capture_output"] and kwargs["text"]
        assert kwargs["timeout"] == 90
        action = args[1]
        if action == "exec":
            action = "verify" if "print(json.dumps" in args[-1] else "probe"
        response = responses[action]
        if isinstance(response, Exception):
            raise response
        returncode, stdout, stderr = response
        if kwargs["check"] and returncode:
            raise subprocess.CalledProcessError(returncode, args, stdout, stderr)
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)

    monkeypatch.setattr(smoke_images.subprocess, "run", run)
    return commands, responses


def test_success_keeps_isolation_checks_and_cleans_named_container(docker):
    commands, _ = docker
    result = smoke_images.smoke("inventory", "qualification")
    assert result["status"] == "passed"
    assert result["checks"]["auth"] == result["checks"]["domain_isolation"] == "ok"
    assert result["checks"]["uid"] == 10001
    start = commands[0]
    assert "--rm" not in start and "--read-only" in start
    for option, value in (("--network", "none"), ("--cap-drop", "ALL"),
                          ("--security-opt", "no-new-privileges"),
                          ("--tmpfs", "/tmp:rw,noexec,nosuid,size=64m")):
        assert start[start.index(option) + 1] == value
    name = start[start.index("--name") + 1]
    assert name == result["container"] and name.startswith("unum-image-smoke-inventory-")
    assert commands[-1] == ["docker", "rm", "-f", name]
    assert all(command[1] != "logs" for command in commands)


def test_verification_failure_keeps_original_error_and_logs_before_cleanup(docker):
    commands, responses = docker
    responses["verify"] = (1, "verification output", "assertion failed")
    responses["rm"] = (1, "", "daemon unavailable during cleanup")
    result = smoke_images.smoke("inventory", "qualification")
    assert result["status"] == "failed"
    assert result["failure"] == {"phase": "verification", "type": "CalledProcessError",
                                 "error": "Docker command failed", "returncode": 1,
                                 "stdout": "verification output", "stderr": "assertion failed"}
    assert result["logs"]["stdout"] == "startup output"
    assert result["logs"]["stderr"] == "application error"
    assert result["cleanup_failure"]["stderr"] == "daemon unavailable during cleanup"
    assert [command[1] for command in commands][-2:] == ["logs", "rm"]


def test_lost_start_response_still_cleans_by_name_and_omits_command_arguments(docker):
    commands, responses = docker
    responses["run"] = subprocess.TimeoutExpired(
        ["docker", "run", "--env", "do-not-record-environment"], 90,
        output=b"daemon accepted container", stderr=b"response lost")
    result = smoke_images.smoke("inventory", "qualification")
    assert result["failure"]["phase"] == "start"
    assert result["failure"]["stdout"] == "daemon accepted container"
    assert result["failure"]["stderr"] == "response lost"
    assert "do-not-record-environment" not in json.dumps(result)
    assert commands[-1] == ["docker", "rm", "-f", result["container"]]


def test_failure_output_is_bounded_and_preserves_its_tail():
    error = subprocess.TimeoutExpired(["docker", "exec"], 90,
                                      output=b"x" * 50_000 + b"last output", stderr=b"\xff")
    result = smoke_images.failure(error)
    assert result["stdout"].startswith("[truncated]\n")
    assert result["stdout"].endswith("last output")
    assert len(result["stdout"]) == len("[truncated]\n") + smoke_images.OUTPUT_LIMIT
    assert result["stderr"] == "\ufffd"


def test_readiness_timeout_records_last_probe(docker, monkeypatch):
    _, responses = docker
    responses["probe"] = (1, "probe output", "connection refused")
    clock = iter([0, 0, 0, 31, 32])
    monkeypatch.setattr(smoke_images.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(smoke_images.time, "sleep", lambda _: None)
    result = smoke_images.smoke("inventory", "qualification")
    assert result["failure"]["phase"] == "readiness"
    assert result["last_probe"] == {"returncode": 1, "stdout": "probe output",
                                    "stderr": "connection refused"}


def test_log_collection_failure_does_not_mask_start_error_or_skip_cleanup(docker):
    commands, responses = docker
    responses["run"] = (125, "", "image unavailable")
    responses["logs"] = subprocess.TimeoutExpired(["docker", "logs"], 90)
    responses["rm"] = (1, "", "Error response from daemon: No such container: test")
    result = smoke_images.smoke("inventory", "qualification")
    assert result["failure"]["stderr"] == "image unavailable"
    assert result["log_failure"]["type"] == "TimeoutExpired"
    assert "cleanup_failure" not in result
    assert commands[-1][1] == "rm"


@pytest.mark.parametrize("cleanup", [(1, "", "cannot remove container"),
                                     subprocess.TimeoutExpired(["docker", "rm"], 90)])
def test_cleanup_failure_fails_otherwise_successful_smoke(docker, cleanup):
    _, responses = docker
    responses["rm"] = cleanup
    result = smoke_images.smoke("inventory", "qualification")
    assert result["checks"]["health"] == "ok"
    assert result["status"] == "failed"
    assert "cleanup_failure" in result and "failure" not in result


@pytest.mark.parametrize("failed_module", [None, "placement"])
def test_main_reports_every_module_and_returns_failure(monkeypatch, tmp_path, failed_module):
    path = tmp_path / "evidence" / "smoke.json"
    attempted = []

    def smoke(module, tag):
        # Evidence is saved before work and after each completed module.
        partial = json.loads(path.read_text())
        assert partial["status"] == "running"
        assert len(partial["modules"]) == len(attempted)
        assert tag == "test-tag"
        attempted.append(module)
        return {"module": module, "status": "failed" if module == failed_module else "passed"}

    monkeypatch.setattr(smoke_images, "smoke", smoke)
    result = smoke_images.main(["--tag", "test-tag", "--report", str(path)])
    report = json.loads(path.read_text())
    assert attempted == list(smoke_images.MODULES)
    assert result == report["exit_code"] == (1 if failed_module else 0)
    assert report["status"] == ("failed" if failed_module else "passed")
    assert report["started_at"] and report["finished_at"]
    assert not path.with_suffix(".json.tmp").exists()
