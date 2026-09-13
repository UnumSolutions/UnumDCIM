# Contributing

The project includes five independent Django services, a React digital twin, and
a conservative reconciliation planner. Use Python 3.12 and Node.js 22 or newer;
follow the root README to install the pinned dependencies. Use synthetic fixtures
and never commit customer data, tokens, private keys, database files, or restricted
vendor documentation.

## Development checks

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_boundaries.py
npm --prefix web test
npm --prefix web run build
```

Changes to locking, tenant enforcement, outbox publication, or recovery also need
`.venv/bin/python scripts/qualify.py` with Docker running. It tests real PostgreSQL
and NATS in disposable containers. Default test runs use temporary SQLite files;
ambient PostgreSQL credentials are ignored. Frontend network changes need tests
for failed and out-of-order responses, not only successful rendering.

Domain services communicate through authenticated APIs/events rather than
cross-service model imports. Keep migrations compatible with the selected
module's isolated database. Production requests require restricted database
roles and authenticated tenant context; do not weaken these checks to make tests
pass. Record unverified customer behavior explicitly in the acceptance ledger.

## Developer Certificate of Origin

All contributions to the core are accepted under the Developer Certificate of Origin (https://developercertificate.org/). Sign off every commit:

```
git commit -s
```

Contributions to `ee/` require a Contributor License Agreement; the maintainers will send it when the first `ee/` pull request opens.

## Inbound licenses

Only code under the licenses listed in `docs/licenses/allowlist.md` may be added to the core. GPL and AGPL software may only be integrated as an isolated container or command-line process.

## Asset contributions (device types, elevation images, 3D models)

Every uploaded or contributed image, drawing or model must carry a rights attestation: either "own work" or "vendor permission attached". Pull requests without an attestation are closed. Vendor Visio stencils, Icecat content, GrabCAD models and non-CC Sketchfab models are never accepted into `library-core`. Definitions are contributed under CC0-1.0 and, where possible, upstreamed to netbox-community/devicetype-library; authored art is contributed under CC-BY-4.0.

## Facts and claims

Any factual claim added to `docs/` must carry a URL to a primary source or be labeled UNVERIFIED. The fact sheet's "corrected" list records wordings that failed verification; do not reintroduce them.

## Takedown

If you believe content in this repository infringes your rights, email the address in `SECURITY.md`. Confirmed takedowns are actioned within 72 hours and recorded in a revoked-asset list.
