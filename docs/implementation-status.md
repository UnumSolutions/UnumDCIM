# Implementation status and acceptance ledger

This is a runnable foundation, not a complete or production-qualified Nlyte
replacement. The project began as documents and an offline planner.

## Delivered

| Capability | Implementation / verification |
| --- | --- |
| Independent services | Inventory, placement, workflow, synchronization, registry; separate processes/databases; HTTP integration tests and import-boundary check |
| Digital twin | React/TypeScript, floor plan, elevations, three.js view, optional walkthrough, inspector, themes, reduced effects; built and browser-reviewed |
| Controlled moves | Persisted proposals, separate-principal approval, revisions, reservations, idempotent execution, definitive expiry/re-plan states, interrupted-response recovery, and active queues with paginated completed history; HTTP and frontend tests |
| Nlyte-owned moves | Staged awaiting owner confirmation; remote writes disabled; HTTP test |
| Reconciliation | Connection IDs, validated current/historical poll provenance, mapped types, optional additions, per-field quarantine and conflict preservation; contract tests |
| Conflict queue | Both values and baseline, authorized resolution staging; canonical inventory unchanged |
| Authentication | RS256 OIDC API access-token verification, required MFA assurance, verified service/caller delegation and intersected site grants; synthetic identity switching remains demo-only |
| Database isolation | FORCE RLS on all 14 tenant tables, restricted runtime-role checks, explicit tenant context, audit append-only trigger, and tenant-scoped workers; real PostgreSQL tests |
| Audit/outbox | Local hash chains, transactional outbox, verifier, bounded NATS publisher and transactional duplicate suppression; real JetStream outage, restart, lost-ack and replay tests |
| Compatibility | Manifests and contract/test-matrix preflight; signature verification cannot be self-attested through API |
| Offline policy | Signed 72-hour grant primitives, scope, epoch, expiry and revocation tests; not wired to API authentication |
| Deployment | Five module image builds/smoke tests, Helm lint/render and invalid-config rejection; Linux host placement/Quadlet templates; actual cluster/host deployment remains unverified |
| Read-only discovery | Explicit configured routes and JSON mappings, bounded GET-only pagination, secret-free aggregate reports and sanitized fixture replay; no target Nlyte compatibility claim |

Registry entries marked `planned` are not installed services. Synthetic overlays
do not represent implemented power, cabling or thermal business modules.

## Location selection amendment

The home directory offers Ashburn and Dallas, totaling three halls, 32 cabinets
and 128 synthetic assets. Opening either location starts in its floor plan.
Cabinet selection supports modifier-click, Shift ranges, keyboard Space, explicit
Multi-select mode, Select all and Clear. Selected cabinets show combined equipment
and capacity. Browser checks verified four-cabinet range selection, two-cabinet
toggle selection and selection reset when switching to Dallas.

Verification on 2026-09-30: 230 backend tests and 16 subtests passed with the
disposable PostgreSQL/NATS qualifier. The normal SQLite run skips the five
infrastructure-only tests. All 41 frontend tests and the
production frontend build passed. Migration drift and domain import boundaries
were checked. Qualification writes exact infrastructure image digests and exit
status to `.data/qualification/latest.json`; CI reruns the qualifier.

The September 30 regression checks cover interrupted successful response bodies
without changing proposal retry keys, bounded browser requests, independent
service refresh results, unfinished work remaining visible beyond 100 completed
changes, scoped history traversal, and discovery cancellation/compressed-response
rejection. Discovery's network deadline does not preempt synchronous parsing or
OS resolver cleanup; see the pilot guide for the precise limit.

The infrastructure tests exercise restricted per-module database roles, raw SQL
tenant isolation, competing U reservations, duplicate reservation/execution,
audit mutation denial, broker restart durability and transactional consumer
deduplication. This evidence does not establish HA, scale, or real Nlyte parity.

## Browser review

The original demo review verified floor plan/tree/inspector, keyboard-entered move and 3D rendering.
Proposed app-01-01 from U3 to U35 as Alex, approved as Jordan, then executed.
Placement changed to U35/revision 2 only after execution. No browser errors were
observed during 3D review. Pending ghosts persist after submission. Dialogs have
focus handling; failed dependencies expose stale data.

The updated isolated browser smoke check loaded the directory/floor plan and
submitted an Alex proposal at U35 while confirming placement stayed at U3.
Approval was left pending; current separate-principal approval, execution and
lost-response recovery are verified by the automated HTTP integration tests.

Overlay values and floor dimensions are synthetic. Familiarity is based on the
recorded design requirements, not inspection of the customer's Nlyte screens.

## Production gates still outstanding

1. **Nlyte discovery:** version, licensed API, reads/writes, auth, paging, rates,
   concurrency, workflows, custom fields, reports, screenshots and ServiceNow
   dependencies. Map every required behavior to acceptance evidence.
2. **Security:** customer IdP/JWKS/claim configuration and MFA assurance acceptance,
   browser login/session integration, full field policy, tenant-key management,
   privileged access procedures and retention anchoring. API token validation,
   runtime-role checks, FORCE RLS and audit triggers are implemented; an owner or
   superuser can still change schema/grants. See the authentication guide.
3. **Federation:** durable site replication, revocation distribution, fencing,
   partition recovery and local secrets. Unit tests do not prove a 72-hour
   operational disconnected deployment.
4. **Live synchronization:** polling, conditional writes, canaries, rate limiting,
   unknown-outcome reconciliation for remote vendor writes and ownership promotion.
   Local move expiry/re-plan UI and ambiguous-ack recovery are implemented.
   Nlyte-owned proposals remain staged because no verified adapter is configured.
5. **Remaining domains:** complete lifecycle/receiving, power/cooling/cabling,
   forecasts, telemetry, reports, library ingestion and simulation. Inventory
   currently exposes synthetic records and revisioned name updates.
6. **Plugins:** trusted verifier, installer, isolated runner/UI protocol,
   permission grants, revocation and resource/egress enforcement.
7. **Qualification:** mixed-release LTS matrix, medium-estate load, HA failover,
   actual Kubernetes/Linux deployment, disaster recovery, accessibility
   audit and acceptance by Nlyte operators.

Deployment templates and version ranges do not satisfy those gates. SQLite is
used only for local development. The new PostgreSQL/NATS tests establish the
specific covered failure cases, not broad operational or HA qualification.

## Operations

Use the root README. The development gateway and five services bind only to
loopback. Data persists in `.data/`; seed commands preserve existing edits. Logs
are in `.data/logs/`; Ctrl+C stops the group. The identity selector is explicitly
a demo mechanism and must never be exposed as production authentication.
Use `scripts/dev.py --data-dir /private/temporary/path --port 18080 --base-port 18101`
for an isolated browser smoke test. Demo startup ignores ambient PostgreSQL
credentials. Audit verification and outbox publishing now require `--tenant`.
