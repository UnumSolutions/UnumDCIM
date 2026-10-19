"""Smoke local module images with disposable synthetic data and no network access.

Build each unum-<module>:qualification image first. This does not qualify a
PostgreSQL deployment, Kubernetes, failover, or Nlyte connectivity.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid

MODULES = {"inventory": "assets", "placement": "scene", "workflow": "changes",
           "synchronization": "status", "registry": "modules"}
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_LIMIT = 16_384


def docker(*args, check=True):
    return subprocess.run(["docker", *args], cwd=ROOT, check=check,
                          capture_output=True, text=True, timeout=90)


def output(value):
    """Keep evidence bounded, including bytes returned by TimeoutExpired."""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = value or ""
    return value if len(value) <= OUTPUT_LIMIT else "[truncated]\n" + value[-OUTPUT_LIMIT:]


def failure(exc):
    # Do not serialize command arguments: docker run includes environment values.
    evidence = {"type": type(exc).__name__}
    if isinstance(exc, subprocess.CalledProcessError):
        evidence.update(error="Docker command failed", returncode=exc.returncode)
    elif isinstance(exc, subprocess.TimeoutExpired):
        evidence.update(error="Docker command timed out", timeout_seconds=exc.timeout)
    else:
        evidence["error"] = str(exc)
    if isinstance(exc, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
        evidence.update(stdout=output(exc.stdout), stderr=output(exc.stderr))
    return evidence


def smoke(module, tag):
    started = time.monotonic()
    name = "unum-image-smoke-" + module + "-" + uuid.uuid4().hex[:12]
    evidence = {"module": module, "image": "unum-" + module + ":" + tag,
                "container": name, "status": "failed"}
    identity = {"image-smoke-token": {"actor": "image-smoke", "role": "viewer",
                "tenant": "demo", "sites": ["ashburn", "dallas"]}}
    phase = "start"
    try:
        # The name exists before the command starts so cleanup is also attempted
        # when Docker starts the container but its response is lost or times out.
        # Keep an exited container until logs are collected; finally removes it.
        docker("run", "-d", "--name", name, "--read-only", "--network", "none",
                 "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                 "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                 "-e", "UNUM_DEMO=1", "-e", "UNUM_DATA_DIR=/tmp/unum",
                 "-e", "UNUM_AUTH_TOKENS=" + json.dumps(identity),
                 evidence["image"], "sh", "-c",
                 "python manage.py migrate --noinput && python manage.py seed_demo && "
                 "exec gunicorn platform_core.wsgi:application --bind 127.0.0.1:8000 "
                 "--workers 2 --timeout 30 --access-logfile -")
        phase = "readiness"
        probe = "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=1).read()"
        deadline = time.monotonic() + 30
        last_probe = None
        while time.monotonic() < deadline:
            last_probe = docker("exec", name, "python", "-c", probe, check=False)
            if last_probe.returncode == 0:
                break
            time.sleep(.2)
        else:
            if last_probe is not None:
                evidence["last_probe"] = {"returncode": last_probe.returncode,
                                          "stdout": output(last_probe.stdout),
                                          "stderr": output(last_probe.stderr)}
            raise RuntimeError(module + " did not become ready within 30 seconds")
        phase = "verification"
        verify = f'''
import json, os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
assert os.getuid() == 10001
assert [p.name for p in Path('/app/services').iterdir() if p.is_dir() and p.name != '__pycache__'] == [{module!r}]
health = json.load(urlopen('http://127.0.0.1:8000/health'))
assert health['service'] == {module!r} and health['demo'] is True
url = 'http://127.0.0.1:8000/api/v1/' + {MODULES[module]!r}
try:
    urlopen(url)
    raise AssertionError('Unauthenticated domain access was allowed')
except HTTPError as exc:
    assert exc.code == 401
response = urlopen(Request(url, headers={{'Authorization': 'Bearer image-smoke-token'}}))
assert response.status == 200
print(json.dumps({{'module': {module!r}, 'health': 'ok', 'ready': 'ok', 'auth': 'ok', 'domain_isolation': 'ok', 'uid': os.getuid()}}))
'''
        evidence["checks"] = json.loads(docker("exec", name, "python", "-c", verify).stdout)
        evidence["status"] = "passed"
    except Exception as exc:
        evidence["failure"] = {"phase": phase, **failure(exc)}
        try:
            logs = docker("logs", "--tail", "100", name, check=False)
            evidence["logs"] = {"returncode": logs.returncode,
                                "stdout": output(logs.stdout), "stderr": output(logs.stderr)}
        except Exception as log_error:
            evidence["log_failure"] = failure(log_error)
    finally:
        try:
            removal = docker("rm", "-f", name, check=False)
            # A rejected docker run may never have created a container.
            if removal.returncode and "No such container:" not in removal.stderr:
                raise subprocess.CalledProcessError(removal.returncode, removal.args,
                                                    removal.stdout, removal.stderr)
        except Exception as cleanup_error:
            evidence["cleanup_failure"] = failure(cleanup_error)
            evidence["status"] = "failed"
        evidence["duration_seconds"] = round(time.monotonic() - started, 3)
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="qualification")
    parser.add_argument("--report", type=Path,
                        default=ROOT / ".data" / "qualification" / "image-smoke.json")
    args = parser.parse_args(argv)
    report = {"status": "running", "modules": [],
              "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    args.report.parent.mkdir(parents=True, exist_ok=True)

    def save_report():
        temporary = args.report.with_name(args.report.name + ".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(args.report)

    save_report()
    for module in MODULES:
        evidence = smoke(module, args.tag)
        report["modules"].append(evidence)
        save_report()
        print(json.dumps(evidence), flush=True)
    report["status"] = "passed" if all(m["status"] == "passed" for m in report["modules"]) else "failed"
    report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report["exit_code"] = 0 if report["status"] == "passed" else 1
    save_report()
    print("Image smoke evidence: " + str(args.report), flush=True)
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
