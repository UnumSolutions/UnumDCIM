#!/usr/bin/env python3
"""Local synthetic demo. No production exposure and no Nlyte connection."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from dev_config import ROOT, SERVICES, environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--base-port", type=int, default=8101)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".data",
                        help="Local synthetic data directory (use a temporary directory for smoke tests)")
    args = parser.parse_args()
    children = []
    logs = args.data_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    def stop(*_):
        for p in children:
            p.terminate()
        for p in children:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        for i, service in enumerate(SERVICES):
            env = environment(service, args.data_dir, base_port=args.base_port)
            subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
            subprocess.run([sys.executable, "manage.py", "seed_demo"], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
            log = open(logs / (service + ".log"), "a")
            children.append(subprocess.Popen([sys.executable, "manage.py", "runserver", f"127.0.0.1:{args.base_port+i}", "--noreload"], cwd=ROOT, env=env, stdout=log, stderr=log))
            log.close()
        children.append(subprocess.Popen([sys.executable, "scripts/dev_gateway.py", "--port", str(args.port), "--base-port", str(args.base_port)], cwd=ROOT))
        print(f"UnumDCIM synthetic demo: http://127.0.0.1:{args.port} (Ctrl+C stops all services)", flush=True)
        while all(p.poll() is None for p in children):
            time.sleep(1)
    finally:
        stop()


if __name__ == "__main__":
    main()
