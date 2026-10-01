# Production browser gateway

This image serves the built UI and proxies its same-origin API requests to the
five modules over verified TLS. It uses the
[unprivileged NGINX image](https://github.com/nginx/docker-nginx-unprivileged).
Google Workspace authentication is provided through the broker described in
[the identity guide](../../docs/google-workspace.md). No machine credential is
stored in the browser or substituted by this gateway.

Copy `runtime.example.json` outside the repository and supply the broker issuer,
registered browser callback/logout URLs, and the five service HTTPS origins.
The browser receives only the `auth` section from `/auth/config`; internal
service routes stay on the server. This configuration contains public OIDC
settings, not a Google client secret. Missing, demo, or invalid production
configuration stops the container rather than enabling demo identities.

```sh
docker build -f deploy/web/Dockerfile -t unum-web:qualification .
.venv/bin/python deploy/web/smoke.py
```

Run the resulting image behind an HTTPS ingress using a read-only root,
capabilities dropped, UID 101, a writable `/tmp` tmpfs, and the configuration
mounted read-only at `/etc/unum-web/runtime.json`. The process listens on port
8080; publish it only on a private network behind the ingress. Preserve the
configured application Host header. `/health` is available for internal probes;
other requests with an unknown Host receive 421. Use a signed immutable image
digest for an actual deployment.

All service routes must use HTTPS. For a private CA, mount its public certificate
bundle and set `upstream_ca_file` to its absolute container path. Hostname and
certificate verification stay enabled. DNS names are resolved when NGINX starts;
restart the gateway after changing service addresses. Do not mount a private
signing key or the broker's Google secret into the web container.

The gateway preserves bearer Authorization headers, drops browser-supplied demo
and service-delegation headers, strips cookies in both directions, disables
upstream request retries, and omits query strings from access logs so callback
authorization codes are not recorded there. Configure equivalent query/body
redaction at the external ingress and telemetry layers. Responses use no-store;
the callback route serves the application, which validates OIDC state/nonce and
exchanges its one-time code using PKCE.

The smoke script starts a disposable container with no external network and
synthetic TLS upstreams. It checks callback routing, public configuration,
authenticated header forwarding, header isolation, host rejection, and failed
TLS hostname verification. It removes the container and test certificates.
These checks do not establish customer ingress, Google OAuth, or production HA.
