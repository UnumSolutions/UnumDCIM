#!/usr/bin/env python3
"""Run real PostgreSQL and JetStream tests in disposable Docker containers."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
IMAGES = {"postgres": "postgres:17", "nats": "nats:2.11-alpine"}


def docker(*args, **kwargs):
    return subprocess.run(["docker", *args], check=True, text=True, capture_output=True, **kwargs).stdout.strip()


def main():
    name = "unum-qualification-" + uuid.uuid4().hex[:10]
    containers = []
    evidence = {"images": {}, "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    result = 1
    try:
        password = secrets.token_urlsafe(32)
        for kind, image in IMAGES.items():
            print(f"Preparing {kind} ({image})", flush=True)
            docker("pull", image)
            evidence["images"][kind] = json.loads(docker("image", "inspect", image))[0]["RepoDigests"]
        postgres_name = name + "-postgres"
        containers.append(postgres_name)
        postgres = docker("run", "--detach", "--name", postgres_name,
            "--publish", "127.0.0.1::5432", "--env", "POSTGRES_PASSWORD", IMAGES["postgres"],
            env=os.environ | {"POSTGRES_PASSWORD": password})
        # Docker may reassign an automatically allocated host port on restart.
        # Choose a free port explicitly so broker recovery uses a stable address.
        with socket.socket() as port_holder:
            port_holder.bind(("127.0.0.1", 0))
            nats_host_port = port_holder.getsockname()[1]
        nats_name = name + "-nats"
        containers.append(nats_name)
        nats = docker("run", "--detach", "--name", nats_name,
            "--publish", f"127.0.0.1:{nats_host_port}:4222", IMAGES["nats"], "-js", "-sd", "/data")
        pgport = docker("port", postgres, "5432/tcp").rsplit(":", 1)[1]
        natsport = docker("port", nats, "4222/tcp").rsplit(":", 1)[1]
        for _ in range(60):
            ready = subprocess.run(["docker", "exec", postgres, "pg_isready", "-U", "postgres"], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("PostgreSQL failed readiness")
        env = os.environ | {
            "UNUM_TEST_PG_DSN": f"host=127.0.0.1 port={pgport} dbname=postgres user=postgres password={password} sslmode=disable",
            "UNUM_TEST_NATS_URL": f"nats://127.0.0.1:{natsport}",
            "UNUM_TEST_NATS_CONTAINER": nats,
        }
        print("Running qualification with restricted application roles and separate module databases", flush=True)
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", *sys.argv[1:]], cwd=ROOT, env=env).returncode
        evidence["exit_code"] = result
    finally:
        cleanup_failures = []
        for container in reversed(containers):
            try:
                removal = subprocess.run(["docker", "rm", "--force", "--volumes", container],
                                         capture_output=True, text=True, timeout=30)
                if removal.returncode and "No such container" not in removal.stderr:
                    cleanup_failures.append(container)
            except (OSError, subprocess.TimeoutExpired):
                cleanup_failures.append(container)
        if cleanup_failures:
            result = result or 1
            evidence["cleanup_failed"] = cleanup_failures
            print("Qualification container cleanup failed; inspect names in the evidence file", file=sys.stderr)
        evidence["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        evidence["exit_code"] = result
        evidence["test_arguments"] = sys.argv[1:]
        path = ROOT / ".data" / "qualification" / "latest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence, indent=2) + "\n")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
