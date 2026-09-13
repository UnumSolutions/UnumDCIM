# ADR 0021: Independent modules, site authority and a familiar twin

- Status: accepted architecture; partial foundation implementation
- Date: 2026-09-12
- Supersedes: monolith packaging in the walkthrough; broad in-process community
  extensions in D24; release-cadence-only compatibility in D27; centrally ordered
  audit assumptions during site disconnection.

Each business module owns its database, contracts, migrations, workers and release
artifact. Retain Python/Django and TypeScript/React; prohibit cross-domain ORM and
table access. Shared physical infrastructure is allowed. Use REST, versioned
events, transactional outboxes and duplicate-safe consumers. Workflow coordinates
domain reservations and resumable execution; it does not own placement.

Independent modules require tested compatibility manifests. LTS combinations span
three years; development 0.1.0 is NOT an LTS. Evolve schemas using expand/migrate/
contract. Verify signatures, dependencies and migration compatibility before
installation. Isolate community backend code and frontend origins/frames.

Sites hold persisted execution authority with epochs. Offline operation lasts
72 hours under preauthorized MFA grants. Authority transfer requires connectivity
and fencing. Cross-site work waits; unreachable Nlyte-owned changes stay staged.
Local producer/site audit chains anchor centrally after reconnection.

The twin defaults to a Nlyte-familiar 2D floor plan, hierarchy, elevations and
inspector. One scene DTO feeds 2D and 3D. Effects are optional. Ghosts represent
proposals, while measured, estimated and illustrative overlays remain distinct.

See `docs/implementation-status.md` for actual coverage. Customer Nlyte version,
API contract, workflows and reference screens remain unavailable discovery inputs.
