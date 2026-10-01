# Google Workspace staff sign-in

UnumDCIM uses Google Workspace or Cloud Identity for staff identity through a
self-hosted Keycloak broker. The broker performs a separate required OTP check
and issues the access token accepted by the existing APIs. Google credentials
and client secrets never enter the browser application or the five DCIM services.
The local configuration is implemented; customer Google OAuth and production
browser acceptance still require the setup and checks below.

Google's [canonical OpenID Connect reference](https://developers.google.com/identity/openid-connect/reference)
distinguishes Google ID tokens from access tokens for Google APIs. It lists no
Unum authorization claims and does not document `amr` or `acr` in its canonical
ID-token claim list. A domain-wide 2-Step Verification policy therefore does not
establish the particular MFA assertion expected by Unum. Do not configure the
Unum API issuer as Google or add a constant `mfa` claim to make a Google token pass.

The broker preserves the API's signature, issuer, audience, scope, role, tenant,
site, and MFA checks. This avoids making Unum responsible for an additional
password/factor store, enrollment engine, recovery UI, and signing service. It
does add an identity service and database to operate. Google sign-in requires
connectivity to Google; a disconnected installation needs a separately approved
local identity configuration with its own MFA. There is no automatic weaker
fallback when Google is unavailable.

## Generate the realm

The generator targets **Keycloak 26.7.5**, pinned to the official container digest
in [generate_realm.py](../deploy/identity/generate_realm.py). Its output contains
no users, passwords, Google secret, or default Unum grants. Copy
[workspace.example.json](../deploy/identity/workspace.example.json) to a private
directory and replace all example values:

```sh
.venv/bin/python deploy/identity/generate_realm.py \
  --config /private/identity/workspace.json \
  --output /private/identity/operations-realm.json
```

The output must be new and is created with mode 0600. The generator rejects
extra fields, secret fields, HTTP, wildcard redirects, cross-origin callbacks,
wildcard hosted domains, and invalid client/realm identifiers. The callback and
logout URL must exactly match the production web configuration in
[deploy/web/runtime.example.json](../deploy/web/runtime.example.json).

Import the JSON into a **new** realm using Keycloak's startup `--import-realm`
mechanism, named `<realm>-realm.json` and mounted read-only in
`/opt/keycloak/data/import/`.
Provide `UNUM_GOOGLE_CLIENT_SECRET` through the deployment's secret-delivery
mechanism. The import placeholder `${UNUM_GOOGLE_CLIENT_SECRET}` is resolved by
Keycloak; the generator never reads the secret. Existing realms are not an
upgrade target for this generator: export/review a proposed migration rather
than deleting or recreating an established realm and its stable principals.
See [Keycloak import/export](https://www.keycloak.org/server/importExport).

Use production `start`, a fixed HTTPS hostname, verified TLS, a supported
production database, secret storage, backups, and restricted administration.
The qualification harness's `start-dev`, ephemeral H2 database, and HTTP loopback
port are test settings only. The pinned image does not replace these deployment
requirements. See [Keycloak production configuration](https://www.keycloak.org/server/configuration-production).

## What the generated policy enforces

The browser client is `unum-web`, a public authorization-code client with required
PKCE S256 and exact callback/origin/logout lists. Implicit, password, service
account, device, CIBA, token exchange, and JWT assertion grant paths are disabled
for this client. Its API scope is `unum.api`, and the API audience is `unum-api`.
Refresh tokens rotate; access tokens expire after five minutes, with a 30-minute
idle and eight-hour maximum broker session.

The browser authentication flow has only the Google redirector, without a cookie
shortcut. A first broker login can create an unprivileged account but cannot
automatically link an existing account by matching its email. The post-broker
flow requires OTP and records achieved level 2 with maximum age zero. The browser
client's minimum ACR is `urn:unum:acr:staff-mfa`; changing the requested ACR cannot
lower this requirement. The ACR mapper emits the achieved level in the access
token, rather than a fixed assurance value. Refreshing an already authenticated
application session is not a new login; it does not repeat OTP.

This distinction matters: Keycloak's ordinary browser flow stops after external
identity-provider login, so placing an OTP step after its redirector is
insufficient. Required additional steps belong in the configured post-login
flow. The server documents both this mechanism and minimum ACR/max-age controls.
See [post-login flow](https://www.keycloak.org/docs/latest/server_admin/#_identity_broker_post_login_flow)
and [step-up authentication](https://www.keycloak.org/docs/latest/server_admin/#_step-up-flow).

The Google provider checks the returned hosted-domain claim against the explicit
comma-separated domain allowlist. This is enforced when validating the Google
token, not merely as a login-screen hint. The exact implementation is visible in
[GoogleIdentityProvider.java at 26.7.5](https://github.com/keycloak/keycloak/blob/26.7.5/services/src/main/java/org/keycloak/social/google/GoogleIdentityProvider.java).
Users are linked through their provider subject; email is not an authorization
key. Google also instructs applications to check the hosted-domain claim and use
the immutable subject in its [server verification guide](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).

## Grant staff access

After a staff member completes Google sign-in and initial OTP enrollment, an
identity administrator verifies that account and assigns these managed attributes:

| Attribute | Value |
| --- | --- |
| `unum_role` | One string: `viewer`, `operator`, `approver`, or `admin` |
| `unum_tenant` | One exact tenant identifier |
| `unum_sites` | One or more exact site identifiers; a multi-valued attribute |

Identifiers begin with an ASCII letter or digit and contain at most 100 letters,
digits, underscores, dots, colons, or hyphens. No wildcard tenant/site is accepted.
The attributes are editable and visible only to identity administrators in the
user-profile configuration. Other unmanaged attributes are disabled. Access-token
mappers emit the role/tenant as strings and sites as an array. No staff member
gets a role, tenant, or site merely by belonging to the Google domain.

Review initial enrollment, factor replacement, and recovery out of band before
granting sensitive access. Restrict broker administrators and audit grant/factor
changes. An offboarded Google account can still have a previously established
broker session, so revoke the broker session and remove its grants as part of
offboarding. Short access-token expiry bounds already issued bearer-token use;
this implementation does not claim immediate JWT revocation or automatic Google
directory provisioning.

Configure every service consistently:

```sh
UNUM_DEMO=0
UNUM_OIDC_ISSUER=https://identity.example.invalid/realms/operations
UNUM_OIDC_JWKS_URI=https://identity.example.invalid/realms/operations/protocol/openid-connect/certs
UNUM_OIDC_AUDIENCE=unum-api
UNUM_OIDC_SCOPE=unum.api
UNUM_OIDC_MFA_ACR_VALUES='["urn:unum:acr:staff-mfa"]'
```

The browser requests `openid profile email unum.api`, the same accepted ACR, and
the `google` provider alias. Its runtime configuration is public; the Google web
OAuth client secret belongs only to Keycloak. Maintain TLS between the gateway,
services, and broker. See [API authentication](security-authentication.md) and
[the production browser gateway](../deploy/web/README.md).

## Customer configuration and acceptance

The administrator must supply the actual Workspace/Cloud Identity hosted
domain(s), a Google web OAuth client ID and secret, the application HTTPS origin,
the broker HTTPS hostname/realm, and the approved staff-to-tenant/site/role map.
In Google, register the broker callback exactly:

```text
https://identity.example.invalid/realms/operations/broker/google/endpoint
```

Use the organization's applicable internal-app policy and allow only the needed
sign-in scopes (`openid`, `email`, `profile`). Configure Google Admin app access
for the intended staff; this integration requires no Gmail, Drive, or Directory
API access and no domain-wide delegation. Google explains these controls in
[Manage app access](https://support.google.com/a/answer/7281227). Keep the Google
organization's own MFA policy enabled; the broker's local OTP is additional
per-login evidence, not a claim about Google's authentication method.

Before a pilot, verify a real staff login through HTTPS, OTP enrollment/reentry,
approved and unapproved users, consumer/wrong-domain rejection, callback/logout,
token expiry, role/site isolation, factor recovery, offboarding/session removal,
and broker/Google outage behavior. Confirm two distinct principals remain
required for change approval. No customer login or Google Admin setting is
created by the repository scripts.

## Reproduce local qualification

```sh
.venv/bin/pytest -q deploy/identity/test_realm.py
.venv/bin/python deploy/identity/qualify.py
```

The second command runs the pinned image on a new Docker network with a random
loopback-only port and synthetic accounts. Google's endpoint hostnames resolve
to container loopback, and the HTTP harness rejects nonlocal requests/redirects.
It first inspects the imported
Google configuration, then replaces that provider with a local synthetic OIDC
realm for protocol testing. It checks actual broker/OTP forms, signed token
claims, missing/wrong PKCE, grant assignment and attempted escalation, repeated
SSO/ACR downgrade, and disabled password grants. It removes its container and
network even after a failed check; cleanup failure makes qualification fail.

The harness uses an HTTP protocol client and test-only cookie transport handling,
so its report explicitly marks real Google login and browser/TLS acceptance as
unverified. It does not contact a customer system, validate Google credentials,
or establish production availability. Its printed report contains only version,
image digest, named checks, and pass/failure status.
