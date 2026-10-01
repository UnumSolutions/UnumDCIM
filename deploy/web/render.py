#!/usr/bin/env python3
"""Render the production web gateway from public OIDC settings and private routes."""
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

MODULES = {"inventory", "placement", "workflow", "synchronization", "registry"}
ACR = "urn:unum:acr:staff-mfa"


def https_url(value):
    if not isinstance(value, str) or not re.fullmatch(r"https://[A-Za-z0-9.\-_:~/\[\]%]+", value):
        raise ValueError("An explicit HTTPS URL without credentials, query, or fragment is required")
    parsed = urlsplit(value)
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid HTTPS host")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid HTTPS port")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", parsed.hostname):
            raise ValueError("Invalid HTTPS host")
    return parsed


def render(data):
    if not isinstance(data, dict) or set(data) - {"auth", "services", "upstream_ca_file"} or not {"auth", "services"} <= set(data):
        raise ValueError("Expected auth and services configuration")
    auth = data["auth"]
    fields = {"mode", "issuer", "client_id", "redirect_uri", "post_logout_redirect_uri", "scope", "acr_values", "google_provider"}
    if not isinstance(auth, dict) or set(auth) != fields or auth["mode"] != "oidc":
        raise ValueError("The production gateway requires explicit OIDC configuration")
    issuer, callback, logout = (https_url(auth[key]) for key in ("issuer", "redirect_uri", "post_logout_redirect_uri"))
    if callback.netloc != logout.netloc or callback.path != "/auth/callback" or logout.path != "/":
        raise ValueError("Use same-origin /auth/callback and / logout URLs")
    if auth["client_id"] != "unum-web":
        raise ValueError("Use the configured unum-web public client")
    if auth["scope"] != "openid profile email unum.api" or auth["acr_values"] != ACR or auth["google_provider"] != "google":
        raise ValueError("Use the staff MFA, API scope, and Google broker configuration")
    services = data["services"]
    if not isinstance(services, dict) or set(services) != MODULES:
        raise ValueError("Provide one HTTPS origin for each application module")
    routes = {}
    for module, value in services.items():
        parsed = https_url(value)
        if parsed.path not in ("", "/"):
            raise ValueError("Service routes must be HTTPS origins without a path")
        routes[module] = f"https://{parsed.netloc}"
    ca = data.get("upstream_ca_file", "/etc/ssl/certs/ca-certificates.crt")
    if not isinstance(ca, str) or not re.fullmatch(r"/[A-Za-z0-9._/-]+", ca) or ".." in ca.split("/"):
        raise ValueError("Invalid upstream CA file path")
    broker_origin = f"https://{issuer.netloc}"
    locations = "\n".join(f"""
        location /api/{module}/ {{
            limit_except GET POST PATCH {{ deny all; }}
            proxy_pass {origin}/api/v1/;
            proxy_set_header Authorization $http_authorization;
            proxy_set_header X-Unum-Caller-Authorization "";
            proxy_set_header X-Demo-Role "";
            proxy_set_header Cookie "";
            proxy_hide_header Set-Cookie;
        }}""" for module, origin in sorted(routes.items()))
    configuration = f"""worker_processes auto;
pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events {{ worker_connections 1024; }}
http {{
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    log_format private '$remote_addr $request_method $uri $status';
    access_log /dev/stdout private;
    client_body_temp_path /tmp/client_temp;
    proxy_temp_path /tmp/proxy_temp;
    fastcgi_temp_path /tmp/fastcgi_temp;
    uwsgi_temp_path /tmp/uwsgi_temp;
    scgi_temp_path /tmp/scgi_temp;
    client_max_body_size 1m;
    proxy_connect_timeout 3s;
    proxy_read_timeout 15s;
    proxy_send_timeout 15s;
    proxy_next_upstream off;
    proxy_ssl_verify on;
    proxy_ssl_server_name on;
    proxy_ssl_trusted_certificate {ca};
    server {{
        listen 8080 default_server;
        server_name _;
        location = /health {{ default_type application/json; return 200 '{{"status":"ok"}}'; }}
        location / {{ return 421; }}
    }}
    server {{
        listen 8080;
        server_name {callback.hostname};
        root /usr/share/nginx/html;
        add_header Cache-Control "no-store" always;
        add_header X-Content-Type-Options nosniff always;
        add_header Referrer-Policy no-referrer always;
        add_header X-Frame-Options DENY always;
        add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' {broker_origin}; img-src 'self' data: blob:; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self' {broker_origin}" always;
        location = /health {{ default_type application/json; return 200 '{{"status":"ok"}}'; }}
        location = /auth/config {{
            default_type application/json;
            alias /tmp/unum-web/auth.json;
        }}
        {locations}
        location /api/ {{ return 404; }}
        location /assets/ {{ try_files $uri =404; }}
        location / {{ try_files $uri /index.html; }}
    }}
}}
"""
    return configuration, dict(auth)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: render.py /path/to/runtime.json")
    try:
        path = Path(sys.argv[1])
        if path.stat().st_size > 32_768:
            raise ValueError("Configuration is too large")
        configuration, public = render(json.loads(path.read_text()))
        output = Path("/tmp/unum-web")
        output.mkdir(mode=0o700, exist_ok=True)
        (output / "nginx.conf").write_text(configuration)
        (output / "auth.json").write_text(json.dumps(public))
    except (OSError, ValueError, TypeError, KeyError):
        raise SystemExit("Invalid or unavailable production web configuration")


if __name__ == "__main__":
    main()
