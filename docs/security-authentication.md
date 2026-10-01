# API authentication and tenant enforcement

This describes implemented controls and their configuration. It is not an
assertion that a customer identity provider or deployment has been qualified.

## OIDC access tokens

Outside `UNUM_DEMO=1`, human static tokens are rejected. Configure the API audience
and a trusted issuer's HTTPS JWKS endpoint using deployment secrets/configuration:

```text
UNUM_OIDC_ISSUER=https://identity.example.invalid/realms/operations
UNUM_OIDC_AUDIENCE=unum-api
UNUM_OIDC_JWKS_URI=https://identity.example.invalid/realms/operations/protocol/openid-connect/certs
UNUM_OIDC_SCOPE=unum.api
```

These are placeholders, not a configured provider. The provider must issue RS256
access tokens for this API with `iss`, `aud`, `sub`, `iat`, and `exp` claims, the
configured API scope, and an `amr` array containing `mfa`. Alternatively, an
administrator can set `UNUM_OIDC_MFA_ACR_VALUES` to a JSON list of the provider's
verified MFA assurance values. Do not put ordinary password assurance values in
that allowlist. The verifier checks the signature, issuer, audience and time
claims through [PyJWT](https://pyjwt.readthedocs.io/en/stable/usage.html).

The default authorization claims are `unum_role`, `unum_tenant`, and `unum_sites`.
Roles are `viewer`, `operator`, `approver`, or `admin`; tenant is one identifier,
and sites is a nonempty list of identifiers. Claim names are configurable through
`UNUM_OIDC_ROLE_CLAIM`, `UNUM_OIDC_TENANT_CLAIM`, and `UNUM_OIDC_SITES_CLAIM`.
Identifiers must begin with an ASCII letter/digit, contain only letters, digits,
underscore, dot, colon or hyphen, and fit within 100 characters. Identity-provider
administrators must control these claims; users must not be able to edit their
own authorization grants. The audit principal derives from issuer and stable
subject, so renaming a login cannot bypass separate-principal approval.

Use `Authorization: Bearer <access-token>` over trusted TLS. Unknown signing keys
are resolved from the configured JWKS URI; token-supplied key URLs are ignored.
Provider failures never permit unverified tokens. The production browser supports
Google Workspace through a self-hosted OIDC broker with mandatory step-up MFA;
see [the configuration and qualification guide](google-workspace.md). It uses
authorization code with PKCE, keeps tokens in memory, and obtains its effective
identity from the authenticated `/api/v1/identity` endpoint. The development
gateway remains a separate, explicitly synthetic mode. Customer Google OAuth,
TLS, logout/revocation policy, and assurance acceptance remain pilot gates.

## Service delegation

`UNUM_AUTH_TOKENS` may contain scoped service credentials outside demo mode. Store
these in deployment secrets, not source control. `UNUM_SERVICE_TOKEN` identifies
the calling service. A workflow forwards both its service credential and the
original caller credential in `X-Unum-Caller-Authorization`. The receiver validates
both, requires a service sender, requires matching tenants, and intersects site
grants. Unsigned tenant/role/site headers confer no access. Downstream audit events
retain the initiating human principal. Configure trusted TLS/mTLS transport
between services; this header carries a bearer credential and must not be logged.

A service credential is scoped to one tenant. A deployment serving additional
tenants needs corresponding authorized service routing/credentials; the current
fixed credential fails closed across other tenants rather than widening scope.

## Database controls

Migrations enable and force RLS on all current tenant tables. Policies restrict
reads and writes to the authenticated `unum.tenant` connection setting; absent
scope exposes no rows. Application roles must not own tenant tables, inherit an
owner/elevated role, have `BYPASSRLS`/superuser, or have `TRUNCATE` rights. The
runtime checks these invariants. PostgreSQL's table-owner and superuser behavior
is described in its [row security documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).

`tenant_scope` sets and clears connection context without wrapping network calls
in a database transaction. Use direct PostgreSQL connections or session pooling;
transaction-pooling proxies are unsupported. Site and field permissions are
enforced by API policy; the database RLS boundary is the tenant.

Audit entries have tenant provenance and an always-enabled trigger rejecting
UPDATE, DELETE and TRUNCATE. Runtime grants also exclude these operations. Audit
heads remain mutable for append operations. An owner/superuser can change schema
or grants, so external retention anchors, tenant-key management, privileged access
control and recovery qualification remain necessary deployment work.

Workers require an explicitly authorized tenant:

```sh
python manage.py publish_outbox --tenant your-tenant
python manage.py verify_audit --tenant your-tenant
```

Consumers pass `trusted_tenant` from their trusted subscription configuration;
an event's tenant must match it before applying a projection. Projection updates
and durable duplicate suppression share the same database transaction.

## Verification

`tests/test_auth.py` exercises real RSA signatures, issuer/audience/time checks,
MFA, tampering, provider outage, production static-token rejection and delegation.
`tests/integration/test_workflow_recovery.py` verifies authorization across actual
HTTP services. `scripts/qualify.py` provisions restricted PostgreSQL roles and
checks RLS without ORM tenant filters, concurrent moves, and audit mutation denial.
These tests do not replace acceptance against the customer's IdP and infrastructure.
