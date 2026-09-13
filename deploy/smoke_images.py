"""Smoke local module images with disposable synthetic data and no network access.

Build each unum-<module>:qualification image first. This does not qualify a
PostgreSQL deployment, Kubernetes, failover, or Nlyte connectivity.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

MODULES = {"inventory": "assets", "placement": "scene", "workflow": "changes",
           "synchronization": "status", "registry": "modules"}
ROOT = Path(__file__).resolve().parents[1]


def docker(*args, check=True):
    return subprocess.run(["docker", *args], cwd=ROOT, check=check,
                          capture_output=True, text=True, timeout=90)


def smoke(module, tag):
    identity = {"image-smoke-token": {"actor": "image-smoke", "role": "viewer",
                "tenant": "demo", "sites": ["ashburn", "dallas"]}}
    cid = docker("run", "--rm", "-d", "--read-only", "--network", "none",
                 "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                 "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                 "-e", "UNUM_DEMO=1", "-e", "UNUM_DATA_DIR=/tmp/unum",
                 "-e", "UNUM_AUTH_TOKENS=" + json.dumps(identity),
                 "unum-" + module + ":" + tag, "sh", "-c",
                 "python manage.py migrate --noinput && python manage.py seed_demo && "
                 "exec gunicorn platform_core.wsgi:application --bind 127.0.0.1:8000 "
                 "--workers 2 --timeout 30 --access-logfile -").stdout.strip()
    try:
        probe = "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=1).read()"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if docker("exec", cid, "python", "-c", probe, check=False).returncode == 0:
                break
            time.sleep(.2)
        else:
            raise RuntimeError(module + " did not become ready\n" + docker("logs", cid, check=False).stdout)
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
        print(docker("exec", cid, "python", "-c", verify).stdout.strip(), flush=True)
    finally:
        docker("rm", "-f", cid, check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="qualification")
    args = parser.parse_args()
    for module in MODULES:
        smoke(module, args.tag)
