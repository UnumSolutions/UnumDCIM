# UnumDCIM

Open-source Data Center Infrastructure Management targeting enterprise deployments. Status: **runnable foundation**. Independent Django services power a React/three.js twin, controlled placement workflow and coexistence rehearsal. Full Nlyte replacement and production qualification are not complete.

## Run the digital twin

Requires Python 3.12, Node.js 22+ and npm. With `uv` installed:

```sh
uv venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
npm --prefix web ci
npm --prefix web run build
.venv/bin/python scripts/dev.py
```

Open [the local twin](http://127.0.0.1:8080). Select an asset, propose a move to a
free U range, switch the explicit demo identity from Alex to Jordan to approve,
then execute. The home page offers Ashburn and Dallas locations, with 32 populated racks, two empty MDF/IDF cabinets, and 128 synthetic assets. Nlyte-owned placements
remain staged; no Nlyte instance is contacted.

Five services use separate local databases. A loopback-only gateway serves the
twin and supplies synthetic identities. **Never expose this gateway as production
authentication.** Ctrl+C stops the group; records persist in `.data/`.

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_boundaries.py
npm --prefix web run test
npm --prefix web run build
```

For database and broker qualification, start Docker and run:

```sh
.venv/bin/python scripts/qualify.py
```

This creates disposable PostgreSQL databases with separate migration and runtime
roles, starts a NATS JetStream broker, and tests tenant isolation, concurrent
reservations, duplicate execution, broker outage/restart, and lost acknowledgements.
It removes its containers and databases when finished. Evidence is written to
`.data/qualification/latest.json`; no customer database is used.

The API supports signed OIDC access tokens with MFA claims, verified caller
delegation, and PostgreSQL FORCE row-level security. See
[authentication and tenant enforcement](docs/security-authentication.md).
The browser identity selector remains a local demo facility. For staff sign-in,
see the [Google Workspace broker integration](docs/google-workspace.md) and
[production browser gateway](deploy/web/README.md). A customer identity provider
and target Nlyte instance must be qualified before a real pilot.

See [coverage and remaining gates](docs/implementation-status.md),
[the twin design review](docs/design/twin-review.md), and
[deployment qualification](deploy/README.md).

## Try the coexistence planner

```sh
.venv/bin/python -m pytest tests/test_reconcile.py tests/test_contracts.py -q
.venv/bin/python -m unum_sync examples/coexistence.json
```

The example plans changes in both directions using synthetic data; it does not
connect to or modify Nlyte. See [the review and implementation sequence](docs/nlyte-coexistence.md)
for tested behavior, limitations and the path to a gradual migration.
The [read-only pilot guide](docs/nlyte-readonly-pilot.md) describes configured
discovery and sanitized fixture replay without guessing vendor API routes.

## What it will be

An open, simulation-ready asset library and a browser-native 2D/3D digital twin that install beside an incumbent DCIM (Nlyte first, NetBox as the free funnel, ServiceNow as the ITSM system of record) and grow, through per-field ownership promotion, into a full system of record for data halls, server rooms and IT closets, for a single operator or a managed service provider serving many clients. Demand and forecast management, hardware receiving and onboarding, and an MCP server for direct AI engagement are core.

## The open-core rule

This rule has exactly one form, repeated verbatim in ADR 0004 and the decision record.

**Free forever (Apache-2.0 core):** twin, library, all ingestion and sync connectors, OIDC/SAML/LDAP, MFA, SCIM 2.0, object and field-level RBAC, change log, webhooks, OpenDC integration, air-gap install, LTS releases, single-Organization demand and forecast management (ResourcePool, Reservation, DemandRequest, Runway, Scenario, runway with intervals, headroom dashboards, alerts, ServiceNow demand mirror, MSP client and site rollups within one Organization), and the MCP server with all its tools.

**FSL tier (`ee/`, FSL-1.1-Apache-2.0, each version converts to Apache-2.0 on its second anniversary):** multi-Organization portfolio rollups (cross-tenant aggregation), ML auto-model selection and ensembles, AI placement optimization, portfolio Monte Carlo, procurement-lead-time optimization, colo revenue analytics with rate plans, audit-event streaming, hosted control plane, certified-connector packaging, extended-support backports.

The core is never relicensed.

## Where to read

- `docs/decisions/00-walkthrough.md`: the founding design walkthrough (decisions D01 to D31, architecture, roadmap, risks).
- `docs/decisions/01-addendum-a.md`: corrections and operational decisions D32 to D62.
- `docs/decisions/02-addendum-b.md`: ServiceNow push/pull, edge scope, multi-client operation, receiving and onboarding, demand and forecast, MCP (D63 to D83).
- `docs/adr/`: one architecture decision record per one-way door.
- `docs/parity-checklist.md`: what "parity with enterprise DCIM" means and when each item ships.
- `docs/fact-sheet.md`: verified facts with URLs, corrected claims, open items.
- `docs/founder-questions.md`: decisions only the founder can make, with recorded answers.
- `docs/licenses/allowlist.md`: inbound license policy.
- `docs/servicenow/setup-kit/`: the ServiceNow setup kit (placeholder).

## Contributing

Contributions to the core are accepted under the Developer Certificate of Origin (`CONTRIBUTING.md`). Asset contributions require a rights attestation. See `GOVERNANCE.md`, `SECURITY.md` and `CODE_OF_CONDUCT.md`.
