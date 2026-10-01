#!/usr/bin/env python3
"""Exercise the web image against synthetic TLS upstreams inside an offline container."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[2]


def docker(*args, check=True):
    return subprocess.run(["docker", *args], check=check, capture_output=True, text=True, timeout=90)


def main():
    name = "unum-web-smoke-" + uuid.uuid4().hex[:10]
    with tempfile.TemporaryDirectory(prefix="unum-web-smoke-") as folder:
        path = Path(folder)
        path.chmod(0o755)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "fixture.local")])
        now = datetime.now(timezone.utc)
        certificate = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("fixture.local")]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(key, hashes.SHA256()))
        (path / "ca.crt").write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        (path / "test.key").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        runtime = json.loads((ROOT / "deploy/web/runtime.example.json").read_text())
        runtime["services"] = {name: "https://fixture.local:8443" for name in runtime["services"]}
        # A valid CA with the wrong host must still fail TLS verification.
        runtime["services"]["placement"] = "https://127.0.0.1:8443"
        runtime["upstream_ca_file"] = "/fixtures/ca.crt"
        (path / "runtime.json").write_text(json.dumps(runtime))
        (path / "upstream.py").write_text('''
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, ssl
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.reply()
    def do_POST(self):
        self.reply()
    def reply(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        response = json.dumps({"path": self.path, "method": self.command,
            "authorization": self.headers.get("Authorization"),
            "delegation": self.headers.get("X-Unum-Caller-Authorization"),
            "demo_role": self.headers.get("X-Demo-Role"), "cookie": self.headers.get("Cookie"),
            "body": body.decode()}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Set-Cookie", "upstream-cookie=must-not-leak")
        self.end_headers(); self.wfile.write(response)
    def log_message(self, *args):
        pass
server = ThreadingHTTPServer(("127.0.0.1", 8443), Handler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain("/fixtures/ca.crt", "/fixtures/test.key")
server.socket = context.wrap_socket(server.socket, server_side=True)
server.serve_forever()
''')
        try:
            docker("run", "--detach", "--name", name, "--read-only", "--network", "none",
                   "--add-host", "fixture.local:127.0.0.1",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                   "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                   "--mount", f"type=bind,source={folder},target=/fixtures,readonly",
                   "--mount", f"type=bind,source={path / 'runtime.json'},target=/etc/unum-web/runtime.json,readonly",
                   "unum-web:qualification")
            docker("exec", "--detach", name, "python3", "/fixtures/upstream.py")
            probe = "import ssl,urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=1); urllib.request.urlopen('https://fixture.local:8443/ready',context=ssl.create_default_context(cafile='/fixtures/ca.crt'),timeout=1)"
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if docker("exec", name, "python3", "-c", probe, check=False).returncode == 0:
                    break
                time.sleep(.1)
            else:
                raise RuntimeError("Gateway startup failed")
            verify = '''
import json, os
from urllib.request import Request, urlopen
from urllib.error import HTTPError
assert os.getuid() != 0
def get(path, **kwargs):
    return urlopen(Request("http://127.0.0.1:8080" + path,
        headers={"Host": "dcim.example.invalid", **kwargs.pop("headers", {})}, **kwargs), timeout=5)
config = json.load(get("/auth/config"))
assert config["mode"] == "oidc" and "services" not in config
with get("/auth/callback?code=synthetic-sensitive-code&state=test") as callback:
    assert callback.status == 200 and b"<html" in callback.read()
    assert "no-store" in callback.headers["Cache-Control"]
    assert callback.headers["X-Frame-Options"] == "DENY"
with get("/api/inventory/identity?check=1", data=b'{"test":true}', method="POST", headers={
    "Authorization": "Bearer synthetic-browser-token", "Cookie": "browser=private",
    "X-Demo-Role": "admin", "X-Unum-Caller-Authorization": "Bearer forged-delegation"}) as response:
    result = json.load(response)
    assert result == {"path": "/api/v1/identity?check=1", "method": "POST",
        "authorization": "Bearer synthetic-browser-token", "delegation": None,
        "demo_role": None, "cookie": None, "body": '{"test":true}'}, result
    assert "Set-Cookie" not in response.headers
for path, status in (("/api/placement/scene", 502), ("/api/unknown/identity", 404)):
    try:
        get(path); raise AssertionError("Unexpected success: " + path)
    except HTTPError as exc:
        assert exc.code == status, (path, exc.code)
try:
    get("/", headers={"Host":"untrusted.example.invalid"})
    raise AssertionError("Untrusted host accepted")
except HTTPError as exc:
    assert exc.code == 421
print("Web gateway smoke passed: config, callback, bearer forwarding, header isolation, TLS hostname, host policy")
'''
            print(docker("exec", name, "python3", "-c", verify).stdout.strip())
            logs = docker("logs", name).stdout
            assert "synthetic-sensitive-code" not in logs
            assert "synthetic-browser-token" not in logs
        except Exception:
            result = docker("logs", name, check=False)
            print(result.stdout)
            print(result.stderr)
            raise
        finally:
            result = docker("rm", "--force", name, check=False)
            if result.returncode and "No such container" not in result.stderr:
                raise RuntimeError("Web smoke cleanup failed: " + name)


if __name__ == "__main__":
    main()
