"""Loopback-only development gateway. Never use this identity switch in production."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import httpx
from dev_config import ROOT, SERVICES


parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8080)
parser.add_argument("--base-port", type=int, default=8101)
args = parser.parse_args()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT / "web/dist"), **kw)

    def do_GET(self):
        if self.path == "/auth/config":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b'{"mode":"demo"}')
            return
        if self.path.startswith("/api/"):
            return self.proxy()
        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        self.proxy()

    def do_PATCH(self):
        self.proxy()

    def proxy(self):
        parts = self.path.split("/", 3)
        if len(parts) != 4 or parts[2] not in SERVICES:
            return self.send_error(404)
        # Reject cross-origin browser writes even in this synthetic demo.
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://127.0.0.1:{args.port}", f"http://localhost:{args.port}"):
            return self.send_error(403)
        role = self.headers.get("X-Demo-Role", "operator")
        if role not in ("operator", "approver", "admin"):
            return self.send_error(403)
        size = int(self.headers.get("Content-Length", "0"))
        if size > 1024 * 1024:
            return self.send_error(413)
        try:
            response = httpx.request(self.command,
                f"http://127.0.0.1:{args.base_port + SERVICES.index(parts[2])}/api/v1/{parts[3]}",
                content=self.rfile.read(size) if size else None,
                headers={"Authorization": "Bearer demo-" + role + "-token", "Content-Type": "application/json"}, timeout=15)
            self.send_response(response.status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(response.content)
        except httpx.HTTPError:
            self.send_error(503, "Module temporarily unavailable")


ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
