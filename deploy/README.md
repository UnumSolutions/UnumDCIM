# Deployment qualification

These templates deploy the application modules. Infrastructure HA, Kubernetes
rollouts, Linux host updates, TLS routing, database failover and restore still
require qualification on the target infrastructure. No infrastructure is
provisioned by the local demo.

Local qualification on 2026-09-13 built and smoke-tested all five module images
on Linux arm64. Helm 4.3.0 lint and rendering passed for all five module values,
including rejection checks for unsafe or missing configuration. Kubernetes and
Ansible execution remain unverified.

## Module images

Build each implementation separately, then run the isolated smoke check:

```sh
for module in inventory placement workflow synchronization registry; do
  docker build --build-arg MODULE="$module" -t "unum-$module:qualification" .
done
python deploy/smoke_images.py
```

The smoke check starts each image with synthetic data in a temporary filesystem,
no network access, a read-only root, UID 10001 and all capabilities dropped. It
checks `/health`, `/ready`, authentication, authenticated domain reads and that
`/app/services` contains only the selected domain. All containers are removed
when their checks finish. This checks image packaging and startup; the separate
PostgreSQL/NATS integration suite checks service transactions and recovery.

Only the selected domain source is included, along with shared infrastructure.
Publish, sign and record immutable image digests before attempting deployment.
Planned registry entries are not deployable modules. A locally built image tag
is not a qualified production artifact.

## Production identity and database configuration

Human API requests require RS256 OIDC access tokens with the configured issuer,
audience, expiry, API scope and tenant/site/role claims. MFA must be represented
by `amr` containing `mfa`, or by an explicitly accepted `acr` value. Configure the
same API audience across cooperating modules so delegated user credentials can
be verified downstream. Browser login and token delivery must use the intended
identity provider integration; the synthetic demo identity switch is not a
production gateway.

Machine credentials use `UNUM_AUTH_TOKENS` entries with role `service` and
explicit tenant/site grants. Workflow sends its `UNUM_SERVICE_TOKEN` together
with the original authenticated caller credential. Downstream services verify
both and intersect their tenant/site grants. The configured workflow token
therefore limits which tenant/site cell that workflow instance can operate.
Configure HTTPS or authenticated mesh transport between modules and prevent
external clients from acquiring machine credentials. All production templates
set `UNUM_DEMO=0`; static human tokens are rejected outside demo mode.

Use a separate PostgreSQL database and two roles per module:

- The migration role owns the schema/tables and runs migrations once.
- The runtime role has only `CONNECT`, schema `USAGE`, table
  `SELECT/INSERT/UPDATE/DELETE`, and needed sequence `USAGE/SELECT`. It must not
  own tenant tables, inherit or assume the owner/elevated roles, have
  `SUPERUSER`, `BYPASSRLS`, or table `TRUNCATE` privileges.

Apply the module and shared migrations before granting runtime table access.
They enable and force tenant row-level security. Runtime connections are checked
for elevated privileges and unprotected tenant tables. Tenant scope comes from
verified authentication and is reset after each request. Use direct PostgreSQL
connections or **session pooling**; transaction/statement pooling cannot preserve
this session scope and is unsupported. A missing tenant sees no tenant rows.
Grant the runtime role access to newly created tables/sequences after each
migration while preserving these restrictions. Do not grant `ALL PRIVILEGES`.

Require PostgreSQL `verify-full` and install the server CA inside the container.
Do not reuse the migration credential in the application environment. The
examples in `linux/module.env.example` and `linux/migration.env.example` name
all required settings and contain placeholders only. Provision real credentials
through the chosen secret manager, with files readable only by root (0600).

Tenant-scoped operational commands also require an explicit tenant:

```sh
python manage.py verify_audit --tenant TENANT
python manage.py publish_outbox --tenant TENANT
```

Run outbox publication as a supervised tenant-scoped worker with the same
restricted database role. The API chart below does not deploy that worker.
Provision NATS JetStream authentication/TLS, stream subjects, durable consumers,
redelivery and DLQ operations separately.

## Kubernetes

Install one `deploy/helm/unum-module` release per module. Start with
`deploy/helm/production-values.example.yaml`, replace the image with a verified
immutable digest, and supply the runtime secret, separate migration secret,
PostgreSQL CA secret, allowed hosts, OIDC settings and authenticated service
URLs. Runtime and migration secrets supply their respective PostgreSQL
credentials and `UNUM_SECRET_KEY`; the runtime secret also supplies scoped
machine credentials. The chart places non-secret OIDC settings in explicit
container environment variables.

The chart rejects unknown modules, unpinned images, fewer than two replicas,
missing identity configuration and non-HTTPS issuer/JWKS endpoints. It provides
startup-independent liveness, database readiness, rolling updates, host spreading
and disruption budgets. Application and migration containers run with read-only
roots and writable temporary volumes.

```sh
helm lint deploy/helm/unum-module -f YOUR_MODULE_VALUES.yaml
helm template inventory deploy/helm/unum-module -f YOUR_MODULE_VALUES.yaml
```

Rendering/linting does not establish Kubernetes API admission, rollout, HA or
load behavior. Application replicas do not provide database HA. Provision and
test PostgreSQL, NATS JetStream and storage independently. Configure ingress
TLS/mTLS, network policies, workload identity and narrowly scoped DB grants
before real data. Migrations run in one Helm hook Job; serialize releases
targeting the same module. Never migrate from every application replica.

## Linux

The Ansible inventory controls placement of modules on hosts. The playbook
requires pre-provisioned 0600 credential files and immutable images, updates one
host at a time and waits for readiness. Mount PostgreSQL trust material at
`/etc/unum/trust`, matching the environment example. Run expand-only migrations
once with the separate migration role before rolling application deployment.
A signature/compatibility preflight, drain coordination and rollback automation
remain qualification work.

The Patroni file is a policy fragment, not an operational cluster. An actual HA
cell requires at least three independent data hosts, quorum, fencing, redundant
ingress and trusted transport. Synchronous replication alone does not prove the
single-host-failure recovery objective.

## Remaining production qualification

- Customer identity-provider login/MFA, claims mapping, revocation and secrets rotation.
- Live Nlyte endpoint discovery, read-only polling validation and licensed workflow parity.
- Durable site federation, revocation distribution and offline identity/secrets integration.
- Signed plugin installation, sandbox runner and lifecycle management.
- Supervised NATS consumer deployment, DLQ operations and failover/restore drills.
- Actual LTS compatibility combinations and medium-estate load qualification.
