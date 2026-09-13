# Nlyte coexistence: review and first executable slice

> Historical initial review. See `implementation-status.md` and ADR 0021 for the
> independently running services, twin and current implementation coverage.

Review date: 2026-09-12. This workspace initially contained the founding design
record only. There was no application, database, connector, UI, deployment package,
or test suite to review, and the supplied directory was not a Git checkout.

The intended product is a functional replacement introduced incrementally beside
Nlyte. It is not yet an API-compatible replacement for Nlyte clients or a complete
DCIM application. Full parity remains the work in [the parity checklist](parity-checklist.md).

## Findings that affect the migration

| Priority | Finding | Consequence / action |
| --- | --- | --- |
| P0 | No runnable application existed. | Implement inventory, persistence, authorization, audit, APIs and operator workflows before a live pilot. |
| P0 | Actual Nlyte write endpoints, payloads and concurrency guarantees are unverified for the target installation (D32). | Require its version/API contract and staging capability report; never infer CRUD from an OData read URL. |
| P0 | Editing in either UI needs intent routing, not two canonical owners (ADR 0007). | Route a non-owner edit to its owner, then read back the accepted result before updating canonical data. |
| P0 | No durable baseline, crosswalk, outbox or retry implementation exists. | Persist these transactionally; use connector-scoped IDs and conditional writes. |
| P1 | Two-snapshot discrepancy suppression increases latency. | Publish measured freshness including two observations, queue time and read-back; do not promise immediate synchronization. |
| P1 | ServiceNow/Nlyte Asset Sync could add a third writer. | Inventory existing integrations and keep the UnumDCIM CMDB path pull-only until explicit ownership cutover (D21b/D63). |
| P1 | Placement, relationships and lifecycle are domain operations. | Keep placement atomic; validate occupancy, power and references; missing records never imply deletion. |
| P1 | A complete UI/workflow replacement is much broader than asset synchronization. | Agree on the first site's required workflows and retire modules only after acceptance testing. |

Nlyte publicly describes bidirectional ServiceNow integration and physical/logical
field ownership in its [integration description](https://www.nlyte.com/blog/servicenow-dcim-integration-closing-the-loop-between-logical-incidents-and-physical-impact/).
Its [BMC integration datasheet](https://www.nlyte.com/web/wp-content/uploads/2019/09/Nlyte_For_BMC_ITSM_Data_Sheet.pdf)
lists asset, location, mounting and custom-field integration through NgageAPI.
These sources establish integration use cases, **not** a verified HTTP contract,
write coverage, entitlements, ETags or transaction support for this deployment.
All of those remain UNVERIFIED until the target-instance probe in D32.

## Executable now

`unum_sync.reconcile` is a dependency-free Python planning module suitable for
later use inside the accepted Django control plane. It makes no network calls,
persists nothing and performs no writes. It was exercised locally on Python 3.9;
the application target remains Python 3.12 per ADR 0003.

From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 -m unum_sync examples/coexistence.json
```

The synthetic example produces a Nlyte-to-Unum name projection and an
Unum-to-Nlyte asset-tag intent. Its capability flags are fictional test inputs,
not a declaration of Nlyte support. Plans are review data, not executable commands.

| Observed state relative to last verified agreement | Plan |
| --- | --- |
| Both peers agree | `converged`: eligible for baseline advancement after current read-back validation |
| Divergence observed once, or values still changing | `pending`: wait for a second distinct complete poll |
| Only owner changed | `mirror`: propose projecting the owner's value |
| Only non-owner changed | `intent`: propose sending the edit to the owner; canonical value stays unchanged |
| Both changed differently | `conflict`: review both values; no automatic overwrite |
| Target lacks verified field write support | `blocked`: preserve discrepancy for operator action |
| Partial snapshot, scope mismatch, missing field or schema drift | Fail closed; pause reconciliation |

Concurrent conflicts deliberately remain unresolved in this first slice. ADR
0007's owner-wins default can preselect an operator resolution, but it does not
authorize this planner to destroy the losing edit. No ownership decision is
changed by this implementation.

Contract details:

- Inputs are normalized, explicitly linked records, scoped by tenant, connector
  instance and canonical entity ID. Crosswalk construction and authentication
  are not implemented. Scope checks are not a substitute for PostgreSQL RLS.
- `baseline` is the per-field last value verified in both systems. Polling alone
  never advances it. Bootstrap requires explicit owner selection and reviewed
  matching; an empty/missing baseline is rejected.
- `revision` is a target concurrency token; `observation_id` identifies a distinct
  successful complete poll. Poll IDs must come from the collector. Replaying a
  poll cannot satisfy the two-observation rule. An unchanged ETag can.
- Values contain only configured business fields. Adapters normalize identifiers,
  enums, units and nulls, excluding telemetry/audit noise. Absence means unknown
  or schema drift, while JSON null is an explicit field clear.
- Placement is one nested value (`placement`), not independently merged rack/U/
  face fields. Domain validation and reference translation are still required.
- Plans contain target revision, preimage hash and a deterministic operation key.
  These are inputs to future execution controls, not implemented idempotency or
  protection against concurrent remote writers. Re-plan both peers before execution.
- Creates, deletions, retirement, links, pagination, scheduling, approval storage,
  promotion/demotion and actual Nlyte transports are not implemented.

## Implementation sequence toward a live pilot

1. **Discover the target installation.** Record Nlyte version/build, API access,
   authentication, entity/field mappings, custom fields, pagination, deletion
   semantics, throttling, reads and writes, and conditional-update behavior.
   Include existing ServiceNow feeds. Use D32's probe checklist and authorized
   test records; supply a supported-capabilities report per connection.
2. **Build the Django/PostgreSQL control plane.** Implement tenant-scoped sites,
   locations, racks and assets; FORCE RLS and composite tenant references;
   ExternalReference unique on `(tenant, connection, entity_type, external_id)`;
   OwnershipPolicy, staged ChangeIntent, SyncObservation, per-field agreement,
   Conflict, transactional OutboxOperation and audited ownership transitions.
   Durable inbox/outbox keys must survive process restarts. Serial/tag duplicates
   require review; never auto-link ambiguous identities or rely on names.
3. **Import and compare without writes.** Traverse all pages; resolve parents
   before children; retain raw provenance; publish completeness, unsupported
   fields and schema drift. A failed or filtered poll cannot retire records or
   advance watermarks. Demonstrate inventory and rack views against a real sample.
4. **Enable one verified write path.** Start with a low-risk field on at most ten
   test assets. Execute approved intents through the authoritative system's
   workflow, recheck ownership and both snapshots, and use a verified atomic
   conditional update. If Nlyte offers no concurrency primitive or equivalent
   serialized workflow, keep unattended writes disabled; a read-before-write
   alone has a race window. Never write directly to Nlyte's application database.
5. **Add recovery and operations.** Enforce D47's dry-run approval, canary,
   read-back, rate limit, kill switch and schema-drift pause. On timeout, determine
   whether the write committed before retrying. Back off on throttling/transient
   failures; isolate permanent failures. If source/target changed, expire and
   re-plan the operation. Advance each baseline only after verified convergence.
   Compensating rollback is another conditional intent, never a blind restore.
6. **Promote ownership gradually.** Pilot one site's chosen fields/entity types;
   keep both projections synchronized. Promotion requires clean reconciliation,
   no pending/conflicting work, verified reverse projection and domain workflow
   acceptance. Freeze and drain scoped work during the audited transition.
   Demotion requires the same checks and a verified write-back route (ADR 0007).
7. **Retire Nlyte modules after parity.** Validate rack moves, receiving/retirement,
   power and network connectivity, capacity, work orders, reporting and remaining
   site-specific dependencies against the parity checklist before decommissioning.

Live-pilot acceptance must include changes initiated in either UI, simultaneous
edits, process restart after remote commit but before acknowledgement, duplicate
events, partial pages, schema drift, throttling, tenant isolation, atomic placement,
retirement review and promotion rollback. Current unit tests cover only the
offline planning contract; they do not establish live connector readiness.
