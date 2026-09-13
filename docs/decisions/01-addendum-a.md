> **Status:** accepted, 2026-09-12. Preserved verbatim from the research session.

# UnumDCIM Design Walkthrough — Addendum A (critic response)

Prepared 2026-09-08. This addendum closes every gap in the critic findings, corrects the unsupported claims in the draft, and adds the operational sections an enterprise architect expects. Decision numbering continues from D31; sub-decisions the critic named (D21b, D25b, D26b) keep those ids. Where the research digest lacked evidence, live sources were fetched on 2026-09-08 and are cited inline; where a source could not be reached, the item stays labeled **UNVERIFIED** and is treated as an assumption to validate, never as a design contract. New verified facts are consolidated in section A.5.

---

## A.1 Corrections to the draft (unsupported or wrong claims)

| # | Draft statement | What was wrong | Corrected statement |
|---|---|---|---|
| C1 | D01: native-mastered objects are "what incumbents structurally cannot hold" (upstream power chain, cooling chain). | Only NetBox/Nautobot lack these. dcTrack auto-generates one-line diagrams from utility feeds, generators, switchgear, transformers and panelboards (https://www.sunbirddcim.com/what-dcim); FNT models buses, rails, breakers, panels and rack PDUs "down to the power port level" (https://www.fntsoftware.com/en/use-cases/data-center); Nlyte's Connection Manager models power paths from the substation feed (https://www.datacenterknowledge.com/management/vendor-profile-nlyte-software-s-7-suite) and its Cooling Capacity Planner "maps your cooling infrastructure" (https://www.nlyte.com/products/nlyte-asset-optimizer/); dcTrack 9.1 has cooling derating and multi-zone assignment. | "Objects that **NetBox/Nautobot** structurally cannot hold and that incumbents hold only in closed, non-exportable form." The differentiator against Nlyte/dcTrack/FNT is openness (Apache-2.0 API, CC0 library, metric geometry, 3D art), not the existence of the chain. D12 ownership defaults for Nlyte shops are revised in D33. |
| C2 | D21/Phase 1: startup probe "fetches `$metadata` once". | No evidence Nlyte exposes `/nlyte/integration/api/odata/$metadata`; the digest lists it as an open question. FlowGate never calls it. | Probe attempts `$metadata`; on 404/401 it falls back to per-entity-set `$top=1` sampling to infer fields and types (D32). |
| C3 | D21/D15: "power-path and network-path overlays (Nlyte realtime values)". | Evidenced OData entity sets are Servers, Cabinets, PowerStrips, Networks, Chassis, LocationGroups, manufacturers, *Materials and `PowerStrips(id)/GetRealtimeValues` (per-outlet readings) plus AssetsAndHosts from a 2021 forum post. No connection, power-path, panel, breaker, network-port or floor-plan geometry entity is evidenced. | Phase 1 overlays sourced from Nlyte are limited to **per-outlet realtime values on rack PDUs**; chains are drawn only where UnumDCIM or NetBox holds the topology. Nlyte-sourced chain topology is a Phase 0 discovery item (D32) with three explicit fallbacks (D33). |
| C4 | D28: "no Sparkplug B decoder in Telegraf, so a decoder is written". | Partly wrong. Telegraf's `mqtt_consumer` README does not mention Sparkplug (https://raw.githubusercontent.com/influxdata/telegraf/master/plugins/inputs/mqtt_consumer/README.md), but Telegraf's `xpath_protobuf` parser documents Sparkplug B decoding by example: `xpath_protobuf_files = ["sparkplug_b.proto"]`, `xpath_protobuf_type = "org.eclipse.tahu.protobuf.Payload"` (https://raw.githubusercontent.com/influxdata/telegraf/master/plugins/parsers/xpath/README.md). | Sparkplug B is decoded with Telegraf `mqtt_consumer` + `data_format = "xpath_protobuf"` and the Eclipse Tahu `.proto` (Eclipse Public License 2.0, UNVERIFIED for the proto file itself); no custom decoder. Birth/death-certificate state tracking (NBIRTH/DBIRTH aliases) still needs a small stateful mapper in `unum-monitor`. |
| C5 | D17/D19: Cisco EoX "with customer SNTC credentials" stated as fact while the digest had it UNVERIFIED. | Now verified: "If you are a Cisco Smart Net Total Care (SNTC) customer, you are entitled to access the Cisco Support APIs" and likewise for Partner Support Services partners (https://developer.cisco.com/site/support-apis/). | Keep the design; drop the UNVERIFIED label; the connector requires the customer's own SNTC/PSS-entitled API credentials. |
| C6 | D30: "NetBox Labs' staged-change/branching products are NLUL-licensed". | netbox-branching is confirmed NLUL. The Change Management plugin's repository and product page returned 404 on 2026-09-08 (https://github.com/netboxlabs/netbox-change-management, https://netboxlabs.com/products/netbox-change-management/); its license is **UNVERIFIED**. NetBox Labs' pricing page places Change Management in Premium/Enterprise tiers (https://netboxlabs.com/pricing/). | "netbox-branching is NLUL-licensed; Change Management is a paid Premium/Enterprise product whose license text is not public." Design impact is unchanged: neither can be a dependency. |
| C7 | D21/Risk 3: "Nlyte claims 150k racks per instance". | A 2015 Nlyte 7 marketing claim via a vendor profile; not current sizing data. | Load planning uses the design partner's actual estate size; the 150k figure is cited only as historical marketing. |
| C8 | D04: "Every core relicensing in the comparables (Terraform, Redis) produced a Linux Foundation-hosted fork". | Over-generalized. MongoDB, CockroachDB and Sentry produced no LF fork; Elastic's fork (OpenSearch) was AWS-led and only later foundation-hosted. | "Terraform and Redis relicensings each produced an LF-hosted fork (OpenTofu, Valkey); other relicensings produced no fork but did produce trust loss." |
| C9 | D05: Grafana "is resented for" its paywall. | Editorial; no evidence in the digest. | "Grafana gates RBAC/SAML/SCIM/audit to Enterprise" (https://grafana.com/docs/grafana/latest/introduction/grafana-enterprise/); no sentiment claim. |
| C10 | D26: "Nlyte v16 itself ships Linux-Docker" as an argument against a Windows installer. | The v16 press release says "Windows and Linux-Docker deployment"; R14 introduced a Linux-Docker **poller**. Whether the full application runs on Linux is not established. | "Nlyte v16 advertises Linux-Docker deployment options (scope unverified); the VA TRM still lists Windows Server/IIS/SQL Server." The Windows-installer rejection stands on support-burden grounds alone. |
| C11 | D18: "EMF-heavy masters (most Cisco)". | The digest says EMF blobs "constitute most Visio VSS shapes" generally; the Cisco attribution was inference. | "EMF-heavy masters (most binary .vss shapes in general)". |
| C12 | D25: SCIM presented as a common free-tier norm on the strength of Zabbix. | Zabbix documents SCIM in 7.4 with introduction version UNVERIFIED; Grafana and GitLab charge for it. | "SCIM is free in at least one comparable (Zabbix) and paid in two (Grafana, GitLab); UnumDCIM chooses free as a deliberate differentiator, not as an industry norm." |
| C13 | Executive summary/D01: "installs beside an incumbent in one hour". | A target with no evidence. | Labeled as a Phase 1 exit criterion (already in the roadmap), not a capability claim. |
| C14 | D14: OGrEE-3D cited as a reference codebase without caveat. | The digest notes OGrEE-3D depends on the paid TriLib 2 asset, which limits reuse of its import pipeline even as reference. | Caveat added; OGrEE-3D is reference-only for scene organization, never for its importer. |
| C15 | D08/digest: Icecat "content may only be used to promote the brand owner's products". | The OPL 1.4 text fetched on 2026-09-08 (https://iceclog.com/open-content-license/) contains the ML clause verbatim ("strictly conditional upon the data NOT being utilized for machine learning training, algorithmic model generation, or automated synthetic content creation"), the "no fee for the OIC itself" clause, the database-right notice and the 1M/month fair-use cap, but the fetched text does **not** contain a "promotion-only" purpose clause; that restriction was attributed to the Fair Use Policy in the digest and is **UNVERIFIED verbatim**. | Counsel question narrowed: does the Fair Use Policy (not the OPL) restrict purpose to product promotion, and does internal DCIM inventory use fall inside it? See D45. |

---

## A.2 New decisions

### Phase 0 additions

#### D32. Nlyte API validation gate (Phase 0 exit criterion)

**Why it matters.** Goal (d) rests on an API whose OData version, `$metadata` exposure, write verbs, `$top` defaults, session lifetime, rate limits, auth modes beyond Basic, entity-set stability across v14/15/16, connection/power-path/floor-plan entities, and licensing of the `/integration/api/odata` endpoint are all unknown. Nlyte publishes no API docs (https://www.nlyte.com/support/customer-support/); the only public client is 2019-era FlowGate; the github.com/nlyte account is an individual user with two forks, not Nlyte Software (https://github.com/nlyte). The NgageAPI datasheet URL returned 404 on 2026-09-08, so even the vendor's write assertion is now unreachable.

**Options.**
- *A. Build the connector and discover at the first customer.* Objection: Phase 1 exit criterion becomes unreachable if any assumption fails.
- *B. Formal Phase 0 probe against a design partner's licensed instance, producing a written capability record and a supported-version matrix, plus a mock server from FlowGate fixtures for CI (recommended).* Objection: requires a design partner before Phase 0 ends.
- *C. Wait for a partner-program response.* Objection: contact-us only; assume zero cooperation.

**Recommendation.** Option B. The probe records, per Nlyte instance: (1) OData version from the `OData-Version` header and `$metadata` if present, else per-entity-set `$top=1` samples with inferred types; (2) auth modes (Basic login endpoint; whether OIDC/SAML-fronted sessions block API use); (3) session TTL from `Set-Cookie max-age`; (4) default page size and whether `$top`/`$skip`/`$count` are honored; (5) throughput at concurrency 1/2/4 with server-side CPU observed by the customer; (6) the full entity-set list and diff against the FlowGate list; (7) presence or absence of connection, power-path, panel, breaker, network-port and floor-plan entities; (8) custom-field typing; (9) any write verb accepted on a throwaway test asset in the customer's staging instance, if one exists; (10) written confirmation from the customer that their Nlyte contract permits third-party API and database access. Supported matrix: Nlyte v15.0.x and v16.0.x (VA TRM shows v14 divesting in 2026, https://www.oit.va.gov/services/trm/ToolPage.aspx?tid=16487); v14 best-effort. A Nlyte OData mock (Python, from FlowGate model classes, BSD-2 attribution) runs in CI.

**Depends on:** D21, D31 (design partners). **Door:** two-way. **Would change it:** Nlyte publishing API terms.

#### D33. Nlyte chain topology and floor geometry: sourcing fallbacks and revised ownership defaults

**Why it matters.** C1 and C3: Nlyte holds power/network chains and Floor Planner rooms (`HasFLoorPlannerRoom`, https://raw.githubusercontent.com/vmware-archive/flowgate/master/nlyte-worker/src/main/java/com/vmware/flowgate/nlyteworker/scheduler/job/common/HandleAssetUtil.java) but none of it is evidenced in OData. The draft's default "UnumDCIM owns upstream power chain" collides with a chain Nlyte already models.

**Options.**
- *A. Overlays limited to outlet readings until topology is evidenced.* Objection: weak Phase 1 demo for Nlyte shops.
- *B. Source chain topology and floor coordinates from the read-only SQL data-warehouse reader (sanctioned customer pattern, https://nlyte.com/web/wp-content/uploads/2026/02/Reporting-against-the-Data-Warehouse-and-Nlyte-Database_Remote.pdf).* Objection: on-prem only; DBA approval; schema undocumented publicly.
- *C. Re-enter the chain in UnumDCIM.* Objection: two masters of one chain unless a reconciliation rule exists.

**Recommendation.** Decide per customer at the Phase 0 probe, in order A, then B, then C. Revised ownership defaults for Nlyte shops: if Nlyte exposes the chain (via OData or SQL), **Nlyte owns the chain segments it models** (feeds to rack PDU, and any upstream elements present) and UnumDCIM owns only segments Nlyte lacks (cooling loops, metric geometry, sensors, art), with shared segments reconciled through the discrepancy queue; if Nlyte does not expose it, UnumDCIM owns the chain and the Nlyte record is treated as a non-authoritative mirror. Floor coordinates: if Floor Planner geometry is readable, it seeds grid calibration (D13); otherwise GridReference plus calibration.

**Depends on:** D12, D32. **Door:** two-way.

#### D34. Backend non-functional requirements and synthetic estate

**Why it matters.** The twin has budgets; the data layer has none. NetBox's cable-path tracing and rack elevation rendering have known scale costs; RFPs ask for sizing.

**Options.**
- *A. Define NFRs per deployment size class and validate with a synthetic-estate generator in CI (recommended).* Objection: numbers chosen before real estates exist.
- *B. Defer to first customer.* Objection: architecture choices (RLS, ltree, partitioning) are one-way and must be sized now.

**Recommendation.** Size classes: **S** (1 site, 500 racks, 10k devices), **M** (10 sites, 5k racks, 100k devices, 1M ports), **L** (50 sites, 20k racks, 500k devices, 5M ports, 200k cables). Targets on the reference install for M, and on a documented 3-node Helm install for L: p95 list-endpoint latency < 300 ms at page size 100; p95 object detail < 150 ms; rack elevation render < 200 ms; power-path trace (outlet to source) < 1 s and cable circuit trace < 1 s at L; capacity rollup per site < 5 s; concurrent interactive users 200 (M) / 1,000 (L); sync freshness: Nlyte lag ≤ 1 poll interval, NetBox webhook-driven lag < 60 s; Phase 0 spike proves S and M; Phase 1 exit proves L. The synthetic generator (`unum synth --class L --seed N`) produces realistic vendor mix from the CC0 library and is run nightly.

**Depends on:** D09, D10, D11. **Door:** two-way. **Would change it:** design-partner estates above class L.

#### D35. Browser support matrix and minimum hardware

**Why it matters.** D14 left the matrix undefined; enterprise NOCs run locked-down Edge/Chrome in VDI without GPU acceleration.

**Recommendation.** Supported: Chrome, Edge and Firefox, current and two prior major versions; Safari current and one prior; WebGL2 required, WebGPU optional and auto-detected (three.js WebGPURenderer falls back to WebGL2, https://github.com/mrdoob/three.js/blob/dev/src/renderers/webgpu/WebGPURenderer.js). Quality presets: **Full** (dedicated GPU), **Standard** (Intel/AMD iGPU, the Phase 0 gate), **VDI/Software** (SwiftShader/ANGLE software rendering: instanced boxes only, no shadows, LOD forced to tier 2, 2D plan mode default, 5k-rack cap per view with pagination by room). The Phase 0 spike adds a software-rendering run in headless Chrome with `--disable-gpu` and a Citrix/AVD test with a design partner. Minimum: 8 GB RAM, 1080p; mobile Safari supported for the technician PWA only (2D and inspector, no 3D), given canvas memory caps (https://konvajs.org/docs/performance/All_Performance_Tips.html).

**Depends on:** D14. **Door:** two-way.

#### D36. Internationalization and units from Phase 1

**Why it matters.** The draft deferred i18n to Phase 3 although the enterprise-architecture digest recommends translations from v1 (NetBox 4.0 shipped eight languages, https://netboxlabs.com/docs/netbox/release-notes/version-4.0/); Nlyte and FNT customers include German-speaking estates; unit localization (in/ft/BTU vs mm/kW) was never mentioned.

**Recommendation.** Phase 1: every UI string externalized (Django `gettext`, react-intl ICU messages), RTL-safe layouts, locale-aware number/date formatting, and a unit-preference layer that stores metric internally (mm, kg, W, °C, L) and renders per user/tenant preference (imperial length/weight, BTU/hr, °F, gallons). Phase 2: community translations (German, French, Spanish, Japanese first) via Weblate or similar; API always metric with explicit unit fields.

**Depends on:** D09, D15. **Door:** one-way for the metric-storage rule.

#### D37. Product usage analytics and community success metrics

**Why it matters.** The draft rejects phone-home but the founder's funnel question (NetBox vs Nlyte) needs evidence.

**Recommendation.** Opt-in, anonymized, documented ping (install id hash, version, deployment mode, site/rack/device counts bucketed, enabled connectors, twin quality preset) sent at most weekly; off by default in air-gap builds; the exact payload shown in the UI before consent; no tenant data ever. Public metrics dashboard: installs (from opt-in pings and container pulls), active sites, library PRs merged upstream, connector coverage, discrepancy-queue median size, time-to-first-render at design partners. These are the KPIs for phase gates alongside module-retirement counts.

**Depends on:** D26. **Door:** two-way.

#### D38. Staffing, budget assumptions and channel/partner program

**Why it matters.** Feasibility of Phase 1 (twin + library + sync + security baseline in seven months) cannot be judged without team size; DCIM is largely sold and implemented through integrators, and Nlyte, Sunbird and FNT all run partner programs.

**Recommendation.** Assumed core team: Phase 0 six FTE (2 Django/data, 2 three.js/React, 1 pipeline/library, 1 DCIM domain/product who has run Nlyte or dcTrack); Phase 1 nine FTE (adds 1 sync/connectors, 1 security/DevOps, 1 technical writer/community); Phase 2 twelve FTE (adds 1 telemetry, 1 QA/automation, 1 solutions engineer); Phase 3 fifteen FTE. Critical-path skills: three.js at scale, Django at scale, DCIM domain. Partner program launches in Phase 2: SI partners certified on the migration playbook (D21b) and connector development, with a revenue share on Supported/Enterprise subscriptions and a public partner directory. If the team is smaller than six in Phase 0, the roadmap stretches by the ratio and the Nlyte Collector is deferred behind the NetBox funnel.

**Depends on:** D07. **Door:** two-way.

### Phase 1 additions

#### D21b. Nlyte migration and cutover playbook

**Why it matters.** Uptime attributes DCIM failure to data-entry errors and integration effort (https://journal.uptimeinstitute.com/dcim-past-and-present-whats-changed/); "Nlyte as downstream mirror" is undefined operationally; records-retention obligations attach to Nlyte's change history.

**Options.**
- *A. Ad hoc per customer.* Objection: every migration re-learns the same lessons; no paid service can be priced.
- *B. Staged playbook with numeric acceptance thresholds, dual-run and rollback, packaged as a paid migration service (recommended).* Objection: rigid for small sites; provide a "lite" track.

**Recommendation.** Option B, stages:
1. **Shadow** (read-only): full snapshot, crosswalk, matching report. Acceptance: ≥ 98% of active assets matched at confidence ≥ 0.9 (D46), ≤ 0.5% unresolved discrepancies after triage, zero unmapped enumerations.
2. **Promote per entity type per site**, in fixed order: geometry and art (always UnumDCIM), sensors, cooling chain, upstream power chain, then rack placement, then assets, then materials, then lifecycle/status, then workflow. Each promotion reversible (D39).
3. **Dual-run** for at least two Nlyte poll cycles per promoted type with a daily reconciliation report (field-level diff counts, trend); cutover criterion per site: three consecutive days with zero owner-field discrepancies and all open ChangeRequests executed in both systems.
4. **History migration**: Nlyte data-warehouse readings and change history imported into the telemetry store and an immutable `ImportedAuditRecord` table with provenance and original timestamps, so retention obligations follow the data; scope agreed in writing per customer.
5. **Cutover**: Nlyte becomes downstream mirror (export path, D21) or is retired; renewal-cycle alignment recorded as a project milestone; user retraining via role-based tutorials.
6. **Rollback**: re-demotion (D39) plus restore from the pre-cutover site bundle (D44).
Deliverables of the paid service: matching report, ownership plan, reconciliation dashboard, history archive, sign-off document.

**Depends on:** D12, D21, D39, D44. **Door:** two-way.

#### D39. Ownership demotion and the guaranteed exit path

**Why it matters.** Reversibility was asserted but not mechanized; irreversible promotion is lock-in and contradicts the open positioning.

**Recommendation.** Demotion of an entity type is permitted only where a verified write-back path exists for the target system (API write validated per D47, or an admin-loaded export whose format was validated with that customer). Otherwise the UI blocks demotion and offers "export for admin load" with a warning that the customer's Nlyte/NetBox admin must apply it. The universal exit is the full-fidelity site bundle (D44), producible at any time by any admin, with importers documented for NetBox (YAML/JSON bulk), openDCIM (XSD templates) and CSV. Demotion is logged as a ChangeRequest with the values handed back, so the audit trail shows exactly what left the system.

**Depends on:** D12, D44, D47. **Door:** one-way (the guarantee).

#### D40. Default OwnershipPolicy for NetBox coexistence

**Why it matters.** NetBox is the larger funnel; unclear ownership reproduces the split-brain the judges caught for Nlyte, and careless writes into community NetBox instances would damage reputation.

**Recommendation.** Published default table, editable per tenant:

| Entity/field group | Owner in NetBox mode | Write path |
|---|---|---|
| Sites, Locations (hierarchy), Tenants, Tags, Custom fields | NetBox | none from UnumDCIM by default |
| Racks (identity, U height, RackType), Devices (identity, DeviceType, serial, asset tag, status, role), U position and face | NetBox | placement intents flow to NetBox as REST writes only if write-back is enabled |
| Cables, terminations, front/rear port mappings, circuits, IPAM/VLAN/VRF | NetBox | none |
| Power panels, feeds, ports, outlets (NetBox vocabulary subset) | NetBox | none |
| Upstream power chain (PowerSource, PowerNode, breakers), cooling loops beyond NetBox 4.7 cooling objects, sensors | UnumDCIM | none (NetBox lacks the fields) |
| NetBox 4.7 cooling objects | NetBox if present, else UnumDCIM | optional write-back |
| Metric geometry, art, templates, scenarios, overlays, ExternalReference | UnumDCIM | none |
| Device types (library records) | UnumDCIM library, NetBox instance copies | NetBox bulk import via versioned mapper, opt-in |

Rules: write-back is opt-in per tenant, starts in dry-run mode showing a field-level diff, uses ETag/If-Match and `changelog_message="UnumDCIM: <intent id>"` (https://netboxlabs.com/docs/netbox/integrations/rest-api/), never touches objects the tenant marked read-only, and is limited to the fields UnumDCIM owns or to confirmed placement intents. Event-rule webhooks (https://netboxlabs.com/docs/netbox/features/event-rules/) are the change-capture path; polling by `last_updated` is the fallback.

**Depends on:** D12, D22. **Door:** two-way.

#### D41. Bulk import at scale

**Why it matters.** All-or-none bulk on 500k rows is impractical; the first impression beside a large estate is the initial load.

**Options.**
- *A. NetBox-style all-or-none REST bulk only.* Objection: fails at class M/L.
- *B. Staged import pipeline with chunked transactions, idempotent upserts, dry-run and resumability (recommended).* Objection: more machinery; two code paths (REST bulk for small, staged for large).

**Recommendation.** Option B. Staging tables per entity (`import_batch`, `import_row` with raw payload, normalized payload, status, error); chunked transactions of 1,000 rows; idempotency key = (tenant, source system, entity set, native id) via ExternalReference, with content hash to skip unchanged rows; dry-run produces a diff summary (creates/updates/conflicts) before commit; resumable by batch id; per-row error report downloadable as CSV; dedupe rules applied in a fixed order (external id, serial, asset number, name+rack+U). Throughput target: 100k assets/hour on the reference install, validated in Phase 1 against the class-L synthetic estate (D34). REST bulk (all-or-none) remains for ≤ 1,000 objects per call.

**Depends on:** D11, D12, D34. **Door:** two-way.

#### D42. Intra-UnumDCIM concurrent editing

**Why it matters.** The draft cites the games' co-op sync bugs as the failure class but sets no policy for two planners on one floor.

**Options.**
- *A. Last-writer-wins.* Objection: silent overwrites.
- *B. Server-authoritative per-object optimistic concurrency with version tokens on ChangeRequest intents, soft edit-locks with presence, conflict UI reusing the discrepancy-queue component (recommended).* Objection: lock UX overhead.
- *C. CRDT scene state.* Objection: unnecessary complexity for placement semantics that must serialize through intents anyway; rejected for v1.

**Recommendation.** Option B. Every object carries a `version` (monotonic); the twin submits intents with the observed version; the server rejects stale intents with a 409 carrying the current state; the client shows a merge dialog (keep mine / take theirs / open discrepancy). Soft locks: a planner "claims" a room or rack for editing (TTL 10 minutes, renewed on activity, visible as a presence badge); claims are advisory and can be overridden by a role with a logged reason. WebSocket/SSE feed broadcasts version bumps so ghosts and badges update live.

**Depends on:** D12, D23. **Door:** two-way.

#### D43. Capacity computation model

**Why it matters.** Capacity numbers are what buyers compare against dcTrack/Nlyte; a game-derived pull evaluator is not a capacity policy an engineer will trust.

**Recommendation.** Every capacity-bearing object carries a triplet: **rated** (nameplate/design), **allocated** (sum of downstream budgeted values), **measured** (latest telemetry or manual reading). Budgeted device power = derated nameplate (`typical_power_w` if known, else `max_power_w × site diversity factor`, default 0.7, configurable per device class), matching the dcTrack budgeted/measured convention and NetBox `max_utilization` (https://netboxlabs.com/docs/netbox/features/power-tracking/). Breaker continuous-load derating default 80% (configurable, since jurisdictions differ). Redundancy policies per site or per chain: N, N+1, 2N, A/B; A/B availability = each path must carry 100% of allocated load under the loss of the other. Cooling: rated kW per unit × configurable aging derating (dcTrack 9.1 precedent) versus allocated heat (W × 3.412 BTU/hr with confidence). Floor load: rated kg/m² per tile or zone versus rack weight (RackType max weight, device weights). Space: U, half-width lanes, zero-U side positions. Formulas are documented in-product with a "show the math" panel per object. Comparison tests: NetBox 4.7 feed utilization fixture and a dcTrack export from a design partner.

**Depends on:** D11, D29. **Door:** two-way.

#### D44. Full-fidelity site/tenant export bundle

**Why it matters.** Exit path (anti-lock-in), demo/seed mechanism, backup of last resort, instance migration, and the basis for demotion.

**Recommendation.** `unumdcim-site` bundle: a ZIP with `manifest.json` (schema version, producer version, tenant, checksums, license manifest), newline-delimited JSON per entity type in dependency order, telemetry as Parquet (optional), asset sidecar files with per-file SPDX ids, and an attribution manifest. Loaders are forward-compatible within a major and guaranteed for every LTS; CI round-trips the NetBox 4.7 fixture and the class-M synthetic estate on every commit. NetBox YAML/JSON and openDCIM XSD exports are derived views of the bundle.

**Depends on:** D11, D27. **Door:** one-way (the guarantee).

#### D45. Icecat scope and AI/ML segregation

**Why it matters.** The OPL 1.4 ML clause is verbatim: permission is "strictly conditional upon the data NOT being utilized for machine learning training, algorithmic model generation, or automated synthetic content creation" (https://iceclog.com/open-content-license/); the promotion-only purpose limit attributed to the Fair Use Policy is UNVERIFIED verbatim (C15). An LLM feature that reads tenant records containing Icecat-derived fields could void the license for that customer.

**Options.**
- *A. Ship the connector, ignore purpose scope.* Objection: possible breach.
- *B. Counsel opinion first; connector ships only for uses inside the opinion; Icecat-derived fields carry a license id and are filtered from all AI/ML paths by default (recommended).* Objection: reduces Icecat's value.
- *C. Drop Icecat.* Objection: loses the only free structured spec source for HP/Dell/Lenovo/APC/Vertiv.

**Recommendation.** Option B. Field-level `license_id = "Icecat-OPL-1.4"`; all NL-query, anomaly-detection, placement-optimization and measured-profile-learning features exclude such fields unless the tenant supplies its own commercial Icecat agreement; the recipe records the registration requirement and the 1M/month cap; if counsel finds internal DCIM use outside scope, the connector degrades to storing datasheet URLs only.

**Depends on:** D08, D17, D19. **Door:** two-way.

#### D46. Sync engine parameters

**Why it matters.** These parameters set the discrepancy queue's signal-to-noise; unspecified, the first design partner sees thousands of false discrepancies.

**Recommendation.**
- **Hash field lists** per entity, excluding volatile fields: for Nlyte assets exclude `AuditDate`, `AuditStatusCorrect`, `LastAuditorAccountID`, `PowerState`, all realtime values, and `@odata.*` annotations; for NetBox exclude `last_updated`, `display`, counts.
- **Matching score**: exact serial 1.0; asset number/asset tag 0.9; RFID tag 0.9; manufacturer+model+name in same rack 0.8; name+rack+U 0.7; name only 0.5. Auto-link ≥ 0.9; review queue 0.7-0.89; below 0.7 create-as-new with a "possible duplicate" flag.
- **Confidence enum** for derived attributes: `measured` (telemetry), `vendor` (vendor tool or spec sheet), `estimated` (derived or community); shown as a badge and propagated through capacity math.
- **Polling defaults**: delta probe every 15 minutes where a modified-date filter exists; otherwise incremental per-entity-set pulls hourly for small sets (LocationGroups, Materials, Cabinets) and a full snapshot nightly in a configurable window; realtime values every 5 minutes; concurrency 2, backoff on 5xx/429.
- **Volatile drift suppression**: a discrepancy must persist across two snapshots before surfacing.

**Depends on:** D12, D21. **Door:** two-way.

#### D47. Write-back safety protocol (Nlyte, NetBox, ServiceNow)

**Why it matters.** No vendor sandbox exists; a bad write corrupts a production system of record; Nlyte 16.0.300 shows connector churn (https://www.nlyte.com/news/nlyte-16-0-300-release-enhancements-integrations-and-fixes/).

**Recommendation.** Any write path is enabled only after: (1) validation against the customer's staging instance or, absent one, a read-only rehearsal producing a field-level diff; (2) dry-run preview approved by a named admin; (3) canary batch (≤ 10 objects) with read-back verification; (4) rate limit (default 60 writes/minute) and a kill switch; (5) automatic pause on any unexpected response shape or on schema drift detected by the version probe; (6) per-tenant feature flag and complete audit trail. Rollback: compensating intents generated from the pre-write snapshot.

**Depends on:** D21, D40. **Door:** two-way.

#### D48. Rack U-slot occupancy edge cases

**Why it matters.** Blade chassis, zero-U PDUs and half-width devices are what evaluators try first.

**Recommendation.** Occupancy model per rack: a bitmap indexed by (face: front/rear, lane: full/left/right, U in 0.5 steps from `starting_unit`, honoring `desc_units`) plus zero-U side positions (left/right, front/rear, ordered) and chassis-slot sub-grids for parent/child devices (NetBox `subdevice_role`, device bays). U pitch from RackType (44.45 mm EIA; 48 mm OCP OpenU, https://en.wikipedia.org/wiki/Open_Rack); `is_full_depth=false` allows front/rear pairing in the same U; the "nearest free U-range" search respects lane and face. Phase 1 exit test suite includes 0.5U devices, descending racks, zero-U PDUs, half-width pairs, blade chassis with populated bays, mixed-pitch rooms.

**Depends on:** D11, D15. **Door:** two-way.

#### D49. Cabling phase sequencing correction

**Why it matters.** Phase 1 promised network-path overlays while patch panels and circuit trace arrived in Phase 3; every estate has patch panels, so Phase 1 traces would be wrong.

**Recommendation.** Move front/rear pass-through ports with port-mappings (NetBox 4.5 vocabulary) and basic end-to-end circuit trace into Phase 1; keep cassettes/enclosures, three-phase balance color coding and DC circuits in Phase 3. The trace algorithm is a port of NetBox's cable-path resolution (Apache-2.0).

**Depends on:** D03, D11. **Door:** two-way.

#### D50. Data model additions (table-stakes objects)

**Why it matters.** Phase 3 promises native system of record and colo portals; without these objects the ratchet cannot absorb Nlyte's purchasing/warranty/parts fields or colo contracts.

**Recommendation.** Add to D11: `Row` and `Aisle` (with hot/cold designation) and `Containment` (aisle containment polygon, type); `FloorTile` with load rating and raised-floor/plenum flags; `Contract`, `Warranty`, `SupportEntitlement` (vendor, level, start/end, linked assets); `Part`/`Spare` with `StockLocation` and quantity; `ReceivingRecord` (PO, delivery date, condition, staged location); `CablePathway` (tray/conduit segments with length and fill); `TenantAllocation` (contracted kW, U/space, ports, per tenant per site) for colo. No-code custom object types ship in core in Phase 2 (typed fields, relations, list/detail views, REST/GraphQL), neutralizing NLUL Custom Objects; GLPI 11 ships custom assets natively (https://raw.githubusercontent.com/glpi-project/glpi/main/composer.json).

**Depends on:** D11. **Door:** two-way (fields), one-way (custom-object substrate).

### Phase 2 additions

#### D51. Agentless discovery

**Why it matters.** Discovery attacks the data-entry-error failure mode and is sold separately by NetBox Labs, Hyperview and Device42.

**Options.**
- *A. None.* Objection: onboarding remains manual.
- *B. Read-only discovery via the collector producing "discovered" staging records reconciled through the discrepancy queue (recommended).* Objection: false positives from unmanaged devices.
- *C. Agent-based.* Objection: excluded; enterprises resist agents on infrastructure devices.

**Recommendation.** Option B in Phase 2: Redfish (system, chassis, PSU, PowerDistribution), SNMP sysDescr/ENTITY-MIB/LLDP-MIB, vSphere via pyVmomi (Apache-2.0), later Kubernetes nodes via the operator; discovered records are never auto-promoted; matching uses D46 scores; an "unclaimed devices" view drives onboarding.

**Depends on:** D28, D46. **Door:** two-way.

#### D52. Alarm engine, collector resilience, polling and retention tiers

**Why it matters.** Phase 2's exit criterion is running alarming instead of NEO/Power IQ; those products are judged on exactly these behaviors.

**Recommendation.**
- **Rule model**: threshold (static, per-asset override or per-class), derivative (rate of change), absence (no reading in N intervals), composite (AND/OR across metrics on one asset); severities info/warning/critical; hysteresis and minimum duration to suppress flapping; dedup by (asset, metric, rule).
- **Lifecycle**: raised, acknowledged (by user, with note), escalated (timed, to next channel/group), cleared, closed; maintenance windows attached to ChangeRequests or scheduled per site/rack suppress raising but record "suppressed" events.
- **Channels**: email, SMS (via provider plugin), generic webhook (HMAC), Slack/Teams/PagerDuty adapters, SNMP trap forwarder; alarm-to-asset mapping through ExternalReference so twin badges light up.
- **Collector resilience**: Telegraf `outputs.http` with disk buffering (`buffer_strategy = "disk"`), active/standby collectors with a heartbeat rule; clock sync required (NTP/PTP), readings carry collector and server timestamps.
- **Polling tiers**: 1 minute (critical PDUs/UPS), 5 minutes (default), 15 minutes (environmental); retention: raw 90 days, 5-minute rollups 2 years, hourly rollups 7 years (configurable); downsampling jobs in `unum-monitor`.
- **ClickHouse switch-over**: recommended when > 50k active series or sustained > 5k writes/s, or when raw retention beyond 90 days is required at class L.

**Depends on:** D10, D28. **Door:** two-way.

#### D53. Declarative validation and business-rules engine

**Why it matters.** dcTrack Smart Models and business rules, Nautobot's Data Validation Engine and NetBox media validation are table-stakes hygiene; the ratchet must not promote dirty data.

**Recommendation.** Phase 2: rule types regex, min/max, required-if, uniqueness scope, relationship constraints (e.g., device class X only in rack type Y; max kW per row; mandatory dual PSU on A/B feeds), evaluated on intents before execution and on import into staging; violations block or warn per rule; rules are exportable YAML. Design ported from nautobot-app-data-validation-engine (Apache Software License 2.0, Copyright (c) 2025 Network to Code, LLC, https://raw.githubusercontent.com/nautobot/nautobot-app-data-validation-engine/develop/LICENSE).

**Depends on:** D11, D30. **Door:** two-way.

#### D54. Reporting, dashboards and drawing export

**Why it matters.** Table-stakes item 9; facilities teams hand drawings to contractors and auditors, which a three.js scene does not print natively.

**Recommendation.** Free tier (Phase 2): saved filtered tables with CSV/Excel export, prebuilt reports (capacity by site/room/row, stranded power, PUE trend, EOL/warranty expiries, audit variance), scheduled report emails, Grafana dashboard JSON for customers who run Grafana, read-only SQL views and OData feed. Drawing export: plan view and one-line diagrams rendered server-side to SVG/PDF from the same scene data (not screenshots), DXF via ezdxf (MIT) with layers per object class, rack elevations to PDF/SVG. Executive multi-site dashboards and forecasting remain in `ee/` (D05).

**Depends on:** D23, D13. **Door:** two-way.

#### D55. Sustainability metrics standard and EU EED reporting

**Why it matters.** Commission Delegated Regulation (EU) 2024/1364 requires data centres with "an installed information technology power demand of at least 500 kW" to report by "15 May 2025, and every year thereafter" (first deadline 15 September 2024), with PUE per "CEN/CENELEC EN 50600-4-2 standard or equivalent", plus installed IT power demand, total and computer-room floor area, total and IT energy consumption (backup generator separately), cooling and electrical redundancy levels, waste-heat use, water use and renewable share (https://eur-lex.europa.eu/eli/reg_del/2024/1364/oj). PUE is standardized as ISO/IEC 30134-2:2016 with EN 50600-4-2 as the European counterpart (https://en.wikipedia.org/wiki/Power_usage_effectiveness); Nlyte v16 markets EED alignment.

**Recommendation.** Model metering points and measurement boundaries per EN 50600-4-2 / ISO/IEC 30134-2 (PUE categories 1-3 by meter location), WUE (ISO/IEC 30134-9, UNVERIFIED part number) and CUE with carbon-intensity sources (grid factors or OpenDC-STEAM traces where licensed); add to D11 a `MeteringPoint` (boundary role, source series) and `FacilityMetrics` period rollups. Phase 3 ships the EU EED Annex I/II reporting template with the fields listed above and a validation checklist; the same metering-point model produces PUE overlays in Phase 2.

**Depends on:** D11, D28. **Door:** two-way.

#### D56. Thermal-estimate validation gate and OpenDC scope

**Why it matters.** Over-claiming physics is risk 6; the heat-diffusion heuristic is game-derived; OpenDC's workload synthesis was unspecified and InlineWorkload capabilities are unknown.

**Recommendation.**
- **Estimate tier gate**: ships visible by default only after validation at ≥ 2 design partners with rack-inlet temperature MAE ≤ 2 °C on ≥ 80% of sensored racks over 7 days; otherwise hidden behind a "lab" flag labeled "unvalidated heuristic". Validation set and metric are documented in-product.
- **OpenDC scope (Phase 2)**: three supported questions only: (1) annual energy and carbon by hall under a given utilization profile; (2) host-consolidation what-if (retire/replace N hosts); (3) availability under a named failure prefab. Workload input: user-authored utilization profiles per device class rendered as inline tasks/fragments, plus optional replay of measured CPU utilization from `unum-monitor` when available; canonical public traces only for demos. Gate: OpenDC power MAPE ≤ 10% against measured PDU power over 7 days at one design partner before results are labeled "forecast" (OpenDT reports 4.39% after calibration, https://arxiv.org/html/2604.11445). Explicitly out of scope: PDU/UPS/cooling simulation via OpenDC.

**Depends on:** D29. **Door:** two-way.

#### D57. Offline entitlement, metering units and the per-cabinet trigger

**Why it matters.** `ee/` features need an entitlement mechanism that does not contradict no-phone-home; "site" was undefined; quoting is impossible without units.

**Recommendation.** Signed offline license files (Ed25519, JSON payload: organization, tier, site and cabinet caps, features, expiry, grace 30 days) verified locally; no telemetry; expired licenses degrade `ee/` features to read-only, never block the core. Definitions: **site** = a Location of type building/campus with ≥ 1 rack; **cabinet** = a rack with ≥ 1 mounted device; **monitored node** = a device with ≥ 1 active polling target. Supported tier priced per site; Cloud and Enterprise move to per-cabinet when the first five paying Cloud customers exist or when a single customer exceeds 2,000 cabinets, whichever is first; the per-cabinet list price is set below the dcTrack anchor of $19.50/cabinet/month (https://www.sunbirddcim.com/pricing).

**Depends on:** D05, D07. **Door:** two-way.

#### D58. Service boundaries, inter-service auth, BI access under RLS, version skew

**Why it matters.** Shared-database microservices are the distributed-monolith trap; SQL views bypass RLS unless designed for it; on-prem collectors and a Cloud core will skew.

**Recommendation.** `unum-core` and `unum-sync` are one modular monolith (one Django project, one database, sync as an app with its own workers). `unum-monitor` is a separate service with its own schema/store, calling core over REST with OAuth2 client credentials (service accounts, scoped tokens). Collectors authenticate with per-collector tokens bound to a tenant and a site. BI: PostgreSQL row-level security applies to tables; "Table owners normally bypass row security" and superusers/`BYPASSRLS` roles always bypass (https://www.postgresql.org/docs/current/ddl-rowsecurity.html), so BI views are exposed only through per-tenant database roles that are not table owners, with `FORCE ROW LEVEL SECURITY` on all tenant tables, and the OData feed runs through the application layer. Compatibility guarantee: collector and core N-1 (a collector one minor behind core keeps working); protocol versioned in the OTLP resource attributes.

**Depends on:** D09, D10, D25. **Door:** one-way for the monolith split; two-way for the rest.

#### D25b. Secrets and device-credential management; control-action approvals

**Why it matters.** A DCIM stores thousands of SNMPv3 keys, Modbus/BACnet endpoints, Redfish/IPMI passwords, integration API credentials and, in Phase 3, outlet-control and door-lock credentials; FIPS/FedRAMP reviews fail without key management.

**Options.**
- *A. Django field encryption with a single key.* Objection: no rotation, no HSM/KMS, no scoping.
- *B. Envelope encryption with a pluggable KMS backend, collector-scoped delivery, rotation workflow, FIPS-validated crypto, approval gates on control actions (recommended).* Objection: more moving parts.

**Recommendation.** Option B. Data keys per tenant wrapped by a master key from a backend: local key file (reference install), OpenBao (MPL-2.0, https://raw.githubusercontent.com/openbao/openbao/main/LICENSE) or HashiCorp Vault (BSL 1.1, licensor IBM, additional use grant bars competing hosted/embedded offerings, https://raw.githubusercontent.com/hashicorp/vault/main/LICENSE; supported as a customer-provided backend, never bundled), AWS KMS/Azure Key Vault/GCP KMS for Cloud. Credentials are delivered to collectors as short-lived, site-scoped leases; rotation is a workflow that re-encrypts and re-leases; FIPS mode selects a validated OpenSSL provider for the Python stack (documented, not default). Control actions (outlet switch, door unlock, firmware push) require a ChangeRequest with approval by a second role, an execution window, and an immutable audit record; no control action is ever available through the community edition without approval configured.

**Depends on:** D25, D28. **Door:** one-way for envelope encryption; two-way for backends.

#### D26b. Backup, DR, retention and data residency

**Why it matters.** A system of record for physical infrastructure is consulted during outages; buyers test restore during POCs.

**Recommendation.** Targets: reference self-hosted RPO 24 h / RTO 4 h (scheduled `pg_dump` plus object-storage sync of asset packs and sidecars, Valkey treated as ephemeral except stream offsets, which are checkpointed to PostgreSQL); Supported tier RPO 15 min / RTO 2 h via WAL archiving with point-in-time recovery; Cloud RPO 15 min / RTO 1 h with cross-zone replicas and regional residency options (EU, US, UK, APAC) chosen at provisioning. Telemetry store backed up separately (ClickHouse backups or partition exports) with its own RPO (1 h). `unum backup` / `unum restore` CLI covers database, telemetry, object storage and license files; encrypted (age/GPG) off-site copies documented; a restore-verification job runs in CI monthly against the class-M estate; DR runbook shipped with the Supported tier.

**Depends on:** D26, D10. **Door:** two-way.

#### D59. Audit-log integrity and retention

**Why it matters.** Compliance buyers require tamper-evident trails and documented retention; the draft cites GDPR/FedRAMP without a policy.

**Recommendation.** Change log and audit events are append-only tables (no UPDATE/DELETE grants for application roles), hash-chained per tenant (each record stores the previous hash; a daily anchor is exported and optionally signed), with WORM export to object storage or SIEM. Retention configurable per class: audit ≥ 7 years default, change log same, telemetry per D52, imported Nlyte history per customer agreement. GDPR erasure: user identity fields pseudonymized (stable hash) rather than deleted, preserving chain integrity; documented in the privacy guide.

**Depends on:** D25. **Door:** one-way for append-only design.

#### D60. Air-gap workflow for sidecar assets, packs and verification

**Why it matters.** Fetch recipes, Sketchfab downloads, Icecat and Cisco EoX require internet; government and colo buyers test air-gap during POCs.

**Recommendation.** Sneakernet flow: on a connected workstation, `unum-ingest fetch --recipes ... --bundle out.utb` produces a signed transfer bundle (sidecar assets with license ids and acknowledgements, asset-pack deltas, connector caches such as EoX results); on the disconnected site, `unum-ingest import out.utb` verifies the Sigstore signature against a bundled public key and Rekor-less checkpoint (offline cosign verification documented in Phase 1), then loads. Monthly asset-pack deltas ship the same way. Geographic views: no online map tiles; ship a small vector world/country tile set (Natural Earth, public domain) or disable the map in air-gap builds.

**Depends on:** D17, D26. **Door:** two-way.

#### D61. Stencil, image and 3D-asset legal operations

**Why it matters.** CC0 cannot clear third-party rights; one DMCA notice or vendor complaint about automated scraping could force a pack recall. Live checks on 2026-09-08: VisioCafe states only "Each collection is copyrighted to its respective owner, and is not the property of VisioCafe" and "Copyright © VSD Grafx Inc. All Rights Reserved" with no terms on automated download or mirroring (https://www.visiocafe.com/); Juniper's icons-and-stencils page carries no license text at all, so Juniper's site-wide legal notice governs (https://www.juniper.net/us/en/products/icons-and-stencils.html, https://www.juniper.net/us/en/legal-notices.html); Cisco: "You may use them freely, but you may not alter them", downloads without login (https://www.cisco.com/c/en/us/about/brand-center/network-topology-icons.html); Sketchfab's general license page does not itself state CC attribution rules, which come from the individual CC deeds and Sketchfab's download-API terms (https://sketchfab.com/licenses; digest source for the "display license and author everywhere" rule).

**Recommendation.**
- **Contributor attestation**: every upload or PR asserts "own work" or "vendor permission attached"; PRs without attestation are auto-closed; the in-app "contribute this model" flow requires it before generating the CC0 PR.
- **Audit protocol for the 2,472 upstream images**: reverse-image search sample (100%) against vendor sites; images matching vendor renders are queried with the contributor; "unknown provenance = procedural fallback" in the shipped pack; results published as a per-image provenance table.
- **Takedown**: designated DMCA agent, 72-hour removal SLA, pack re-issue with a revoked-asset list that installed instances apply automatically.
- **Fetch policy**: recipes default to "open vendor page, user downloads, tool ingests" for VisioCafe, Juniper, Cisco and any site without explicit automated-access permission; automated fetch only where a documented API or terms allow (Icecat API, Sketchfab Download API with end-user login, Cisco EoX API).
- **Trademark/logo policy**: no vendor logos on procedural models; vendor names as text labels only; Cisco credit line rendered wherever Cisco product photos appear; no vendor marks in UnumDCIM marketing.
- **Attribution manifest**: every asset carries author/license/source; exports (PDF/SVG/bundles) embed an attribution appendix; an offline "About / Attributions" panel lists them; CC-BY-SA assets are quarantined to a share-alike-marked pack.

**Depends on:** D08, D17, D18. **Door:** two-way.

#### D62. Competitive threat to the NetBox funnel

**Why it matters.** Sunbird announced a NetBox connector (July 2026) and NetBox Labs sells Discovery, Assurance and Change Management, so incumbents can sit beside NetBox exactly as UnumDCIM proposes.

**Recommendation.** Differentiate the NetBox funnel on: Apache-2.0 adapters (theirs are proprietary), CC0 library contributions flowing back upstream, no per-cabinet fee for the twin, metric geometry and 3D that NetBox users cannot get elsewhere, and the schema-superset round-trip (device types with dimensions/power contributed upstream). Track Sunbird's connector scope quarterly; if NetBox Labs ships a facility/twin layer, the NetBox relationship becomes adversarial and the Nlyte/openDCIM/RackTables funnels take priority. Added to the risk register as risk 13.

**Depends on:** D01, D22. **Door:** two-way.

---

## A.3 Roadmap amendments

**Phase 0 exit criteria (additions):** Nlyte capability record and supported-version matrix from a design-partner instance (D32); Nlyte OData mock in CI; NFR targets met for classes S and M with the synthetic estate (D34); software-rendering and VDI run in the twin spike (D35); string externalization and metric-storage rule in place (D36); staffing plan approved (D38).

**Phase 1 (additions/changes):** pass-through ports and basic circuit trace (D49); U-slot edge-case suite (D48); staged import pipeline validated at class L (D41); concurrency versioning and soft locks (D42); capacity triplet and formulas (D43); site bundle format and CI round-trip (D44); NetBox OwnershipPolicy table with dry-run write-back (D40); Nlyte overlays scoped to outlet readings unless D33 finds chain topology; offline cosign verification docs and sneakernet bundle (D60); attribution manifest and contributor attestation (D61); envelope encryption with local-key backend (D25b); append-only audit tables (D59); opt-in analytics (D37). Removed from Phase 1: any claim of Nlyte-sourced power/network chains.

**Phase 2 (additions):** migration playbook and paid service (D21b); demotion mechanics (D39); discovery (D51); alarm engine and collector resilience (D52); validation engine (D53); free reporting set and drawing export (D54); metering points and PUE overlays (D55); OpenDC three-question scope with validation gate (D56); offline license files and metering units (D57); OpenBao/Vault/KMS backends (D25b); PITR backups (D26b); custom object types (D50); partner program (D38).

**Phase 3 (additions):** EU EED reporting template (D55); thermal-estimate tier promoted only after the D56 gate; colo TenantAllocation portal (D50); per-cabinet pricing per D57 trigger.

---

## A.4 Risk register additions

13. **Incumbents beside NetBox** (Sunbird connector, NetBox Labs Discovery/Assurance/Change Management). Mitigation: D62.
14. **Nlyte chain topology unreachable** via OData and SQL access refused by DBAs. Mitigation: D33 fallback C with documented reconciliation; Phase 1 demo scoped to outlet readings.
15. **Icecat purpose scope excludes DCIM use.** Mitigation: D45 counsel gate; connector degrades to URLs.
16. **RLS bypass through BI roles or owner connections.** Mitigation: D58 (non-owner roles, `FORCE ROW LEVEL SECURITY`, application-layer OData).
17. **Credential sprawl and control actions without approval.** Mitigation: D25b.
18. **Restore never tested.** Mitigation: D26b monthly CI restore job.
19. **Thermal heuristic shown as fact.** Mitigation: D56 gate and labeling.
20. **Vault BSL entanglement.** Vault is customer-provided only; OpenBao (MPL-2.0) is the documented open backend.

---

## A.5 Fact sheet additions (verified 2026-09-08)

- Cisco Support APIs (EoX, SN2Info): "If you are a Cisco Smart Net Total Care (SNTC) customer, you are entitled to access the Cisco Support APIs"; the same for Partner Support Services partners. https://developer.cisco.com/site/support-apis/
- Telegraf `xpath_protobuf` parser documents Sparkplug B decoding (`xpath_protobuf_files = ["sparkplug_b.proto"]`, `xpath_protobuf_type = "org.eclipse.tahu.protobuf.Payload"`); `mqtt_consumer` README itself does not mention Sparkplug. https://raw.githubusercontent.com/influxdata/telegraf/master/plugins/parsers/xpath/README.md, https://raw.githubusercontent.com/influxdata/telegraf/master/plugins/inputs/mqtt_consumer/README.md
- Icecat Open Content License 1.4 (2026-02-11): ML clause verbatim; "You may not charge a fee for the OIC itself"; fair use bars "more than 1 million data-sheet downloads per month"; notice "Database Right data-sheet [Year] Icecat. All rights reserved."; registration required. No promotion-only purpose clause found in the OPL text (that restriction, attributed to the Fair Use Policy, remains UNVERIFIED verbatim). https://iceclog.com/open-content-license/
- VisioCafe: "an independent non-profit web site"; "Each collection is copyrighted to its respective owner, and is not the property of VisioCafe"; "Copyright © VSD Grafx Inc. All Rights Reserved."; no stated terms on automated download, mirroring or bandwidth. https://www.visiocafe.com/
- Juniper icons-and-stencils page: ZIP downloads (ACX 49.1 MB, EX 77.4 MB, MX 70 MB, QFX 102.7 MB) with no license or terms text on the page. https://www.juniper.net/us/en/products/icons-and-stencils.html
- Cisco topology icons: "You may use them freely, but you may not alter them"; downloads without login. https://www.cisco.com/c/en/us/about/brand-center/network-topology-icons.html
- Commission Delegated Regulation (EU) 2024/1364: ≥ 500 kW installed IT power demand; reporting 15 September 2024 then 15 May 2025 and yearly; PUE per EN 50600-4-2 or equivalent; KPIs include installed IT power, total and computer-room floor area, total and IT energy (backup generator separately), cooling and electrical redundancy, waste heat, water, renewables. https://eur-lex.europa.eu/eli/reg_del/2024/1364/oj
- PUE standardized as ISO/IEC 30134-2:2016; EN 50600-4-2:2016 is the European counterpart. https://en.wikipedia.org/wiki/Power_usage_effectiveness
- PostgreSQL RLS: superusers and `BYPASSRLS` roles always bypass; table owners bypass unless `ALTER TABLE ... FORCE ROW LEVEL SECURITY`. https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- HashiCorp Vault: Business Source License 1.1, licensor IBM, additional use grant bars offering "on a hosted or embedded basis in order to compete with IBM Corp's paid version(s)", change to MPL 2.0 after four years. https://raw.githubusercontent.com/hashicorp/vault/main/LICENSE
- OpenBao: Mozilla Public License 2.0. https://raw.githubusercontent.com/openbao/openbao/main/LICENSE
- nautobot-app-data-validation-engine: Apache Software License 2.0, Copyright (c) 2025 Network to Code, LLC. https://raw.githubusercontent.com/nautobot/nautobot-app-data-validation-engine/develop/LICENSE
- Nlyte Asset Optimizer product page: "The open API allows additional custom integrations"; "import existing spreadsheets, barcode scans or discovery files"; tracks "power draw, available capacity and cooling needs at the device, rack and room levels"; Cooling Capacity Planner "maps your cooling infrastructure and highlights thermal conditions". https://www.nlyte.com/products/nlyte-asset-optimizer/
- github.com/nlyte is an individual user account (two forks: microsoft/generative-ai-for-beginners, apache/olingo-odata4), not an Nlyte Software organization. https://github.com/nlyte
- Unreachable on 2026-09-08 (HTTP 404): netboxlabs/netbox-change-management repository and product page (license UNVERIFIED); Nlyte NgageAPI datasheet PDF (write assertion now unreachable); Nlyte NgageAPI resource page.

### Still UNVERIFIED after this pass
- Nlyte OData `$metadata`, write verbs, rate limits, session TTL, entity-set stability across v14/15/16, connection/power-path/floor-plan entities, and whether the integration endpoint is separately licensed (D32 resolves per customer).
- Nlyte BDM/Asset Autoloader template formats.
- Icecat Fair Use Policy purpose restriction (D45 counsel gate).
- NetBox Labs Change Management plugin license.
- Eclipse Tahu Sparkplug `.proto` license (assumed EPL-2.0).
- ISO/IEC 30134 part numbers for WUE/CUE.
- Whether the full Nlyte application (not only pollers) runs on Linux-Docker.
