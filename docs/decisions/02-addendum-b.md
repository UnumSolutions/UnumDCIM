# Addendum B: ServiceNow, edge scope, multi-client, receiving, demand/forecast, MCP

> **Status:** accepted, 2026-09-12. Addendum B as produced by the round-2 design pass, with the round-3 corrections applied in place (per-decision correction blocks inserted after each of D63 to D74; C.4 re-labelings applied to the wording), and the round-3 conflict resolutions, new decisions D75 to D83 and roadmap/risk/question amendments appended below. The condensed form of every decision here is in the approved plan; where this document and the corrections sections differ, the corrections win.


**Status:** proposed, 2026-09-11. Continues the decision record from D62. Numbering D63 to D74 matches the condensed entries already merged into the plan's section 2b; this document is the full form (options, objections, rationale, doors, evidence that would flip each decision) and supersedes the condensed text where the two differ. Two condensed-text corrections are applied here: Claude.ai's per-call timeout is 240 s, not 240-second (D74), and Redfish exposes `AssetTag` **and** `HostName` as writable, so `AssetTag` is the only writable *inventory-tag* property, not the only writable identity property (D70).

**Inputs.** Round-2 research on five topics (ServiceNow, edge/MSP scope, receiving/onboarding, demand/forecast, MCP) with adversarial verification of 25 claims: 6 confirmed, 3 disputed on detail, 16 refuted on detail. Where verification corrected a researcher, the corrected form is used and the original is listed in section B.7. Two licenses the research left unverified were checked on 2026-09-11: django-oauth-toolkit is BSD-2-Clause (https://raw.githubusercontent.com/jazzband/django-oauth-toolkit/master/LICENSE); Nominatim's Python is GPL-3.0-or-later, its other files GPL-2.0, its Lua config Apache-2.0 (https://github.com/osm-search/Nominatim), so per D04 it runs only as an isolated container.

**Founder constraints honored:** Apache-2.0 core (D04), self-hosted only for 24 months (D10/D26), balanced funnel (Phase 1 ships both the NetBox twin and the Nlyte Collector). Nothing below introduces a hosted dependency, a phone-home, or a non-permissive in-process dependency.

---

## B.1 ServiceNow bidirectional sync (requirement 5)

### D63 ServiceNow adapter architecture: pull, push, real-time inbound, auth, write-back safety

**Area:** `unum-sync` adapter (D22 framework), security (D25), write-back protocol (D47).

**Why it matters.** The founder asked for automation that pushes *and* pulls data-center updates, not a CMDB export. ServiceNow's surface is well documented but licensing-shaped: the pull direction is nearly free, the push direction has one sanctioned door into the CMDB (the Identification and Reconciliation Engine), and the "ServiceNow calls UnumDCIM" direction has a licensed and an unlicensed variant. Getting the door choice wrong either bypasses ServiceNow's reconciliation (creating duplicate CIs the customer's CMDB team will blame on us) or ties the customer to an IntegrationHub subscription they may not hold. It also sets the shape of every later ITSM adapter (Jira, BMC per D30).

**Options and strongest objection to each.**

*Pull direction (ServiceNow → UnumDCIM).*

| Option | Strongest objection |
|---|---|
| P1. Table API scheduled delta pulls on `sys_updated_on` per table, plus Change Management API for changes | Polling latency (15 min baseline) and per-user hourly rate-limit rules; no server-side change feed. |
| P2. ServiceNow-initiated push on every record change (Business Rule / Flow) as the primary channel | Requires customer-side development on every instance; Flow Designer REST step needs IntegrationHub; business rules fire per record and can flood a self-hosted endpoint; no replay if UnumDCIM is down. |
| P3. Nightly full export via Table API only | Loses intra-day change and receipt events that the receiving workflow (D70) depends on. |

*Push direction (UnumDCIM → ServiceNow CMDB).*

| Option | Strongest objection |
|---|---|
| U1. Direct IRE REST: `POST /api/now/identifyreconcile/enhanced` with a registered discovery source, `sys_object_source_info` native keys, `/query` for dry-run | a verifier's paraphrase of ServiceNow developer guidance says apps that push via the IRE REST API are not eligible for Store certification (UNVERIFIED, no URL captured; not load-bearing, correction C.4 item 3); the discovery-source `sys_choice` must exist before the first call; dependent CIs need parents in the same payload. |
| U2. Import Set API + transform map calling `CMDBTransformUtil.identifyAndReconcile` | One transform map per import set, no mandatory-field checks, and "cannot be applied to Import Sets for dependent CIs" (PDU outlets, blades), which are exactly the objects UnumDCIM masters. |
| U3. IntegrationHub ETL / Robust Transform Engine (the Service Graph Connector substrate) | Requires `cmdb_inst_admin`, IntegrationHub entitlement on the customer side, and a scoped app to ship; this is the certified pattern but the wrong first artifact for an OSS project without a Store presence (D66). |
| U4. Table API writes to `cmdb_ci_*` | Bypasses IRE entirely; duplicates, no `discovery_source` stamping, no reconciliation precedence; discouraged by ServiceNow and by every precedent connector. |

*Real-time inbound (ServiceNow → UnumDCIM event delivery).*

| Option | Strongest objection |
|---|---|
| R1. Business Rule + `RESTMessageV2.executeAsync` with an OAuth profile, optionally `setMIDServer` | Customer must own a small script per table; async has no delivery guarantee, so it is a hint, not the record of truth. |
| R2. Flow Designer REST step | Needs the IntegrationHub plugin/subscription; the "1 million free transactions" tier "is no longer true for all customers". |
| R3. No inbound at all; pull only | Receipt events and change approvals arrive up to one polling interval late; acceptable for CMDB, weak for the dock (D70) and approval gates (D65). |

*Write-back safety.*

| Option | Strongest objection |
|---|---|
| W1. Apply the D47 protocol verbatim (staging validation, dry-run diff approved by a named admin, canary ≤ 10 objects with read-back, rate limit, kill switch, schema-drift auto-pause, per-tenant flag) | D47 was written for Nlyte's undocumented API; ServiceNow's `/query` dry-run and `maskedAttributes` give stronger primitives that D47 does not use. |
| W2. Trust IRE and skip staging | A masked write looks like success to a naive client; reconciliation rules can silently reject our values and the customer's CMDB team can change rules at any time. |

**Recommendation.** P1 as the baseline with R1 documented as the low-latency hint channel (R2 documented as the alternative for customers who already own IntegrationHub); U1 for CMDB writes with U2 available as a fallback only for independent CIs; W1 extended with IRE-specific steps. Concretely:

- **Pull:** Table API (`GET /api/now/table/{table}` with `sysparm_query=sys_updated_on>{watermark}`, `sysparm_fields`, `sysparm_limit`/`sysparm_offset`, `sysparm_display_value=all` for choice labels, `sysparm_exclude_reference_link=true`) over `cmdb_ci_datacenter`, `cmdb_ci_computer_room`, `cmdb_ci_zone`, `cmdb_ci_rack`, `cmdb_ci_pdu`, `cmdb_ci_pdu_outlet`, `cmdb_ci_ups`, `cmdb_ci_crac`, `cmdb_ci_hvac`, `cmdb_ci_power_eq`, `cmdb_ci_circuit`, the device classes the customer maps, `cmdb_rel_ci`, `alm_hardware`/`alm_asset`, `alm_stockroom`, `alm_transfer_order`, `proc_po`/`proc_rec_slip`, `cmn_location`, `core_company`, `cmdb_model`/`cmdb_hardware_product_model`, `task_ci`, `change_request` via `/api/sn_chg_rest/change`, and `dmn_demand` where SPM exists (D65). Delta every 15 min where the watermark filter works, nightly full snapshot with hash comparison (D46 parameters). Honor `X-Total-Count`, `Link`, HTTP 429 with `Retry-After` and `X-RateLimit-*`. Use the Batch API (`/api/now/v1/batch`) only for small, ordered read sets: it runs on the default semaphore pool and can starve the customer's UI.
- **Push:** every CMDB write is an IRE payload (`items[]` with `className`, `values`, `lookup[]`, `related[]`; `relations[]` with `parent`/`child` indexes and `type`; `sys_object_source_info {source_name: "UnumDCIM", source_native_key: <UUIDv7>}`; `last_discovered` set to the UnumDCIM confirmation time). Dry-run with `/query` or `/queryEnhanced` before every batch; independent parents precede dependent CIs in the same payload; discovery source `UnumDCIM` registered by a documented one-time admin step (v1 uses the admin step only; an install-time Fix Script becomes available only with the D66 scoped app, correction C.1 D63 item 4; ServiceNow's own Service Graph Connectors use one; a scoped app cannot package the `sys_choice` as an application file because `sys_choice` does not extend `sys_metadata`). Never write `cmdb_ci` through the Table API. Non-CMDB tables (`cmn_location`, `alm_hardware` when UnumDCIM is HAM master, `change_request`, `change_task`, `task_ci`, `em_event`) are written through their own APIs.
- **Real-time inbound:** UnumDCIM exposes `POST /api/v1/webhooks/servicenow` (OAuth 2.0 bearer only, from a per-tenant django-oauth-toolkit client-credentials client; HMAC dropped per correction C.1 D63 item 7; idempotent on `sys_id` + `sys_mod_count`, always followed by a pull of the referenced record so the webhook is a hint and the Table API is the record). Ship a copy-paste Business Rule (`RESTMessageV2`, `executeAsync`, OAuth profile, optional `setMIDServer`) in the docs; MID Server reaches a self-hosted UnumDCIM outbound on 443 with no inbound firewall change.
- **Auth:** inbound OAuth 2.0 client credentials (Washington DC+; property `glide.oauth.inbound.client.credential.grant_type.enabled`, "OAuth Application User" set, Public Client false) with a dedicated integration user flagged **Web Service Access Only** (never "Internal Integration User") holding `itil` or `asset` plus per-table roles, `evt_mgmt_integration` if Event Management is used; basic auth only as a documented fallback. One integration user per tenant/workload so rate-limit rules scale.
- **Write-back safety (extends D47):** staging → `/query` dry-run diff → named-admin approval → canary ≤ 10 CIs with read-back and `maskedAttributes` inspection → rate limit (default 60 IRE items/min, configurable) → kill switch → auto-pause on `UPDATE_WITH_DOWNGRADE`, class-not-found, or a masked-attribute rate above a threshold → per-tenant flag. Every `maskedAttributes` entry becomes a provenance conflict in the discrepancy queue (D12), never a silent success.
- **Loop prevention:** tag every UnumDCIM-originated write with `sys_object_source_info` and compare `last_discovered`; ignore inbound webhooks whose `sys_updated_by` is our integration user; two-snapshot persistence before surfacing discrepancies (D12).
- **Compatibility:** N and N-1 family releases (Australia and Zurich today; Brazil expected Q4 2026), tested on a Personal Developer Instance each family release, with IRE payload fixtures in CI.

**Rationale.** IRE is the documented path for "any 3rd party data source" and stamps `discovery_source`/`last_discovered` on every CI it touches, which is exactly the provenance signal D12 needs (https://www.servicenow.com/docs/r/api-reference/rest-apis/c_IdentifyReconcileAPI.html; https://github.com/ServiceNow/ServiceNowDocs/blob/australia/markdown/servicenow-platform/configuration-management-database-cmdb/ire.md; https://github.com/ServiceNow/ServiceNowDocs/blob/australia/markdown/servicenow-platform/configuration-management-database-cmdb/exploring-ire.md). Import Sets cannot carry dependent CIs (https://github.com/ServiceNow/ServiceNowDocs/blob/australia/markdown/servicenow-platform/configuration-management-database-cmdb/identification-import-sets.md). The discovery-source scoping constraint and the fix-script workaround are documented in the community thread (https://www.servicenow.com/community/itom-forum/creating-discovery-source-via-scripts-from-application-scope/m-p/2681253). Table API semantics, rate limiting and the Batch API pool behavior: https://www.servicenow.com/docs/bundle/zurich-api-reference/page/integrate/inbound-rest/concept/c_TableAPI.html, https://www.servicenow.com/docs/r/yokohama/api-reference/rest-api-explorer/inbound-REST-API-rate-limiting.html, https://www.servicenow.com/community/servicenow-ai-platform-articles/an-introduction-to-the-batch-rest-api-endpoint-api-now-batch/ta-p/2317136. `RESTMessageV2` needs no IntegrationHub while the Flow REST step does, and the free-transaction tier is no longer guaranteed (https://www.servicenow.com/community/servicenow-ai-platform-forum/do-we-need-any-licenses-for-integration-hub-etl/m-p/2703296). MID Server is outbound-only on 443 (https://www.servicenow.com/community/itom-forum/mid-server-port-details-connection-between-instance-and-mid-and/m-p/2616197). Inbound client credentials and the Web Service Access Only guidance: https://www.servicenow.com/community/developer-blog/up-your-oauth2-0-game-inbound-client-credentials-with-washington/ba-p/2816891. Precedents that chose IRE over Table writes: Device42 (one-way, IRE, free Store app) and NetBox Labs (scoped app, IRE, per-object-type authority; https://netboxlabs.com/docs/servicenow/). Release cadence: https://snowcoder.ai/blog/servicenow-release-cycle-2026.

**Depends on:** D12 (ownership, ExternalReference), D22 (DiffSync framework), D25 (secrets), D41 (staged import), D46 (sync parameters), D47 (write-back protocol).

**Door:** two-way for mechanisms (adapter internals can change); one-way for the rule "CMDB writes only through IRE" (ADR 0019), because any customer CMDB polluted by Table writes cannot be cleaned by us.

**Evidence that would change it.** A ServiceNow primary source showing that IRE REST pushes are Store-certifiable would reopen U3 vs U1 ordering; a customer contract where the integration user still counts as an Unrestricted User despite the Web Service Access Only flag would change the auth default; a documented change-feed API (none exists today) would replace P1's polling.

---


#### Round-3 corrections to D63 (from `Addendum B corrections` C.1; where these differ from the text above, these win)

1. **CI retirement and relationship removal (gap 1).** IRE has no delete operation. The rule "CMDB writes only through IRE" (ADR 0019) is narrowed to *creation and attribute updates of `cmdb_ci` rows*. Retirement is expressed as IRE value updates: `install_status = Retired` (or `Absent` for a CI removed from the estate), `operational_status = Retired`, `hardware_status = Retired/In Disposition` per the customer's mapping, `life_cycle_stage` where the CSDM mapping is enabled, plus `last_discovered`. Relationship removal is a two-step rule: (a) the Phase 0 PDI spike tests whether the `/enhanced` partial-payload path prunes relations omitted from a full-relationship payload (**UNVERIFIED**); (b) if it does not, the adapter is permitted one documented exception: `DELETE /api/now/table/cmdb_rel_ci/{sys_id}` only for rows whose `sys_created_by` equals the UnumDCIM integration user and whose `parent`/`child` both carry `discovery_source = UnumDCIM` or are UnumDCIM-mastered per D64. Relations created by other sources are never deleted; a stale foreign relation becomes a discrepancy. Physical deletion of a CI is never performed; a `retired` CI stays with our stamp so the customer's CMDB team can run their own archival job. ADR 0019 is reworded accordingly.
2. **Write order and reference resolution (gap 2).** Fixed write plan per push run: `core_company` (lookup only; create only when the tenant's OwnershipPolicy names UnumDCIM as company master, default no) → `cmn_location` (lookup, then append child rows per D64 item 3) → `cmdb_hardware_product_model`/`cmdb_model` (lookup by manufacturer + model number; **create only when UnumDCIM is model master**; otherwise a "model missing in ServiceNow" discrepancy is raised and the CI is pushed with `model_id` empty and a `u_unum_model_slug` hint) → `alm_hardware` resolution by serial (item 5) → independent CIs (datacenter, computer room, zone, rack, PDU, UPS, CRAC, power equipment, circuit, devices) → dependent CIs (PDU outlets, blades/modules) in the same payload as their parents → relations. Sys_ids resolved in one step are cached per run; a failed lookup fails the item, not the batch.
3. **Setup kit as a precondition of push (gap 3).** See D75. The adapter probes `cmdb_identifier` at connect time and refuses to push any class that lacks an identification rule, with a message naming the missing rule.
4. **Discovery-source registration in v1 (gap 4).** v1 uses the documented one-time admin step only (create the `sys_choice` on `cmdb_ci.discovery_source`, value `UnumDCIM`). The install-time Fix Script exists only when the D66 scoped app ships (Phase 3 on customer demand). The D63 text "or an install-time Fix Script" is struck for v1.
5. **ServiceNow asset auto-creation (gap 5).** Before pushing any device CI the adapter resolves the existing `alm_hardware` row by serial number (then asset tag) and includes `serial_number`, `asset_tag` and `model_id` in the IRE values so the `AssetAndCISynchronizer` matches rather than creates. At connect time the adapter reads `glide.create_alm_asset` / `glide.create_alm_asset.async` and the "Asset - Create asset delayed sync" job state and records them on the connection profile. Assets that appear in `alm_hardware` with `sys_created_by` = the synchronizer within 30 minutes of a UnumDCIM push are surfaced in the discrepancy queue as "auto-created asset" so the HAM team can merge or accept.
6. **Coexistence with Nlyte Asset Sync or any other DCIM writer (gap 7).** At connect time the adapter enumerates `cmdb_ci.discovery_source` values present on the target classes. If any non-UnumDCIM DCIM source (Nlyte, dcTrack, Device42, Hyperview, NetBox Labs) has stamped placement attributes (location, rack, U, PDU relations) in the last 90 days, those attributes default to **pull-only** for the tenant and the OwnershipPolicy marks them external (owner = that source, mirrored via ServiceNow). A one-way **cut-over switch** (D21b, new) flips ownership to UnumDCIM for a migration: it requires the D47 named-admin approval, records the date, and thereafter treats the other source's writes as discrepancies. Two DCIM writers on the same attribute are never allowed silently.
7. **Inbound webhook authentication (gap 46).** OAuth 2.0 bearer (a django-oauth-toolkit client-credentials client issued per tenant) is the **only supported mode**; HMAC is dropped. `RESTMessageV2.setAuthenticationProfile` with an OAuth profile is the documented customer-side pattern. The docs include MID Server keystore import for private CAs (the UnumDCIM TLS certificate must be trusted by the MID JVM) and the ECC-queue behavior when UnumDCIM is unreachable (fire-and-forget; the pull is the record).
8. **Bulk-load mode after the canary (gap 45).** Three throughput modes: *canary* (≤ 10 CIs, read-back), *steady* (default 60 IRE items/min), *bulk* (post-canary, admin-enabled, off-hours window configurable; enhanced payloads of up to 250 items with parents and dependents grouped; concurrency 2; rate governed by `X-RateLimit-Remaining`/`Retry-After`). Expected throughput is documented as an **estimate** of 5,000 to 15,000 items/hour on a typical production instance; D41's 100k assets/hour applies to UnumDCIM's own import, not to the ServiceNow push, and D41's text is annotated to say so. Initial CMDB population of 100k CIs is planned as a multi-night bulk run, not a one-hour job.
9. **Plugin and license probing (gaps 9, 10).** The connect-time probe (D75) detects Event Management (`em_event` readable / `evt_mgmt_integration`), SPM (`dmn_demand`), Procurement (`proc_po`, `proc_rec_slip`), HAM Pro (`sn_hamp`), CI Class Models (`cmdb_ci_container_rack`), Domain Separation (`sys_domain` on `cmdb_ci`), Multisource CMDB, Telecom Network Inventory, and the inbound client-credentials property. Each absent feature disables the corresponding adapter function with a named message; nothing returns a bare 403 to the operator.
10. **Test instances (gap 11).** The Phase 0/1 CI target is a **partner sub-production instance** (founder question 19) or a vendor instance; a Personal Developer Instance is used only for smoke tests. PDI constraints are recorded: auto-upgrade to the current family, reclamation after inactivity, no HAM Pro/SPM/Event Management/Discovery, and developer-program terms for automated commercial testing **UNVERIFIED**. The N-1 promise is restated as "N supported; N-1 tested where an N-1 instance is available to the project; otherwise best effort with fixtures recorded on N-1 while it was current."
11. **Phase 0 exit criterion (gap 12).** Replaced: "With a Discovery-style reconciliation rule set installed on the test instance (ServiceNow priority 100 on HAM-owned attributes, UnumDCIM priority 100 on placement attributes, per the D64 table), a 100-CI payload round-trips with placement attributes accepted, HAM-owned attributes masked exactly as the D64 table predicts, and the masked entries visible in the discrepancy queue."

### D64 CMDB/CSDM class mapping and per-attribute ownership

**Area:** data model crosswalk (D11/D12), OwnershipPolicy defaults (D40 pattern).

**Why it matters.** ServiceNow has real facility classes but no U-position, no device-level elevation and no power-path model out of the box. If UnumDCIM tries to make ServiceNow the master of anything spatial, the twin's placement-as-one-fact rule (D12) breaks. If UnumDCIM refuses to publish spatial facts at all, the customer's CMDB stays blind and the integration looks like a viewer. The mapping also decides which of the customer's custom `u_` fields must be configurable per tenant.

**Options and strongest objection.**

| Option | Strongest objection |
|---|---|
| M1. Map to base CMDB classes (`cmdb_ci_datacenter`, `cmdb_ci_computer_room`, `cmdb_ci_zone`, `cmdb_ci_rack`, `cmdb_ci_pdu`, `cmdb_ci_pdu_outlet`, `cmdb_ci_ups`, `cmdb_ci_crac`/`hvac`, `cmdb_ci_power_eq`, `cmdb_ci_circuit`) plus `cmn_location` for the ITSM hierarchy; publish U-position as tenant-configurable attributes and "Rack contains" relationships | Custom `u_` field names differ per instance; no closet class exists; ServiceNow's OOB `cmdb_rel_rollup` on "Rack contains" recomputes `rack_units_in_use`/`power_consumption` and may fight our values. |
| M2. Ship a scoped attributes table (NetBox Labs' `x_nbl_cmdb_netbox_attributes` pattern) for elevation, orientation, power path | Requires a scoped app and therefore a Store presence or a customer-installed update set; deferred by D66. |
| M3. Require the CI Class Models app's container classes (`cmdb_ci_container_rack`, `_cabinet`, `_shelf`, `_slot`, patch panels) | Not installed everywhere; base-class customers would get nothing. |
| M4. Target Telecom Network Inventory's native rack elevation ("Equipment Holder", "Rack to slot") | Separately licensed product; only telco customers have it. |

**Recommendation.** M1 by default, M3 when the Class Models app is detected (probe the class table at connection time), M2 as the future scoped-app artifact (D66), M4 detected and treated as an external elevation master per OwnershipPolicy if a customer runs TNI.

- **Spaces:** `cmn_location` hierarchy (site → building → floor → room/closet, `parent` and `cmn_location_type` where the instance uses it; lat/long, time zone, `company`, `stock_room`) for ITSM use, plus CIs for the CMDB: data_hall/computer_room/micro_edge_dc → `cmdb_ci_datacenter` or `cmdb_ci_computer_room`; zone/row/cage → `cmdb_ci_zone`; telecom_room/main_telecom_room/server_room/equipment_room/entrance_facility/telecom_enclosure (D67 classes) → `cmn_location` plus `cmdb_ci_computer_room` with `u_space_class` (documented; no OOB closet class).
- **Racks and devices:** Rack → `cmdb_ci_rack` (`rack_units` from RackType height; `rack_position`/`rack_row` where used). Device → the customer's class map (server, switch, PDU, etc.) with tenant-configurable elevation fields (default names `u_rack_position`, `u_rack_height_u`, `u_rack_face`), a "Rack contains" (`In Rack::Rack contains`) relationship, model `Height (U)` pushed to `cmdb_hardware_product_model`. Publish **either** our own `rack_units_in_use`/`power_consumption` with the OOB rollup disabled by the customer, **or** only the relationships and heights and let `cmdb_rel_rollup` compute; the adapter setting is explicit and defaults to "let ServiceNow roll up" so we never fight it.
- **Power and cooling:** PDU → `cmdb_ci_pdu`, outlet → `cmdb_ci_pdu_outlet` (dependent CI, parent in the same payload), UPS/`power_eq`/`circuit` for the upstream chain, `powers::powered by` relationships from PDU outlet to device; CRAC/HVAC CIs with `Cools::Cooled by` (relationship type UNVERIFIED; used only if present in `cmdb_rel_type`, correction C.4 item 4) only where the customer already uses it. End-to-end power-path traversal stays in UnumDCIM; ServiceNow gets the edges.
- **Ownership defaults (added to the D12/D40 tables, editable per tenant):** ServiceNow (HAM/Discovery) masters asset tag, serial, model normalization, cost/contract/warranty, assigned-to, asset state and CI operational status when HAM/Discovery is present; UnumDCIM masters `cmn_location`-independent placement (room, rack, U, face, orientation), power path (PDU/outlet), cooling assignment, capacity, rack units in use, floor geometry, art and scenarios; either may master `cmn_location` depending on which system the customer designates. The reconciliation rule priority per data source in ServiceNow mirrors the OwnershipPolicy; a `maskedAttributes` response is treated as "ServiceNow is the owner of this field on this class" and offered to the admin as a one-click OwnershipPolicy update.
- **CSDM:** Physical CIs carry the CSDM `life_cycle_stage`/`life_cycle_stage_status` where the customer enabled the life-cycle mapping (`csdm.lifecycle.sync.between.ci.and.asset.activated`); we never invent CSDM Service Instances; the CSDM 5 "Facility Service Instance" is not targeted until a customer models one (open question).

**Rationale.** Class inventory: https://www.servicenow.com/docs/r/servicenow-platform/configuration-management-database-cmdb/cmdb-tables-details.html and https://www.servicenow.com/docs/r/servicenow-platform/configuration-management-database-cmdb/cmdb-ci-class-model-list-of-classes.html. Community elevation pattern and the rollup: https://www.servicenow.com/community/cmdb-forum/tracking-racks-in-servicenow-as-cis-and-creating-relationships/m-p/3480774 (verification added KB0788463 and `cmdb_rel_rollup` on "Rack contains"). Location hierarchy and `cmn_location` fields: https://github.com/ServiceNow/ServiceNowDocs/blob/australia/markdown/platform-administration/table-administration-and-data-management/data-hierarchies.md, https://www.servicenow.com/community/brazil-snug/cmn-location-table/ba-p/2280051. Reconciliation precedence and `maskedAttributes`: https://www.servicenow.com/community/cmdb-articles/understanding-ire-reconciliation-rules/ta-p/3289239. Precedent ownership split (ServiceNow masters asset attributes, Nlyte masters location/cabinet/U): https://www.nlyte.com/blog/master-your-assets-nlyte-servicenow-cmdb-integration/. NetBox Labs' mapping of Sites/Regions to `cmn_location`, Tenants to `cmn_department`, Manufacturers to `core_company`: https://netboxlabs.com/docs/servicenow/. CSDM 5: https://www.servicenow.com/community/common-service-data-model/csdm-5-finally-get-the-csdm-5-white-paper-here/ta-p/3254967.

**Depends on:** D11, D12, D40, D63, D67 (space classes).

**Door:** two-way; the mapping table is data, versioned per family release.

**Evidence that would change it.** An OOB device-level rack-position field in Brazil or later, or a customer whose CSDM 5 Facility Service Instances are the required container, would change the default targets.

---


#### Round-3 corrections to D64 (from `Addendum B corrections` C.1; where these differ from the text above, these win)

1. **Install state ownership (gap 6; conflict with D65/D70).** Ownership of state fields is split by lifecycle segment, and the D64 table is amended:
   - *Procurement segment* (`On order` → `In stock` and substates, `In transit`, `Missing`, `Retired` substates such as `Disposed`/`Sold`): **ServiceNow HAM masters** when HAM is present; UnumDCIM mirrors.
   - *Placement segment* (`install_status` and `hardware_status` for devices UnumDCIM has placed or staged: `Pending Install`, `Installed`, `In Maintenance`, `Retired`, `Absent`): **UnumDCIM masters** and pushes through IRE; the customer's `alm_hardware_state_mapping` then copies to the asset. The setup kit (D75) includes a reconciliation rule granting UnumDCIM priority on `install_status`/`hardware_status` for the mapped device classes.
   - If the customer refuses that rule, the tenant switches to *request mode*: installation creates a `change_task` "set asset state for {serial}" assigned to the HAM group, and UnumDCIM waits for the pulled value. The mode is a per-tenant setting recorded with the OwnershipPolicy.
2. **`cmn_location` default (gap 13).** Default: **ServiceNow masters `cmn_location`** when at connect time the table has ≥ 1 row referenced by `alm_stockroom`, `cmdb_ci` or `sys_user`; otherwise **UnumDCIM masters**. In either mode UnumDCIM only ever *appends* child rows for spaces absent in ServiceNow (matched by parent + name), never renames or re-parents existing rows; re-parent proposals are discrepancies.
3. **Per-source values on the ServiceNow side (gap 47).** Per-source attribute history in ServiceNow depends on the Multisource CMDB feature (ITOM Discovery license). Without it ServiceNow keeps only the winning value; UnumDCIM keeps its own staged per-source copies (D12/D41) regardless, and the docs say so.
4. **Relationship types.** Attested types are `In Rack::Rack contains` and `Powers::Powered by`. The `Cools::Cooled by` type is **UNVERIFIED** and is used only if present in `cmdb_rel_type` at connect time; otherwise cooling assignment stays in UnumDCIM.
5. **Serial and asset-tag ownership (conflict with D40/D70).** Resolved by D76.

### D65 Change, work orders, alarms, HAM receiving and demand attachment

**Area:** workflow (D30), alarms (D52), receiving (D70), demand (D71).

**Why it matters.** "Push and pull data-center updates" in an ITSM shop means MAC work rides on change requests, DCIM alarms become alerts and incidents, receipts come from the HAM stockroom, and capacity demand originates in SPM. Without these attachments the adapter is a CMDB mirror, which every precedent already sells.

**Options and strongest objection.**

| Option | Strongest objection |
|---|---|
| C1. UnumDCIM work orders create/lookup `change_request` via `/api/sn_chg_rest/change`, add affected CIs through `task_ci`, create `change_task` per MAC step, gate execution on the pulled approval state | The "add affected CI" endpoint `POST /api/sn_chg_rest/v1/change/{sys_id}/ci` is UNVERIFIED (docs returned 403); fallback is a Table API insert into `task_ci`. |
| C2. ServiceNow change drives UnumDCIM (change created first in ServiceNow, UnumDCIM executes) | Facilities planners work in the twin; forcing them into ServiceNow first defeats the intent model (D12). Support both directions via ExternalReference. |
| C3. No change integration in v1 | The Nlyte Service Management Connector and dcTrack ticket sync already do this; parity gap. |

**Recommendation.** C1 with C2 supported (a change created in ServiceNow that references a UnumDCIM CI becomes a ChangeRequest intent in UnumDCIM via the pull). Details:

- **Change:** normal, standard (from template) and emergency via `/api/sn_chg_rest/change`; affected CIs via the vendor-documented `/change/{sys_id}/ci` if verified on the PDI, else `POST /api/now/table/task_ci`; one `change_task` per WorkOrder step; approval state polled (and hinted by webhook per D63); the change number stored on the WorkOrder and rendered on the twin's ghost placement; maintenance windows from the change's planned start/end feed the alarm engine's suppression (D52).
- **Alarms:** `POST /api/global/em/jsonv2` into `em_event` with `message_key` = UnumDCIM alarm id so clears close alerts; `evt_mgmt_integration` role; off by default, per-tenant toggle.
- **HAM receiving linkage:** pull `proc_po`, `proc_rec_slip` (and lines), `alm_hardware` with state In stock, `alm_transfer_order`, disposal orders; a receiving slip becomes a ReceivingRecord with provenance = ServiceNow; UnumDCIM placement then pushes `install_status`/`hardware_status` and the location through IRE and the change. Create `alm_hardware` from UnumDCIM only when the tenant's OwnershipPolicy names UnumDCIM as HAM master. Detect `sn_hamp` (HAM Pro) at connection time to know whether model normalization, mobile receiving and onboarding flows exist on the customer side; on core-only instances, states are changed manually and the adapter must tolerate values outside the documented enum (e.g., "Consumed" from a known error).
- **Demand:** where SPM is present, mirror `dmn_demand` (default states Draft, Submitted, Screening, Qualified, Deferred, Approved, Completed; configurable via playbooks since the Australia release, so state names are mapping data) into DemandRequest (D71) with an ExternalReference; conversion targets (Project, Epic, Change, etc.) are read, not created, in v1. Whether UnumDCIM masters or mirrors DemandRequest is a per-tenant OwnershipPolicy (founder question 15).

**Rationale.** Change API and roles: https://www.servicenow.com/docs/bundle/zurich-api-reference/page/integrate/inbound-rest/concept/change-management-api.html. Event Management inbound: https://www.rapdev.io/blog/send-test-events-to-servicenow-event-management-with-postman. HAM tables, receiving slips per partial receipt, and lifecycle: https://www.servicenow.com/community/ham-forum/essential-plugins-and-terminology-for-streamlined-hardware-asset/m-p/3239979, https://www.servicenow.com/docs/bundle/xanadu-it-asset-management/page/product/procurement/task/t_ReceiveAnAsset.html. HAM Pro vs core: https://www.servicenow.com/community/ham-blog/core-asset-management-vs-ham-pro-what-you-actually-get-and-when/ba-p/3518013. Demand lifecycle: https://www.servicenow.com/community/spm-forum/understanding-demand-management-in-servicenow-spm-end-to-end/m-p/3544948 (verification: table `dmn_demand`, states configurable in Australia). Nlyte's RFC-from-workflow precedent: https://www.nlyte.com/blog/master-your-assets-nlyte-servicenow-cmdb-integration/.

**Depends on:** D30, D52, D63, D64, D70, D71.

**Door:** two-way.

**Evidence that would change it.** PDI verification of `/change/{sys_id}/ci`; a design partner without SPM (then DemandRequest is UnumDCIM-mastered by default); a design partner running HAM Pro mobile receiving (then the dock UI in D70 defers to ServiceNow's and UnumDCIM only pulls slips).

---


#### Round-3 corrections to D65 (from `Addendum B corrections` C.1; where these differ from the text above, these win)

1. **Change state mapping (gap 8).** An editable mapping table, shipped with defaults, maps `change_request.state` to UnumDCIM intent/WorkOrder states: New/Assess/Authorize → ChangeRequest `submitted` (ghost visible, reservations soft); Scheduled → `approved` (reservations firm, WorkOrder `ready`); Implement → WorkOrder `executable`; Review → WorkOrder `verifying`; Closed (successful) → intent `applied`; Closed (unsuccessful/incomplete) → intent `failed`, ghost retained for rework; **Canceled or rejected → intent withdrawn, ghost removed, reservations released**, with a notification to the proposer. The Phase 2 exit criterion references this table.
2. **Reverse receipt into HAM (gap 24).** When HAM masters assets but the physical receipt happens at a UnumDCIM dock: preferred mechanism is a Table API insert into `proc_rec_slip` and `proc_rec_slip_item` for the matched PO line (**UNVERIFIED** that the receiving business logic fires on API inserts; test on the partner instance); fallback is a `change_task` "receive PO line {n}, serial {s}" assigned to the HAM group, with the UnumDCIM ReceivingRecord holding provenance until the pulled asset state reaches `In stock`. The mechanism is selected per tenant after the probe.
3. **Licensing checklist (gap 9).** Event Management inbound requires the ITOM Event Management/ITOM Health subscription; `dmn_demand` requires the SPM Demand Management SKU; `proc_po`/`proc_rec_slip` require the Procurement plugin; HAM Pro features require `sn_hamp`. Added to risk 21 and to the D75 probe.
4. **Demand push (gap 32).** v1 is **mirror-only**: when SPM is present, ServiceNow masters DemandRequest and UnumDCIM never writes `dmn_demand`. The extra UnumDCIM states (`Reserved`, `Fulfilled`, `Closed`, `Rejected`) are local sub-states beneath `Approved`/`Completed`/`Deferred` and are not projected. A push path (Table API writes to `dmn_demand` with a state mapping, fields **UNVERIFIED**) is deferred to a founder decision after a partner instance is available; D72's "ServiceNow demand sync" is reworded to "ServiceNow demand mirror (pull), push deferred".

### D66 Store, Service Graph Connector and partner-program posture

**Area:** go-to-market, D07/D24 certified-connector program.

**Why it matters.** Store certification is the credibility signal enterprise CMDB teams ask for, but the corrected research shows it is gated by a paid partner program, a design review, two beta customers, per-release recertification, and customer-side ITOM or ITAM subscription units. Paying that early buys nothing for an OSS project with no customers.

**Options and strongest objection.**

| Option | Strongest objection |
|---|---|
| S1. No Store app in v1; direct IRE adapter in `unum-sync`; revisit certification on the first paying customer that requires it | Competitors (Sunbird, Device42, NetBox Labs, Nlyte) hold the "certified connector" slot; some RFPs check the box. |
| S2. Build a scoped Store app now (pull/import-set pattern, attributes table) and pursue SGC certification | Build Partner Program fee (amount unverified; program restructured 20 Jan 2026 into Access/Registered/Select/Premier/Elite), certification duration unknown (plan one family-release cycle; correction C.4 item 2), recertification each family release, and SGC usage forces the customer to hold ITOM Visibility/Discovery or ITAM SU SKUs; the certified artifact is a *different* artifact from the direct IRE adapter. |
| S3. Publish an uncertified scoped app as an update set in the repo | Update sets are not installable through the Store and ServiceNow discourages them for third-party apps; still carries the discovery-source fix-script problem. |

**Recommendation.** S1, with the scoped-app design (D64 M2) kept ready as a Phase 3 option funded by a customer. Budget assumptions if triggered: Build Partner membership at the lowest tier that can publish (verify whether the no-enrollment Access Tier can), vendor instances, two beta customers from the design-partner program, recertification twice a year folded into the D27 release cadence. Differentiation stays open-source transparency and provenance, not Store presence.

**Rationale.** SGC program requirements and licensing: https://blog.glidefast.com/what-are-service-graph-connectors-in-servicenow, https://www.servicenow.com/content/dam/servicenow-assets/public/en-us/doc-type/resource-center/data-sheet/ds-service-graph-connector-program-data-sheet-partners.pdf (403 on fetch; snippet), https://www.servicenow.com/community/itom-forum/service-graph-connector-entitlement/td-p/3245107 (verification: ITAM SU SKUs are an alternative entitlement path via the "Service Graph Connector Licensing" dependency app; "n-3" currency unconfirmed). NetBox Labs' certified v2.0 requires a commercial CMDB Integration license, which shows the certified route is being monetized by incumbents, not given away: https://netboxlabs.com/docs/servicenow/.

**Depends on:** D06, D07, D24, D63.

**Door:** two-way.

**Evidence that would change it.** A signed customer whose procurement requires a Store listing; publication of the Build Partner fee schedule showing an Access Tier that can list on the Store at no cost.

---


#### Round-3 corrections to D66 (from `Addendum B corrections` C.1; where these differ from the text above, these win)

- The "5 to 8 weeks certification" figure has no source and is struck; the budget line reads "certification duration unknown; plan one family-release cycle."
- The claim "ServiceNow's developer guidance says apps that push via the IRE REST API cannot be Store-certified" is re-labeled **UNVERIFIED** (no URL captured) and does not bear on S1, which stands on the partner-program and entitlement facts alone.

## B.2 Scope extension: server rooms, closets, IDF/MDF, floor-plan-less sites (requirement 6a)

### D67 Space classes, per-class feature applicability, rack form factors, bulk site onboarding and map views

**Area:** data model (D11), floor geometry (D13), twin UX (D15), library (D17), sync (D22).

**Why it matters.** A NetBox-superset schema has Region/SiteGroup/Site/Location but no notion of *what kind* of space a Location is, and the twin assumes floor geometry. Closets have no floor plan, hold one wall cabinet, and are audited by a technician with a scanner, not planned by a capacity manager. Without a typed class, every feature (aisles, containment, CFD, tile load) leaks into the closet UX and the product looks wrong to the customer whose estate is 300 IDFs and two halls. The class also determines the ServiceNow, Nautobot and NetBox projections (D64).

**Options and strongest objection.**

| Option | Strongest objection |
|---|---|
| T1. Typed `SpaceClass` enum on Location (written deviation from NetBox), Nautobot-style attachment rules enforced in UnumDCIM | Lossy to NetBox (class must ride in a custom field or tag; NetBox declined native classes, issue #21041 closed not planned Dec 2025); a fixed enum needs a governance path for new classes. |
| T2. Free-form `facility` string and tags only (NetBox-native) | No enforcement, no per-class feature gating, no reliable projection to Nautobot `LocationType` or ServiceNow `cmn_location_type`. |
| T3. Fully user-defined LocationType hierarchy (Nautobot 1:1) | Every estate invents its own taxonomy, so crosswalks (Nlyte LocationGroups, dcTrack LOCATION/SUB-LOCATION, Device42 Building/Room, ServiceNow) cannot be shipped as defaults. |

**Recommendation.** T1 with a small fixed class set and a `custom` escape hatch that maps to Nautobot `LocationType` by name:

- **Classes:** `region`, `campus`, `building`, `floor`, `data_hall`, `computer_room`, `micro_edge_dc` (TIA-942-C µEDC, Type A networked / Type B standalone), `server_room`, `equipment_room` (ER), `telecom_room` (TR/IDF; TIA-942 HDA/IDA when inside a data center (editorial vocabulary choice, not a standards statement; correction C.4 item 10)), `main_telecom_room` (MDF; MDA/ENI/MD in TIA/ISO terms), `entrance_facility` (EF/ER/ENI), `telecom_enclosure` (TE), `cage`, `row`/`aisle` (existing), and the stock classes `dock`, `staging`, `burn_in`, `stockroom` (D70). Each class carries `nestable`, `allowed_parents`, `allowed_children`, `allowed_content_types` (Nautobot pattern) and a feature-applicability profile.
- **Feature applicability:** floor geometry, tile grid, aisles, containment, cooling chain, tile load rating, heat tiles and the OpenDC/CFD tiers apply to `data_hall`, `computer_room`, `micro_edge_dc` (and `cage` inside them). `server_room` gets geometry optionally. `telecom_room`, `main_telecom_room`, `equipment_room`, `entrance_facility`, `telecom_enclosure` default to **no floor plan**: rack list, elevation view, patch-panel-dense cabling, single-feed power (optional −48 V DC chain from dcTrack 7.1-style objects), one or two environmental sensors, and a map pin. The twin renders a procedural closet scene (walls sized from rack count and form factor) when no geometry exists, labeled "procedural"; geometry can be added later without changing the class.
- **Rack form factors:** adopt NetBox `RackFormFactorChoices` verbatim (`2-post-frame`, `4-post-frame`, `4-post-cabinet`, `wall-frame`, `wall-frame-vertical`, `wall-cabinet`, `wall-cabinet-vertical`), widths 10/19/21/23 in, RackType-first (mandatory in NetBox 5.0). Add CC0 RackType records for common sub-20U wall cabinets, 2-post relay racks and 10-inch cabinets to `library-core` so closet onboarding needs no custom types.
- **Identifiers:** a TIA-606-C-compatible identifier generator (Class 1 single ER, Class 2 building/tenant, Class 3 campus, Class 4 multi-site; pattern `[site-]building-space-rack[-panel-port]`, e.g., `B1-TR2-PP05-P12`) as the default naming template; Class 4 site prefixes are switched on automatically in MSP mode (D68). Standards texts are paywalled; product copy uses the vocabulary and never claims "TIA-942 compliant".
- **Bulk site onboarding:** CSV/XLSX template (address, class, contact, time zone, rack rows with form factor and height, optional lat/long, optional client for MSPs) through the D41 staging importer; geocoding via a pluggable provider whose default is a **self-hosted Nominatim container** (GPL, isolated per D04; public Nominatim only for tiny batches at ≤ 1 request/second with an identifying User-Agent), never Google Geocoding for persisted coordinates (its policy forbids storing results other than place IDs).
- **Map view:** MapLibre GL JS (BSD-3) in `unum-twin` with pins by class/status/alarm and clustering for thousands of closets; tile source configurable and defaulting to a bundled public-domain low-zoom basemap so air-gap and no-phone-home (D26/D37) hold; external tile providers are opt-in with their terms shown.
- **Crosswalk:** ExternalReference mappings for Nlyte `LocationGroups`, dcTrack LOCATION/SUB-LOCATION, Device42 Building/Room/Customer, Hyperview Location, Hudu company/asset and ServiceNow `cmn_location`/`cmn_location_type`.
- **Projections:** Nautobot `LocationType` 1:1 (lossless, with `content_types` derived from the applicability profile); NetBox Site (+SiteGroup for site-level classes) or Location + `unum_space_class` selection custom field (lossy: attachment rules cannot be expressed in NetBox); ServiceNow `cmn_location` + `cmn_location_type` where used (D64).

**Rationale.** TIA-942-C spaces and µEDC: https://www.tiafotc.org/tia-standards-update/tia-942-c/, https://www.cablinginstall.com/standards/article/55245177/tia-942-c-data-center-standard-brings-a-host-of-changes-and-updates; TIA-569-E: https://www.tiafotc.org/tia-standards-update/tia-569-e/; TIA-606-C classes and identifiers: https://www.cablinginstall.com/cable/article/14035166/tia-606-c-standard-requirements-for-cable-plant-administration; ISO/IEC 11801 distributors: https://en.wikipedia.org/wiki/ISO/IEC_11801. NetBox Location fields (no type): https://netboxlabs.com/docs/netbox/models/dcim/location/; form factors and RackType: https://raw.githubusercontent.com/netbox-community/netbox/main/netbox/dcim/choices.py, https://netboxlabs.com/docs/netbox/models/dcim/racktype/. Nautobot LocationType (nestable, content_types, linear chains recommended): https://docs.nautobot.com/projects/core/en/stable/user-guide/core-data-model/dcim/locationtype/. Vendor hierarchies: https://www.sunbirddcim.com/help/dcTrack/v810/API/en/Content/dcTrack/dcTrack_Hierarchy.htm, https://docs.device42.com/infrastructure-management/buildings-rooms-and-racks/buildings-and-rooms/, https://docs.hyperviewhq.com/user-guide/layout-management/topics/location-layouts.html. Closet-scale estates exist (300 IDF sites; ~400 telco closets in 180 countries): https://www.sunbirddcim.com/blog/how-does-dcim-software-support-edge-computing-it-closets-and-distributed-it-environments. Geocoding and tile policies: https://operations.osmfoundation.org/policies/nominatim/, https://developers.google.com/maps/documentation/geocoding/policies, https://github.com/maplibre/maplibre-gl-js. Nominatim license mix (GPL-3.0-or-later Python, GPL-2.0 other files, Apache-2.0 Lua): https://github.com/osm-search/Nominatim.

**Depends on:** D04 (GPL isolation), D11, D13, D15, D17, D22, D26, D41.

**Door:** one-way for the class enum and the applicability-profile concept (ADR 0016); two-way for the class list contents, map stack and geocoder.

**Evidence that would change it.** NetBox adding a native location class (would let the projection become lossless and might argue for adopting their vocabulary); a design partner whose closets do have drawings (would raise the default for `telecom_room` to "geometry optional"); TIA-606-D publication changing the identifier grammar.

---


#### Round-3 corrections to D67 (from `Addendum B corrections` C.1; where these differ from the text above, these win)

1. **Row, Aisle, Cage are not SpaceClass values (gap 14; conflict with D50).** D50 wins. `Row`, `Aisle` and the colo cage (a `TenantAllocation` boundary) remain distinct objects. `SpaceClass` applies to `Location` only; `row`, `aisle` and `cage` are removed from the enum. Cage-like *spaces* in a data hall that are not tenant boundaries are `Location` with class `computer_room` or `data_hall` nested under the hall. ResourcePools attach to Locations, Rows and Racks via the existing ltree; RLS is unaffected.
2. **OSM data license (gap 21).** Nominatim's *data* is OpenStreetMap under ODbL. Whether persisted geocoded coordinates and their export in the site bundle constitute an ODbL derivative database is sent to counsel alongside Icecat (D45). Until answered: CSV-supplied latitude/longitude is the **default** onboarding path; geocoding is an explicit opt-in per tenant with the ODbL attribution string stored on each geocoded Location; the map view shows OSM attribution when the basemap is OSM-derived. The Compose profile documents the extract size and import time as **estimates** (country extracts on the order of single-digit to tens of GB and one to several hours; a planet import is out of scope). The 300-closet exit criterion assumes CSV coordinates, not a live geocoder.
3. **Second WebGL context (gap 22; conflict with D14/D35).** The map view is a **separate route** in `unum-twin` (`/map`), never mounted beside the three.js scene; on the VDI/iGPU presets the map falls back to a static basemap image with SVG pins. The D14/D35 Phase 0 spike adds a map-route test on the class-VDI preset.
4. **Standards mapping is editorial.** The equivalences `telecom_room` ≈ TIA-942 HDA/IDA and `main_telecom_room` ≈ MDA/ENI/MD are presented as editorial vocabulary choices, not standards statements; the docs carry that caveat.
5. **Crosswalk (gap 20).** Added to the D22 mapper list: `Client → NetBox/Nautobot Tenant` (and `TenantGroup` = MSP Organization), `SpaceClass → Nautobot LocationType` (lossless), `SpaceClass → NetBox custom field` (lossy), `SpaceClass → Nlyte LocationGroups` (**UNVERIFIED** whether LocationGroups carries a type; D32 gate), `SpaceClass → dcTrack LOCATION type` (**UNVERIFIED** type fidelity), `SpaceClass → ServiceNow cmn_location_type`. A **Hudu adapter** (pull companies/assets, push inventory summaries) is scheduled as an optional Phase 3 read-first adapter; the MSP funnel claim is reworded to "Hudu is the most accessible integration target for MSP documentation; an adapter is Phase 3 and conditional on an MSP design partner."

## B.3 Multi-client (MSP) operation (requirement 6b)

### D68 MSP tenancy model, client scoping, portals, rollups, offboarding

**Area:** security and tenancy (D25/D25b), export bundle (D44), API tokens (D23), MCP grants (D73).

**Why it matters.** An MSP managing inventories for many clients needs one console with cross-client rollups *and* a contractual guarantee that client A never sees client B. D25 already makes Organization the hard boundary with a tenant column and RLS, and reserves schema-per-tenant for MSPs. The question is whether a client is an Organization (strong isolation, hard rollups and offboarding) or a partition inside the MSP's Organization (easy rollups, isolation carried entirely by RLS discipline). ServiceNow's domain separation shows the cost of choosing a schema-irreversible model.

**Options and strongest objection.**

| Option | Strongest objection |
|---|---|
| N1. `Client` entity beneath an MSP Organization: every record in MSP mode carries `client_id`; RLS policies key on (`tenant_id`, `client_id`); MSP staff span clients | Isolation depends on every code path applying the client filter (lists, dropdowns, exports, imports, API, MCP); Snipe-IT and GLPI show this is where bugs concentrate; RLS bypass paths (owner without FORCE, BYPASSRLS, FK probes) must be closed. |
| N2. Client = full Organization; MSP gets an "umbrella" role across Organizations | Cross-client rollups become cross-tenant queries that RLS is designed to forbid; offboarding is trivial but every shared object (library sidecar, MSP staff, shared dock) must be duplicated per client. |
| N3. Schema-per-tenant (django-tenants) per client | Migration time linear in client count, catalog bloat at thousands of schemas, hostname-based resolution conflicts with a single MSP console, cross-client reporting requires cross-schema SQL. |
| N4. Instance-per-client (Compose/Helm per client) | No rollups; the MSP runs N installs; acceptable only when data residency forces it. |

**Recommendation.** N1 as the default MSP model, N4 retained for residency-driven cases, N3 reserved for hard-isolation packaging of a single client that later becomes its own Organization (with the D44 bundle as the migration path), N2 rejected.

- **Enforcement stack:** mandatory `tenant_id` and (in MSP mode) `client_id` columns; `ENABLE` + `FORCE ROW LEVEL SECURITY` on every tenant table; the application connects as a **non-owner** role with no `BYPASSRLS`; migrations run as the owner in a separate connection; composite `(id, tenant_id)` foreign keys (django-multitenant's `TenantForeignKey` pattern) so cross-client references fail at the schema level for client-scoped tables and at the policy level for shared tables (D77, correction C.1 D68 item 1); `pgrls`-style lint in CI plus per-client isolation tests (every list/search/export/import/API/MCP endpoint executed as client A must return zero client-B rows); BI/OData roles are non-owner and tenant-scoped (D58). Library `django-rls` (BSD-3) vendored or ported, not depended on at runtime.
- **Scoping semantics (Snipe-IT/GLPI pattern):** client filter applied to lists, search, dropdowns, exports, imports, REST, GraphQL, OData/SQL views and MCP tools; MSP-staff users may hold grants for several clients and see the union; MSP superusers see all; a location-client consistency check rejects placing a client-B asset in a client-A rack.
- **Client-scoped credentials:** D23 tokens and D73 MCP grants carry an explicit client/site scope independent of the user's full permission set (NetBox tokens cannot); reuse the D25b site-scoped collector lease mechanism; per-client vendor and ServiceNow credentials in the per-tenant envelope-encrypted store.
- **Client portal and branding:** Phase 2 read-only client portal (their sites, racks, assets, capacity, reports, exports) on the same RBAC; Phase 3 branding limited to logo, colours and one domain per Organization (IT Glue's MyGlue is logo-only; the branding scope stands on cost grounds alone (correction C.4 item 15)); SSO per client via the platform's OIDC/SAML federation.
- **Cross-client rollups:** MSP-only dashboards over ResourcePool (D71) and metering (D69) with the client as the top hierarchy level in `hierarchicalforecast` reconciliation.
- **ServiceNow in MSP mode:** one connection profile per client (instance URL, OAuth client, discovery-source name, `core_company` filter) supporting both one-instance-per-client and one shared instance; IRE does not require `sys_domain` in the payload (the CI's domain defaults to the integration user's domain), so run one domain-scoped integration user per client on domain-separated instances; `sysparm_query_no_domain` needs a special role and is never used by default.
- **Offboarding:** a per-client subset of the D44 `unumdcim-site` bundle plus CSV, a **freeze → export → purge** state machine honoring the D59 audit retention (audit rows pseudonymized, not deleted), and a "client became its own Organization" path that replays the bundle into a new tenant.
- **Reversibility:** MSP mode is a per-install feature flag that can be switched off (clients collapse into the Organization) and the `client_id` column can be dropped by a migration; this is deliberately stronger than ServiceNow domain separation, which can be disabled but never removed.

**Rationale.** PostgreSQL RLS semantics and bypass paths: https://www.postgresql.org/docs/current/ddl-rowsecurity.html (confirmed). Library options: https://github.com/kdpisda/django-rls, https://github.com/citusdata/django-multitenant, https://github.com/django-tenants/django-tenants, https://github.com/pgrls/pgrls. Scoping precedents: https://snipe-it.readme.io/docs/multi-tenancy-ish, https://help.glpi-project.org/documentation/modules/administration/entities, https://docs.device42.com/administration/role-based-access-control/. ServiceNow domain separation (disable-able, not removable; request-gated; sys_domain behavior): https://www.servicenow.com/docs/csh?topicname=c_DomainSeparation.html&version=latest, https://www.servicenow.com/docs/r/washingtondc/platform-security/domain-sep-plugin.html. MSP documentation-tool patterns (companies as root, per-client export, API on all plans vs Enterprise-only): https://www.hudu.com/pricing, https://help.itglue.kaseya.com/help/Content/1-admin/it-glue-api/getting-started-with-the-it-glue-api.html (three regional endpoints US/EU/AU), https://help.itglue.kaseya.com/help/Content/5-myglue/using-myglue/myglue-faq.html. Sensor-level colo access as a UX precedent: https://hyperviewhq.com/blog/sensor-level-access-control-a-game-changer-for-colocation-providers/.

**Depends on:** D10, D23, D25, D25b, D44, D58, D59.

**Door:** one-way for the `Client` entity, FORCE RLS and the non-owner role (ADR 0017); two-way for portal scope and branding.

**Evidence that would change it.** A design partner requiring per-client data residency inside one install (pushes toward N4/instance-per-region); an isolation-test failure rate in Phase 1 that shows N1's discipline cost exceeds N2's duplication cost; a legal requirement for cryptographic separation per client (would add per-client envelope keys, already supported by D25b, or force N3).

---


#### Round-3 corrections to D68 (from `Addendum B corrections` C.1; where these differ from the text above, these win)

1. **Schema-level claim downgraded (gap 15).** The composite `(id, tenant_id)` key blocks cross-*tenant* references only. Cross-*client* references inside an MSP tenant are prevented by (a) composite `(id, tenant_id, client_id)` keys on the client-scoped tables listed in D77, and (b) RLS `WITH CHECK` policies keyed on `client_id`, plus the isolation test suite. The sentence "cross-client references fail at the schema level" is replaced by "cross-client references fail at the schema level for client-scoped tables and at the policy level for shared tables."
2. **Shared vs scoped inventory and session mechanism (gap 16).** See D77.
3. **Offboarding vs audit retention (gap 17; conflict with D59).** See D77 (per-client audit chain).
4. **Monitor-store scoping (gap 44; conflict with D58).** `unum-monitor` series and alarms carry `tenant` and `client` labels from the collector lease (D25b); portal and MCP reads of telemetry go through core-issued, client-scoped tokens that the monitor validates by introspection; the isolation suite includes monitor reads and SSE streams. D58 is amended.
5. **TenantAllocation vs Client (gap 19; conflict with D50).** A `TenantAllocation` references a `Party`, and `Client` is a `Party` with MSP scoping enabled. A colo tenant that also needs a portal is therefore a `Client` with `scoping = portal_only` (RLS filters the portal, not MSP staff). `ResourcePool.contracted` lives on `TenantAllocation` and rolls up to the `Party`. D71's contracted-capacity placement is updated to match.
6. **Precedent wording.** Hudu "unlimited companies" and "per-client export" are re-labeled **UNVERIFIED** in the rationale; the MSP-precedent argument rests on Snipe-IT, GLPI and Device42, which are verified. The generalization "full white-label is not the norm" is withdrawn; the branding scope (logo, colours, domain) stands on cost grounds alone.

### D69 MSP metering unit and billing views (revises D57)

**Area:** business model (D07/D57), reporting (D54).

**Why it matters.** D57 planned per-cabinet pricing below Sunbird's $19.50/cabinet/month anchor. A closet-heavy MSP estate breaks that: a one-cabinet IDF is not worth a hall cabinet, and MSPs need a unit they can pass through to their own clients. Choosing the unit after the first customers are billed is a customer-visible repricing.

**Options and strongest objection.**

| Option | Strongest objection |
|---|---|
| B1. Per managed asset (racks, PDUs, UPS, cooling units, servers, network devices, patch panels; cables, blanking panels and components excluded), per-client rollup, per-site-class weight | Hyperview already uses per-asset and pairs it with a 500-asset floor that is hostile to single closets; asset counts fluctuate with discovery. |
| B2. Per cabinet, RU-weighted (Sunbird's unpublished quarter-rack terms since dcTrack 8.0) | A wall cabinet with one switch still pays a rack-based fee; fractional quarter-rack licensing exists since dcTrack 8.0 and is not on the public price page (correction C.4 item 12) rather than copy. |
| B3. Per site with class tiers (hall, room, closet) | Rewards dense halls and punishes small rooms; hard to explain when a site straddles classes. |
| B4. Per user (Hudu/IT Glue) | Facilities tools have few named users and many read-only consumers; punishes portals. |

**Recommendation.** B1 published *before* the D57 per-cabinet trigger fires, with: a published (not negotiated) small-site weight table (closet-class assets at 0.25 of a hall asset, illustratively), an **MSP-level** aggregate floor rather than per-client or per-site minimums, and a monthly metering snapshot exposed per client through the read-only OData/SQL views (D23/D58) so MSPs can invoice pass-through. The core remains free; metering applies to the Supported tier and any `ee/` entitlement. Offline Ed25519 license files (D07) carry the unit and weights; expired licenses degrade `ee/` to read-only and never block the core.

**Rationale.** Sunbird list price and rack-based licensing: https://www.sunbirddcim.com/pricing (verification: fractional quarter-rack licensing exists since dcTrack 8.0 but is unpublished). Hyperview $3/asset/year, 500-asset minimum, billable/non-billable asset lists, per-rack add-ons: https://hyperviewhq.com/pricing/. Hudu per-user ("unlimited companies" and per-client export UNVERIFIED from primary pages, correction C.4 item 1): https://www.hudu.com/pricing. Uptime 2025 density data (most estates low-density) supports asset counts over cabinet counts as the value proxy: https://datacenter.uptimeinstitute.com/rs/711-RIA-145/images/2025.Annual.Survey.Report.pdf.

**Depends on:** D07, D57, D58, D68.

**Door:** two-way until published; one-way in practice after the first invoice.

**Evidence that would change it.** MSP design-partner interviews (founder question 18) preferring per-site or per-client units; a competitor publishing a small-site unit that resets buyer expectations.

---


#### Round-3 corrections to D69 (from `Addendum B corrections` C.1; where these differ from the text above, these win)

1. **Deciding factor and draft table (gap 18).** The unit prices *operational effort per managed asset*, and the site-class weight exists because the same asset in a closet consumes less support and integration effort than in a hall (fewer power chains, no floor geometry, no CFD). Draft table, published before the first invoice: `data_hall`/`computer_room`/`micro_edge_dc` assets weight 1.0; `server_room` 0.5; `telecom_room`/`main_telecom_room`/`equipment_room`/`entrance_facility`/`telecom_enclosure` 0.25; stockroom/dock assets 0.1. Floor: **MSP-level** aggregate of 500 weighted assets; no per-client or per-site minimum.
2. **Which tier uses which unit (gap 18; conflict with D57).** Weights apply to the **Supported tier** (effort pricing). `ee/` entitlements are licensed per Organization with an unweighted asset count band, because the entitlement buyer is portfolio management, not operations. D57 is revised (C.2 item 3).
3. **Sunbird wording.** "Negotiated case by case" is replaced by "fractional quarter-rack licensing exists since dcTrack 8.0 and is not on the public price page."

## B.4 Hardware receiving and onboarding (requirement 7)

### D70 Asset lifecycle, procurement objects, receiving dock, first-power hooks (extends D11/D30/D46/D50/D51)

**Area:** data model, workflow, technician PWA, monitoring hooks, sync projections.

**Why it matters.** Every incumbent has a receiving story (Nlyte Receiving, dcTrack install requests, NetBox Labs' commercial Asset Lifecycle); none of it is open. Receiving is also where identity is born (serial, asset tag, MAC), where ServiceNow HAM and vendor ASNs meet the twin, and where demand becomes committed capacity. D50 placed a `ReceivingRecord` in the schema without a state machine; this decision supplies it and separates the physical unit from its placement so an asset can exist before, between and after placements.

**Options and strongest objection.**

| Option | Strongest objection |
|---|---|
| A1. Two objects: `Asset` (serialized unit with a procurement lifecycle) and `Device` (placement/role); installation links them and syncs serial/asset tag | Two records per server doubles the surface for sync mappers; NetBox has only Device, so the NetBox projection collapses `Asset` into Device fields plus optional netbox-inventory objects. |
| A2. Lifecycle states on `Device` only (NetBox `status` extended) | Cannot represent an asset in a stockroom without inventing a fake placement; spares and RMAs have no home; ServiceNow's `alm_hardware` vs `cmdb_ci` split cannot be mirrored. |
| A3. Adopt NetBox Labs' Asset Lifecycle objects as the model | Commercial-only (GA 2026-06-30 on NetBox Cloud and Enterprise Premium; no public repo, no PyPI, license unpublished); data model reset at v0.3.0 shows it is still volatile. |

**Recommendation.** A1, with the procurement objects below and peer enums as projections.

- **Canonical Asset state machine:** `planned` (BOM line, no serial) → `ordered` (PO line) → `inbound` (ASN/expected serial) → `received` (dock scan) → `in_stock` {`available`, `reserved`, `defective`, `quarantine`, `pending_install`, `pending_transfer`} → `staged` (burn-in/ZTP; BMC reachable) → `installed` {`active`, `powered_off`, `off_site`, `offline`, `failed`, `in_maintenance`} → `decommissioning` → `retired` {`disposed`, `sold`, `donated`, `vendor_credit`, `lease_return`, `returned`}; orthogonal `in_transit` (TransferOrder) and `missing` {`lost`, `stolen`}; `rma` as a sub-flow (Pending → Shipped to Vendor → Received by Vendor → Under Investigation → Approved/Rejected → Completed, per the CESNET plugin). Transition triggers: PO create, ASN import, dock scan, QA inspection, reservation to a ChangeRequest, WorkOrder completion, discovery confirmation (never auto-promote, D51), ServiceNow CI status change, decommission request, disposal completion. Every transition is an append-only audit event (D59).
- **Projections (editable mapping tables per peer):** NetBox `Device.status` (planned, inventory, staged, active, offline, failed, decommissioning); ServiceNow `alm_hardware` State (7 hardware values: On order, In stock, In transit, In use, In maintenance, Retired, Missing; Build is not a hardware state) + substate, with `install_status`/`hardware_status` via the customer's `alm_asset_ci_state_mapping`/`alm_hardware_state_mapping` tables and CSDM life-cycle stage via the separate `life_cycle_mapping`; dcTrack Planned/Installed{Powered On, Powered Off, Off-Site}/Storage/Archived; Hyperview `assetLifecycleState` (planned, procurement, inventory, staging, active, retired). Ship defaults; tolerate unknown peer values by parking them in a discrepancy.
- **Procurement objects (D11 additions):** `Supplier`, `PurchaseOrder` + `POLine`, `Shipment` (ASN) + `ShipmentLine` (expected serials, SSCC-18, carrier/tracking), `ReceivingRecord` + `ReceivingLine` (received vs expected quantity, damage flag and photos, short-ship, receiver, timestamp, dock location, pallet id), `StockLocation` as SpaceClass `dock`/`staging`/`burn_in`/`stockroom` (D67) rendered in the twin as non-rack bins with occupancy counts, `TransferOrder`, `DisposalOrder`, `RMA`, `SupportEntitlement`/`Warranty` with provenance and `license_id`. ASN importer is format-agnostic: X12 856 (HL S/O/T/P/I; `PRF` PO reference; `MAN*GM` SSCC-18; `REF*2I` tracking; `LIN`/`SN1` per line; one `REF*SE` per serialized unit), reseller portal CSV, or emailed packing-list CSV.
- **Dock identity (extends D46):** serial 1.0 > asset tag 0.9 > MAC 0.8; ASN/CSV pre-creates `inbound` assets; unknown serial quick-creates into `in_stock/quarantine`; reject → RMA/return; per-manufacturer label parsing rules (Dell service tag vs PPID, HPE CT, Cisco SN/PID) with a confidence prompt on ambiguous scans.
- **Receiving dock UI:** lands in the technician PWA (D30) with HID scanner input first, camera scanning second (html5-qrcode Apache-2.0 for QR/2D, quagga2 MIT for 1D), offline queue, MSP client selector for shared docks (each ReceivingLine assigned to a client at scan time; the MSP tenant owns the record and the client sees it). Functions: search by PO, PR, cost center, pallet, serial, asset tag, RFID tag, asset name; batch mode; expected-vs-received reconciliation with gap highlighting; confirm/reject; receiving-location override; over/short quantities; asset-tag entry and label printing (netbox-qrcode-style templates per D30); "reserved for" a Project/ChangeRequest; immediate downstream trigger (WorkOrder or staging task). The data model, importers and REST API land in Phase 1 so ServiceNow HAM pulls and CSV receipts work before the PWA exists; a minimal desktop receiving form ships in Phase 1 for design partners.
- **Workflow linkage (D30/D12):** BOM lines derive from planned (ghost) objects in the twin; reserving a received asset to a ChangeRequest satisfies the WorkOrder's "materials on hand" gate; staged placement is a ChangeRequest intent; installation closes the intent, confirms the placement (owner system) and flips the NetBox/ServiceNow projections; quarantine/burn-in has an optional checklist (firmware baseline, Redfish inventory captured, LLDP verified) configurable as a gate before reservation (open question 11 in the research).
- **Vendor entitlement connectors (D17/D19 fetch-recipe pattern, customer-credentialed, per-client for MSPs):** Dell TechDirect Warranty API (OAuth client credentials, ≤ 100 service tags per query); Cisco SN2INFO v2 (≤ 75 serials per call; SNTC customers or PSS partners only); Lenovo `supportapi.lenovo.com` (rep-issued ClientID); HPE: request-only `api-gw.support.hpe.com` warranty check and the GreenLake COM beta (servers already onboarded), otherwise manual CSV. Degrade gracefully when credentials are absent; record `SupportEntitlement` with provenance and fetch time.
- **First-power hooks (`unum-monitor`, Phase 2):** SSDP listener for Redfish services (`ST: urn:dmtf-org:service:redfish-rest:1`, optional on BMCs, so also a DHCP-lease/MAC watcher on staging VLANs); read `SerialNumber`/`SKU`/`UUID`/`Manufacturer`/`Model` (read-only properties), match to the `inbound`/`in_stock` asset, propose `staged`; write `AssetTag` (writable, alongside `HostName`) to the BMC only after an approved WorkOrder under D25b's second-role approval. LLDP neighbor capture (SNMP LLDP-MIB or the agent's Chassis ID/Port ID/System Name, the fields Ironic uses for `local_link_connection`; not the Port Description TLV) proposes rack/ToR placement into the discrepancy queue, never auto-promoted (D51). Restrict listeners to staging VLANs; treat auto-enroll as a DoS vector (Ironic's own warning).
- **ZTP:** UnumDCIM exposes `staged` as the trigger status (NetBox planned → staged → active gate; Ironic enroll → manageable → available verbs as the vocabulary) for external ZTP/PnP/Ironic systems and does not implement ZTP itself.
- **RFID:** Phase 3 collectors for RF Code-style active tags and generic EPC Gen2 reader webhooks; tag ids stored as identifiers on the Asset; no promise of RFID-driven auto-placement.
- **Demand linkage (D71):** `on_order`, `inbound`, `received-not-installed` and `reserved` quantities with their model's typical W, U and weight are committed demand on the relevant ResourcePools.

**Rationale.** Nlyte Receiving fields and batch semantics: https://www.nlyte.com/web/wp-content/uploads/2019/09/nlyte-receiving.pdf. dcTrack statuses and install-request gate: https://www.sunbirddcim.com/help/dcTrack/v710c/en/Content/dcTrack/Item_and_Connection_Statuses.htm, https://www.sunbirddcim.com/help/dcTrack/v600/en/Content/dcTrack/Asset_Lifecycle_and_Workflow.htm. ServiceNow states, receiving, transfer and disposal orders: https://www.servicenow.com/docs/r/it-asset-management/asset-management/t_SettingAssetStatesAndSubstates.html, https://www.servicenow.com/docs/bundle/xanadu-it-asset-management/page/product/procurement/task/t_ReceiveAnAsset.html, https://www.servicenow.com/docs/bundle/yokohama-it-asset-management/page/product/asset-management/concept/transfer-orders-for-am.html, https://www.servicenow.com/docs/bundle/yokohama-it-asset-management/page/product/hardware-asset-management/reference/hardware-disposal-stages.html (verification: the "predefined asset/CI state" infocard is community-authored; cite the docs pages). NetBox statuses: https://raw.githubusercontent.com/netbox-community/netbox/main/netbox/dcim/choices.py. NetBox Labs Asset Lifecycle commercial-only, GA 2026-06-30: https://netboxlabs.com/blog/asset-lifecycle-public-preview/, https://netboxlabs.com/blog/netbox-asset-lifecycle-ga/. Reusable OSS models: https://github.com/ArnesSI/netbox-inventory/blob/master/README.md (MIT), https://github.com/sol1/netbox-inventory-plus (MIT), https://github.com/CESNET/inventory-monitor-plugin (Apache-2.0). Hyperview lifecycle enum: https://docs.hyperviewhq.com/redoc-static.html. X12 856 structure: https://www.insight.com/content/dam/insight/en_US/pdfs/insight/support/edi/insight-edi-vendor-856-guidelines.pdf (confirmed). Redfish writable properties and SSDP: https://redfish.dmtf.org/schemas/v1/ComputerSystem.v1_1_0.json (verification: current schema v1_28_0; `HostName` also writable; SSDP optional). Ironic states, auto-discovery caveats and LLDP fields: https://docs.openstack.org/ironic/latest/user/states.html, https://specs.openstack.org/openstack/ironic-inspector-specs/specs/lldp-reporting.html (ironic-inspector retired; in-tree inspection now). Vendor APIs: https://www.dell.com/support/contents/en-us/article/product-support/self-support-knowledgebase/technologies-and-tools/techdirect/self-dispatch-and-apis, https://developer.cisco.com/docs/support-apis/serial-number-to-information/, https://pubs.lenovo.com/lxca/support_viewwarranty. Scanner libraries: https://github.com/mebjas/html5-qrcode (Apache-2.0), quagga2 (MIT). RFID integration precedent: https://www.rfcode.com/blog/optimize-nlyte-dcim-integration-rf-code-centerscape.

**Depends on:** D11, D12, D17, D19, D25b, D30, D41, D46, D50, D51, D59, D65, D67, D68, D71.

**Door:** two-way for states and UI; one-way for the Asset/Device split (schema and every mapper depend on it).

**Evidence that would change it.** A design partner running HAM Pro mobile receiving (dock UI becomes pull-only); NetBox Labs publishing a stable public API for BOM/PO/Shipment (adds mapper targets); Dell/Cisco/Lenovo terms found to forbid MSP third-party queries (connectors become client-run recipes only).

---


#### Round-3 corrections to D70 (from `Addendum B corrections` C.1; where these differ from the text above, these win)

1. **Asset granularity (gap 23).** `Asset.parent` is added. A serialized child unit (blade, module, PSU, line card, optic) is its own `Asset` linked on install to a `Module` or `InventoryItem` in the NetBox projection. `ReceivingLine.kind ∈ {serialized, quantity}`: serialized lines create N `Asset` rows matched by expected `REF*SE` serials (parent-child by `HL` nesting when the ASN provides it); quantity lines increment `Part/Spare` stock at the receiving `StockLocation` (D50). `Part/Spare` and `Asset` never both represent the same unit: an item becomes an `Asset` the moment it carries a serial.
2. **Nlyte projection (gap 25).** A mapping row `Nlyte Asset Status/Sub-Status` (Planned Procurement/Received, Planned, Installed, Storage, Decommissioned; **UNVERIFIED** enumeration) is added, and the enumeration probe joins the D32 gate.
3. **First-power listener and BMC credentials (gap 26).** See D79.
4. **EDI parser (gap 27).** The X12 856 importer is an in-house minimal segment reader (ISA/GS/ST envelopes; HL, PRF, TD5, REF, MAN, LIN, SN1 segments; configurable delimiters) under Apache-2.0 in `unum-core`; no third-party EDI library is adopted (pyx12/badX12 license and maintenance status not vetted). The reader is on the D04 allowlist check as first-party code.
5. **Attachments (gap 28).** See D78.
6. **Cisco pagination.** "may paginate at 50" is re-labeled **UNVERIFIED**.
7. **Reverse receipt.** Covered in D65 correction 2.

## B.5 Demand and forecast management (requirement 8)

### D71 Demand and forecast data model, capacity ladder, resource types, algorithms, OpenDC integration (extends D43, D29/D56)

**Area:** capacity (D43), simulation (D29), telemetry rollups (D28), workflow (D30), colo/MSP allocations (D11 TenantAllocation).

**Why it matters.** Incumbents converge on a small set of primitives: a capacity ladder (rated → budgeted → reserved → measured), project reservations that expire or release on planned decommission, "days of supply" runway charts, what-if placement and stranded-capacity views. None offers a structured demand-request intake; that lives in ServiceNow SPM. Uptime's 2025 survey shows forecasting concern rising (36% very concerned, up nine points since 2023) while most estates are low-density and slow-moving, so transparent simple models win over ML. The founder calls this a key requirement, which forces the open-core resolution in D72.

**Options and strongest objection.**

| Option | Strongest objection |
|---|---|
| F1. Explicit objects (ResourcePool, Reservation, DemandRequest, Forecast, Runway, Scenario) on a full capacity ladder; statistical ladder in the Django worker; deterministic planned overlay | More schema and more UI than incumbents' base tiers; a wrong exhaustion date shown without bands erodes trust. |
| F2. Extend the D43 triplet with a linear trend and no demand intake | Below dcTrack's base product (reservations with expiry, project what-if); no MSP/colo contracted-vs-drawn view. |
| F3. Push forecasting into the TelemetryStore (Timescale Toolkit `stats_agg` slope/x-intercept) | Toolkit is under the Timescale License and not in the built-in hyperfunction subset; PostgreSQL-partition and ClickHouse backends would have no equivalent. |
| F4. ML-first (Darts/GluonTS/foundation models) | Sparse, step-like series; PyTorch in the reference install; foundation-model weights carry separate licenses; nothing to "show the math" with. |

**Recommendation.** F1, with F3 as an optional accelerator behind the `ForecastEngine` interface and F4 confined to `ee/` per D72.

- **ResourcePool:** one per node of the power, cooling, space, port, IP and compute hierarchies, attached to the ltree tree so rollups and reconciliation reuse it; carries `resource_type`, `rated`, derating policy (continuous-load factor default 0.8 for breakers, N/N+1/2N/A-B redundancy, cooling aging factor, site diversity default 0.7), and for colo/MSP clients `contracted` capacity via `TenantAllocation`.
- **Resource types (enum):** `space_u`, `floor_area_m2`, `tiles`, `floor_load_kg`, `weight_kg` (per rack), `power_kw` and `power_a` per phase/leg at every power-chain node (PowerSource, PowerNode, PanelExtension/Breaker, PowerFeed, outlet), `cooling_kw` per CoolingUnit/zone, `ports_copper`, `ports_fiber`, `cross_connects`, `ip_addresses` per Prefix, `vcpu`, `ram_gb`, `storage_tb`, `bandwidth_gbps`.
- **Capacity ladder per pool (replaces the D43 triplet as the display model; the triplet remains the storage primitive):** rated → usable (after derating and redundancy) → committed (installed allocated + contracted) → reserved (soft pipeline, firm approved) → planned (approved ChangeRequest intents with in-service and decommission dates) → measured (telemetry) → budgeted (policy-derived from measured: default p95 over 8 weeks + 10% margin, refreshed weekly; fallback to a similar-model profile, then nameplate × 0.6; implemented independently of Sunbird's patent-pending Auto Power Budget with a freedom-to-operate note in the ADR). Stranded capacity is reported both ways: budgeted − measured (Sunbird's definition) and usable − max(committed, planned) across coupled pools (space, power, cooling) to expose the unbalanced-resource case.
- **Reservation:** hardness (soft/firm/committed), quantity per resource type, optional exact placement (rack + U range, outlet, port), start and expiry with auto-release (dcTrack 6.1 pattern), release-on-planned-decommission date, holder (DemandRequest, Project, TenantAllocation); auto-created from planned devices and ChangeRequest intents so planned-state evaluation (D30) and capacity checks share one source.
- **DemandRequest:** client-scoped intake (Organization/Client): business driver (project, application, program), requested quantities per resource type or "N racks of profile X", location constraints, need-by date, term (colo), priority, probability (pipeline weighting), state machine Draft → Submitted → Screening → Qualified → Approved → Reserved → Fulfilled → Closed, with Deferred and Rejected; ExternalReference to `dmn_demand` (D65); approval creates Reservations and a Project/ChangeRequest.
- **Forecast:** method, horizon, p10/p50/p90 points, model parameters, training-window hash, deterministic planned overlay; stored in a `forecast_points` hypertable/partition with retention; computed in the Django worker behind `ForecastEngine`.
- **Runway:** per pool and threshold (warning at a configurable %, hard at usable): exhaustion-date band, days remaining, procurement lead time per resource type (configurable defaults documented as estimates, e.g., shipped only as labeled placeholders (the ~128-week transformer figure is secondary and is removed from defaults, correction C.4 item 11); UNVERIFIED), alert when exhaustion − lead time falls inside the horizon; surfaced as twin badges, reports and MCP tools.
- **Scenario:** baseline plus hypothetical demands, decommissions, policy changes (redundancy, derating) and build-outs; compared per pool; OpenDC (D29 tier 3) is invoked from a Scenario for the three sanctioned questions (annual energy/carbon by hall, host consolidation, availability under a failure prefab) with the Scenario's planned devices projected into OpenDC topology; results land as Forecast points labeled "simulation" and are gated by the D56 MAPE criterion. The deterministic web-worker sim (tier 2) evaluates a Scenario's power-chain feasibility instantly (breaker/UPS headroom) before any statistical forecast.
- **Algorithm ladder (all permissive; no deep learning in the reference install; "show the math" panel always):** time-weighted daily/weekly aggregates from D28 rollups → OLS trend with prediction interval and x-intercept against usable (statsmodels, BSD-3, default) → damped Holt/ETS or Theta when ≥ 2 seasons of history (statsmodels/statsforecast AutoETS/AutoTheta) → conformal intervals (statsforecast `ConformalIntervals`, needs `n_windows × h` < series length, so unavailable for new sites and shown as such) → Croston/TSB for intermittent request arrivals → hierarchical MinTrace reconciliation across rack → row → room → site and client → site (hierarchicalforecast, optional until a few hundred pools) → probability-weighted deterministic overlay from the demand pipeline with Monte Carlo exhaustion bands. Rejected: Prophet (maintenance mode, Stan), NeuralProphet (beta since June 2024), Timescale Toolkit as default.
- **Colo/MSP:** `TenantAllocation` gains `contracted` per resource; pools track contracted vs committed vs drawn so per-client runway, overage alerts and sellable-capacity views exist; a rate-plan model (committed kW flat, metered kWh, per circuit) is deferred to `ee/` revenue analytics.
- **Vocabulary and standards:** ITIL 4/5 "capacity and performance management" (demand management is not an ITIL 4 practice); ISO/IEC 30134-2:2026 (PUE, replaced 2016 edition on 16 January 2026), -6:2021 ERF, -7:2023 CER, -8:2022 CUE, -9:2022 WUE; EN 50600-4-x "almost identical"; this closes the D55 open question on part numbers.

**Rationale.** Vendor primitives: https://www.sunbirddcim.com/product/data-center-capacity-management, https://www.sunbirddcim.com/blog/introducing-dctrack-61, https://www.sunbirddcim.com/sites/default/files/FB003_Sunbird_FAQ_poweriq-features-and-benefits_9_1.pdf, https://www.sunbirddcim.com/sites/default/files/DS022_Sunbird_DataSheet_Auto_Power_Budget.pdf, https://www.sunbirddcim.com/help/dcTrack/v700/en/Content/dcTrack/Bulk_Update_Power_Budget.htm, https://www.sunbirddcim.com/glossary/data-center-capacity-planning, https://www.nlyte.com/solutions/nlyte-placement-and-optimization-ai/, https://www.nlyte.com/solutions/colocation-solution/, https://www.fntsoftware.com/en/products/fnt-command/c-logic/data-center-cockpit, https://www.device42.com/use-cases/capacity-planning/, https://www.ekkosense.com/resources/industry-insight/how-to-find-stranded-capacity-in-data-centers/. Schneider folded Capacity into a unified per-rack module in IT Advisor 10.0 (June 2026), so "capacity is a paid add-on" is no longer an industry norm (verification of https://shop.se.com/pro/us/en/product/subscription-ecostruxure-it-advisor-capacity-module-saas-1-year-10-racks/). Market: https://datacenter.uptimeinstitute.com/rs/711-RIA-145/images/2025.Annual.Survey.Report.pdf (confirmed). Libraries: https://pypi.org/project/statsmodels/, https://github.com/Nixtla/statsforecast, https://nixtlaverse.nixtla.io/statsforecast/docs/tutorials/conformalprediction.html, https://github.com/Nixtla/hierarchicalforecast, https://github.com/facebook/prophet, https://github.com/ourownstory/neural_prophet/releases, https://github.com/timescale/timescaledb-toolkit, https://www.tigerdata.com/docs/learn/hyperfunctions/about-hyperfunctions (all confirmed). ITIL and ISO: https://itsm.tools/34-itil-4-management-practices/, https://www.peoplecert.org/browse-certifications/it-governance-and-service-management/ITIL-1, https://ucsiso.com/iso-iec-30134-2/, https://webstore.iec.ch/en/publication/75152 (confirmed). SPM demand states: https://www.servicenow.com/community/spm-forum/understanding-demand-management-in-servicenow-spm-end-to-end/m-p/3544948 (disputed: states configurable since Australia).

**Depends on:** D10 (TelemetryStore), D11, D28, D29, D30, D43, D55, D56, D65, D68, D70.

**Door:** two-way for algorithms and thresholds; one-way for the ResourcePool/Reservation objects once the public API ships.

**Evidence that would change it.** A design partner's series proving that ETS beats OLS on ≥ 70% of pools at 12-week horizon (would change the default rung); OpenDC failing the D56 gate (Scenario keeps only tiers 1 and 2); legal advice that the budgeting policy is too close to Sunbird's claims (would switch to a different percentile scheme).

---


#### Round-3 corrections to D71 (from `Addendum B corrections` C.1; where these differ from the text above, these win)

1. **Series sources and cross-service read (gap 29; conflict with D58).** See D80. In brief: the **inventory-derived series** (committed and planned per pool per day, reconstructed from the change log) is the default input for every pool; measured series from `unum-monitor` are an additive input when present, read through a new bulk rollup endpoint.
2. **Minimum history and seasons (gap 30).** No statistical forecast below **8 weekly aggregates**; below that the runway panel shows "insufficient history; planned overlay only" with the deterministic exhaustion date from committed + planned. Season is defined per resource: weekly (7 days) for power/cooling measured series; annual (52 weeks) for inventory-derived series (budget cycles), which makes ETS with seasonality effectively unavailable for most sites before year two. A **segmented trend** option (fit on the last window after the most recent step, step detection by a simple change-point test on weekly deltas) is the default for step-like inventory series; plain OLS is used for measured series.
3. **Committed formula (gap 31).** `committed(pool) = Σ_tenant max(installed_allocated_t, contracted_t) + installed_allocated_untenanted`. Overage is reported separately as `drawn_t − contracted_t` per tenant.
4. **Hierarchical reconciliation (gap 33).** The summing structure is a **grouped** cross-sectional matrix (site × client, then row and rack beneath site) rather than a tree; cooling pools are excluded from strict additive reconciliation and are reported as constraints (min over the containing zone), as are floor-load and weight pools.
5. **Lead-time defaults.** The transformer figure (~128 weeks) is removed from shipped defaults; the shipped table contains **placeholders** labeled "example, replace with your supplier's quote", and the docs cite no external lead-time source until a primary source is captured.
6. **Demand push.** Mirror-only in v1 (D65 correction 4).

### D72 Open-core boundary resolution for demand/forecast (revises D05)

**Canonical open-core rule (one form; identical in README.md, ADR 0004 and 00-walkthrough.md D05).** Free forever (Apache-2.0 core): twin, library, all ingestion and sync connectors, OIDC/SAML/LDAP, MFA, SCIM 2.0, object and field-level RBAC, change log, webhooks, OpenDC integration, air-gap install, LTS releases, single-Organization demand and forecast management (ResourcePool, Reservation, DemandRequest, Runway, Scenario, runway with intervals, headroom dashboards, alerts, ServiceNow demand mirror, MSP client and site rollups within one Organization), and the MCP server with all its tools. FSL tier (`ee/`, FSL-1.1-Apache-2.0, each version converts to Apache-2.0 on its second anniversary): multi-Organization portfolio rollups (cross-tenant aggregation), ML auto-model selection and ensembles, AI placement optimization, portfolio Monte Carlo, procurement-lead-time optimization, colo revenue analytics with rate plans, audit-event streaming, hosted control plane, certified-connector packaging, extended-support backports. The core is never relicensed. The text below is the design pass's reasoning toward this rule; where wording differs, the canonical rule above wins.


**Area:** open-core promise (D05), `ee/` scope, D07 pricing.

**Why it matters.** D05 placed "forecasting and AI placement" in the FSL `ee/` tier. The founder now names demand and forecast management a key requirement, and dcTrack ships days-of-supply and project reservations in its base product. An OSS DCIM without runway and reservations would rank below incumbents' base tiers, which contradicts the parity contract (D03). The boundary must be resolved before the README publishes the open-core rule.

**Options and strongest objection.**

| Option | Strongest objection |
|---|---|
| O1. Everything demand/forecast in core; `ee/` keeps only the hosted control plane and audit streaming | Removes the one analytic product line that could fund the project before support revenue matures. |
| O2. Single-site primitives and statistical runway in core; portfolio/ML/AI-placement/revenue analytics in `ee/` | The line "single-site vs portfolio" can look arbitrary; an MSP with one site per client may feel fenced. |
| O3. Keep D05 as written (forecasting in `ee/`) | Fails the founder's requirement; core would lack dcTrack-base features; community perception of "core is a viewer". |

**Recommendation.** O2, published as ADR 0015 and in the README before v1:

- **Core (Apache-2.0, free forever):** ResourcePool, Reservation (with expiry and decommission release), DemandRequest (intake and states), Forecast, Runway, Scenario objects and APIs; the full statistical ladder (OLS, ETS/Theta, conformal, Croston/TSB, hierarchical reconciliation) for any number of pools within an Organization; headroom and stranded-capacity dashboards; exhaustion-date and lead-time alerts; Scenario comparison for a single Organization including OpenDC runs; ServiceNow demand sync; every MCP tool that reads or proposes these objects; colo contracted-vs-drawn views.
- **`ee/` (FSL-1.1-Apache-2.0, converts after two years):** multi-Organization portfolio executive forecasting (cross-tenant rollups for holding companies, not MSP client rollups, which are core per D68); ML auto-model selection and ensembles (sktime/Darts/GluonTS/foundation models); AI placement optimization (Nlyte Placement & Optimization class); Monte Carlo scenario comparison at portfolio scale; procurement-lead-time optimization; colo sellable-capacity and revenue analytics with rate plans; plus the unchanged items (audit-event streaming, hosted control plane, certified-connector packaging, extended-support backports).
- **Rule for future features:** a feature is core if an incumbent ships it in a base per-rack product or if a single facilities operator needs it to run one estate; it may be `ee/` only if its buyer is portfolio management, finance or a hosted-service operator.

**Rationale.** dcTrack base features: https://www.sunbirddcim.com/blog/introducing-dctrack-61, https://info.sunbirddcim.com/hubfs/DS009_Sunbird_DataSheet_dcTrack9_2.pdf; Schneider's 2026 move to a unified module (verification of the shop URL above); Nlyte's AI placement as a distinct premium capability: https://www.nlyte.com/solutions/nlyte-placement-and-optimization-ai/. Open-core comparables and backlash risk are in D05 and risk 12.

**Depends on:** D03, D05, D06, D07, D71.

**Door:** one-way promise once published (features can move from `ee/` to core, never the reverse).

**Evidence that would change it.** Founder question 4 (paywall owner) answered "IT management/compliance pays" would not move these items back but could add compliance packs to `ee/`; a community fork triggered by the boundary would argue for O1.

---


#### Round-3 corrections to D72 (from `Addendum B corrections` C.1; where these differ from the text above, these win)

- The D05 plan body is rewritten (C.2 item 1) so that the only forecasting fence is **multi-Organization portfolio rollups**, defined as cross-tenant aggregation. MSP multi-site and multi-client rollups within one Organization are core.

## B.6 MCP server (requirement 9)

### D73 MCP placement, protocol version, transport, SDK, authorization and tenant scoping

**Area:** API surface (D23), security and tenancy (D25, D68), stack (D09), deployment (D26).

**Why it matters.** AI assistants must reach the system directly, safely, per tenant and per client, from clients that today straddle two protocol eras (2026-07-28 stateless vs 2025-06-18/2025-11-25 session-based). The authorization server choice decides whether the bundled air-gap IdP (Keycloak, D25) can issue MCP tokens at all. Getting the placement wrong (a sidecar with its own ORM copy) doubles the security surface; getting the auth wrong (token passthrough to ServiceNow/Nlyte) violates the spec's hard ban.

**Options and strongest objection.**

*Placement.*

| Option | Strongest objection |
|---|---|
| L1. In-process ASGI sub-app mounted at `/mcp` in `unum-core` | The Python SDK's `session_manager.run()` lifespan and in-process legacy sessions constrain worker topology (sticky routing or `stateless_http=True`). |
| L2. Separate `unum-mcp` service sharing the database | Second deployment unit, second RLS-connection configuration, duplicated ORM and permission code; more places for the tenant filter to be missed. |
| L3. Separate service over the REST API only (no ORM) | Clean, but every tool becomes an HTTP hop with token exchange, and MRTR/Tasks state must be stored twice. |

*Protocol.*

| Option | Strongest objection |
|---|---|
| V1. 2026-07-28 with dual-era serving of 2025-11-25 and 2025-06-18 | Legacy clients require in-process `Mcp-Session-Id` sessions. |
| V2. 2026-07-28 only | Locks out ServiceNow AI Agent Studio (2025-06-18), Claude.ai connectors (auth specs through 2025-11-25) and Copilot Studio. |
| V3. 2025-11-25 only | Claude Code v2 runtime and the ecosystem are moving; Roots/Sampling/Logging/DCR are formally deprecated. |

*Authorization server.*

| Option | Strongest objection |
|---|---|
| Z1. django-oauth-toolkit 3.4+ as the platform AS (RFC 8707, 9728, 8414, 7591/7592, 9207, CIMD, PKCE) federating to the customer's IdP | Its MCP RFC stack landed July/August 2026 and is untested at scale; RFC 9207 `iss` and S256-only PKCE are opt-in flags until 4.0. |
| Z2. Bundled Keycloak as AS | Stock Keycloak rates RFC 8707 "Not supported" and MCP 2025-06-18+ "Partially Supported"; the `resource-indicators` and `cimd` feature flags are experimental (26.6/26.7) and do not cover CIMD clients until 26.8. |
| Z3. Static API keys only | Fails the spec's OAuth 2.1 MUST for HTTP transports; no per-client scoping or step-up. |

*SDK.*

| Option | Strongest objection |
|---|---|
| K1. Official Python SDK v2 (`mcp` 2.x, MIT) | Weeks old (2.2.0 on 2026-09-07); Tasks extension support server-side must be confirmed. |
| K2. FastMCP 4 (Apache-2.0) on top of SDK v2 | Extra abstraction layer and release coupling; but ships Tasks, OAuthProxy/OIDCProxy, JWTVerifier, ID-JAG today. |
| K3. django-mcp-server (MIT) | Written against the mcp 1.x/FastMCP API and the 2025-03-26 transport model; last release 2025-10-10; would need a rewrite. |
| K4. mcp-django | Dev-time introspection shell, explicitly not for production. |

**Recommendation.** L1 + V1 + Z1 + K1 (K2 adopted only if Tasks/OAuthProxy/ID-JAG are needed before the official SDK exposes them; K3/K4 rejected).

- **Mount:** `MCPServer.streamable_http_app()` mounted under the Django ASGI app so the canonical RFC 8707 resource URI is `https://<instance>/mcp`; host lifespan enters `session_manager.run()`; `TransportSecuritySettings(allowed_hosts=[...])` set from the instance's configured hostnames; CORS allows `Mcp-Method`, `Mcp-Name`, `MCP-Protocol-Version`, `Mcp-Session-Id`; `Origin` validated (403 on mismatch). Streamable HTTP only; never HTTP+SSE; stdio only through an optional local developer proxy. Legacy-era sessions served with `stateless_http=True` by default (elicitation to legacy clients then raises `NoBackChannelError`, so legacy clients get handle-plus-poll tools instead) or, where an operator needs legacy elicitation, a single-replica MCP deployment with sticky routing documented in the Helm chart.
- **Authorization:** the MCP endpoint is an OAuth 2.1 **resource server**: `TokenVerifier` validates opaque DOT-issued access tokens by in-process database lookup (D81; the earlier JWT wording is withdrawn, correction C.4 item 5) (audience must equal the canonical `/mcp` URI; RFC 8707 resource validated; `iss` per RFC 9207), publishes RFC 9728 metadata at `/.well-known/oauth-protected-resource/mcp`, returns 401 with `resource_metadata` and `scope`, and 403 `insufficient_scope` for step-up. The AS is django-oauth-toolkit 3.4+ (BSD-2-Clause, verified) with `PKCE_REQUIRED`, `COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS=True`, S256-only, CIMD enabled with a trust policy (enterprise installs allowlist known client-metadata domains such as Claude, OpenAI and Microsoft plus the customer's own), DCR enabled for backward compatibility (deprecated in the spec; earliest removal ≥ 2027-07-28), pre-registered clients supported, short-lived access tokens (≤ 1 h) with rotated refresh tokens for public clients. DOT federates to the customer's OIDC/SAML/LDAP (D25); the bundled Keycloak stays the air-gap IdP behind DOT and becomes eligible as the MCP AS only when a stable release supports RFC 8707 and CIMD together (targeted 26.8). Token passthrough forbidden: ServiceNow, Nlyte and NetBox lookups use server-held per-tenant credentials, never the caller's token. M2M for `unum-monitor` and collectors via the `io.modelcontextprotocol/oauth-client-credentials` extension (Phase 3) or ordinary REST until then.
- **Tenant and client scoping:** Organization, Client and site grants are claims in the token (scope strings `org:<id>`, `client:<id>`, `site:<id>`, plus capability scopes); every tool takes an explicit `org` (and `client` in MSP mode) argument annotated `x-mcp-header: Org`/`Client` so clients mirror it as `Mcp-Param-Org`/`Mcp-Param-Client` for gateway routing, per-org rate limits and audit; the server rejects any org/client outside the token's grants; `tools/list`, `resources/list` and `prompts/list` are filtered by scope and returned with `cacheScope: "private"`; `unum.org.list` enumerates accessible orgs/clients for MSP users. No cross-call state without a server-minted, user-bound handle re-authorized on each call.
- **Scopes (least privilege, step-up via challenges):** `mcp:inventory.read`, `mcp:capacity.read`, `mcp:forecast.read`, `mcp:twin.read`, `mcp:change.propose`, `mcp:change.apply` (off by default, admin-granted), `mcp:receiving.propose`, `mcp:sync.read`, `mcp:sync.trigger`; `scopes_supported` advertises only the read baseline.
- **Observability:** propagate `_meta` `traceparent`/`tracestate` into OpenTelemetry spans (`opentelemetry-api` is already a hard dependency of `mcp` v2); log deprecated-feature use.
- **Licensing:** `mcp` (MIT), FastMCP (Apache-2.0) if adopted, django-oauth-toolkit (BSD-2-Clause) are all inside the D04 allowlist; the MCP server ships in the Apache-2.0 core (D74).

**Rationale.** Spec revision, transport, authorization and deprecations: https://modelcontextprotocol.io/specification/latest/changelog, https://blog.modelcontextprotocol.io/posts/2026-07-28/, https://modelcontextprotocol.io/specification/2026-07-28/deprecated, https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http, https://modelcontextprotocol.io/specification/latest/basic/authorization, https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/client-registration, https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations, https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning (confirmed). SDK: https://py.sdk.modelcontextprotocol.io/migration/, https://py.sdk.modelcontextprotocol.io/run/asgi/, https://py.sdk.modelcontextprotocol.io/run/legacy-clients/ (verification: cite legacy-clients and whats-new for the dual-era and auth assertions). FastMCP 4: https://gofastmcp.com/changelog. django-mcp-server: https://pypi.org/project/django-mcp-server/ (verification: not "stuck", but written against mcp 1.x). DOT changelog: https://django-oauth-toolkit.readthedocs.io/en/latest/changelog.html; license verified BSD-2-Clause at https://raw.githubusercontent.com/jazzband/django-oauth-toolkit/master/LICENSE. Keycloak status (experimental `resource-indicators` since PR #46763; CIMD behind `--features=cimd`; full support targeted 26.8) per the verification notes. Client requirements: https://code.claude.com/docs/en/mcp, https://claude.com/docs/connectors/building (240 s timeout, ~150k chars), https://developers.openai.com/api/docs/mcp, ServiceNow client 2025-06-18 tools-only: https://www.servicenow.com/community/now-assist-articles/enable-mcp-and-a2a-for-your-agentic-workflows-with-faqs-updated/ta-p/3373907.

**Depends on:** D09, D23, D25, D26, D68.

**Door:** one-way for placement in `unum-core` and the resource-server/AS split (ADR 0018); two-way for SDK choice and legacy-session topology.

**Evidence that would change it.** Keycloak 26.8 shipping supported RFC 8707 + CIMD (Z2 becomes viable for air-gap installs); the official SDK gaining Tasks server-side (removes the FastMCP option); ServiceNow's client adopting 2026-07-28 (dual-era serving can be retired after the deprecation window).

---


#### Round-3 corrections to D73 (from `Addendum B corrections` C.1; where these differ from the text above, these win)

1. **Token format and grant encoding (gap 35).** See D81. Summary: **opaque** django-oauth-toolkit access tokens validated in-process by the `TokenVerifier` (DB lookup; introspection endpoint reserved for future external resource servers); Organization/Client/site grants are **not** scopes; they are resolved at verification time from the user's RBAC grants and displayed on the consent screen; only capability scopes are OAuth scopes. "Validates DOT-issued JWTs" is withdrawn.
2. **DCR and CIMD defaults (gap 36; conflict with D26/D37).** Enterprise/air-gap default: DCR **off** (or enabled only with an initial access token issued by an admin); CIMD **off** unless an egress allowlist of client-metadata domains is configured; **pre-registered clients** are the default. Cloud-connected installs may enable CIMD with the allowlist (Anthropic, OpenAI, Microsoft, the customer's own domains). Both are added to risk 29 and to the hardening guide.
3. **Legacy-session claim.** The assertion that `stateless_http=True` serves elicitation-free 2025-06-18 tools is re-labeled "per the SDK's legacy-clients page; behavior to be confirmed in the Phase 0 dual-era spike."
4. **Reachability (gap 37).** See D81 reachability matrix.
5. **Tasks in the official SDK.** The K1-only recommendation is conditional: the Phase 0 spike probes server-side Tasks support in `mcp` 2.x; if absent, FastMCP 4 is adopted for Phase 2 (K2), and the ADR records the trigger.

### D74 MCP tool catalog, resources, prompts, annotations, audit, prompt-injection defenses, roadmap, open-core placement

**Area:** API surface (D23), ownership and intents (D12/D30/D47), audit (D59), forecast (D71/D72), receiving (D70), sync (D63).

**Why it matters.** The tool catalog is the contract AI assistants and ServiceNow agents will build on; annotations decide what a client auto-approves; every write path is a route around the ownership model unless it is an intent. DCIM records carry free text from Nlyte, NetBox and ServiceNow, which makes tool results an injection channel unless structured and labeled.

**Options and strongest objection.**

| Option | Strongest objection |
|---|---|
| G1. Read tools plus write tools that only create ChangeRequest intents; `apply` behind a separate scope, elicitation and out-of-band approval | Slower "agentic" demos; an agent holding `mcp:change.apply` could still approve its own proposal unless approval is enforced outside MCP. |
| G2. Direct CRUD tools (NetBox Cloud Platform MCP style) | Violates placement-as-one-fact (D12) and OwnershipPolicy; no human gate; one prompt injection away from a rack move. |
| G3. Read-only only (netbox-mcp-server, Nautobot official) | Fails the requirement to "engage with the system", which includes proposing changes and receipts. |

**Recommendation.** G1.

- **Naming and annotations:** `unum.<domain>.<verb>`, deterministic order (prompt caching), 1 to 128 chars of `[A-Za-z0-9_.-]`; reads `readOnlyHint=true`, `openWorldHint=false`; writes `readOnlyHint=false`, `destructiveHint=false` (additive intents only), `idempotentHint=true` with a required `idempotency_key`; `title`/`description` static, versioned, reviewed in CI; `outputSchema` derived from typed return values with the text form also populated.
- **Catalog.** Inventory: `unum.inventory.search` (cross-object, `fields=`, cursor), `.list`, `.get`, `.changelog`, `.provenance` (owner system, source, last sync per field), `.trace` (power/network/cable path). Capacity: `unum.capacity.summary` (site/room/row/rack: U, kW, cooling, weight, ports), `.find_space` (constraints → candidate positions), `.power_chain`, `unum.runway.get`. Demand and forecast (core per D72): `unum.demand.list`, `.propose` (intent), `unum.forecast.list_scenarios`, `.get`, `.run` (Tasks), `unum.scenario.compare`. Twin: `unum.twin.deep_link`, `.snapshot` (render → `resource_link`; Tasks if slow), `.view_state` (server-minted, user-bound handle). Change intents: `unum.change.propose_placement`, `.propose_move`, `.propose_decommission`, `.propose_field_update` (OwnershipPolicy enforced: fields owned by Nlyte, NetBox or ServiceNow produce a staged value plus a logged discrepancy override under `mcp:discrepancy.override`, never a canonical write (D12 wins; correction C.1 D74 item 4)), `.list`, `.get`, `.submit`; `unum.change.execute` (renamed from `apply`; correction C.1 D74 item 7) only executes an intent already approved by a different principal in the UI or by the ServiceNow change gate, behind `mcp:change.execute`, with a form-mode elicitation that confirms execution but does not constitute approval and `_meta["anthropic/requiresUserInteraction"]=true`, and the approval itself is recorded by a different principal than the proposer (D25b second-role rule), so an agent cannot approve its own proposal. Receiving: `unum.receiving.list_shipments`, `.propose_receipt` (serial/asset tag/PO → intent), `.match_devicetype`, `.status`. Sync and ServiceNow: `unum.sync.status`, `.discrepancies`, `.trigger` (Tasks), `unum.servicenow.lookup_ci` (server-held credentials). Org: `unum.org.list`. ChatGPT compatibility aliases `search` and `fetch` (read-only, `id/title/url` and `id/title/text/url/metadata` shapes).
- **Resources:** custom scheme per RFC 3986 with RFC 6570 templates: `unum://org/{org}/site/{site}`, `.../site/{site}/rack/{rack_id}`, `unum://org/{org}/device/{device_id}`, `.../site/{site}/capacity/summary`, `unum://org/{org}/forecast/{scenario_id}`, `unum://org/{org}/change/{cr_id}`, `.../site/{site}/twin/scene.glb` (blob), `unum://org/{org}/library/devicetype/{slug}`; `https://` deep links only where the client can fetch them; change and sync resources subscribable via `subscriptions/listen`; all list/read results carry `ttlMs` and `cacheScope: "private"`.
- **Prompts (user-controlled, with argument completion):** `capacity-review`, `rack-audit`, `receiving-checklist`, `forecast-brief`, `discrepancy-triage`.
- **Long-running work:** `io.modelcontextprotocol/tasks` for forecast runs, sync triggers and renders; `unum.task.get` handle-plus-poll fallback for clients without the extension; synchronous tools kept under Claude.ai's 240-second per-call timeout; results capped below client limits (25k tokens Claude Code by default, ~150k characters Claude.ai) with `fields=` and cursor pagination as the escape.
- **Safety and audit:** no tool mutates canonical state directly; every `tools/call` and `resources/read` audited with `sub`, `client_id`, org/client, request UUID and `traceparent` in the D59 append-only log; MRTR `requestState` AEAD-protected and bound to `sub`, TTL and request digest, single-use where it gates authorization; elicitation form mode never for secrets, URL mode for anything credential-related, and elicitation bound to the token's `sub`, never client-supplied identity; external free text (names, comments, descriptions from Nlyte/NetBox/ServiceNow) returned inside `structuredContent` under a `data` key with a `source` label and never in tool descriptions or instructions; tool descriptions static and diffed in CI; `notifications/tools/list_changed` and a version bump on any catalog change so clients re-approve; per-token and per-org rate limits with 429; input validation and output sanitization per the spec's tool-security MUSTs; a published safety policy citing OWASP MCP Tool Poisoning and the MCPTox findings (36.5% average description-poisoning success), with re-approval on config change, allowlists and credential isolation.
- **Interoperability:** publish `server.json` (`com.unumsol/unumdcim`, templated `streamable-http` remote) to the MCP Registry once it leaves preview; document tested clients: Claude Code v2 runtime (2026-07-28; DCR, CIMD, pre-registered OAuth), Claude.ai/Desktop connectors (`oauth_dcr`, `oauth_cimd`, `custom_connection`; loopback and `https://claude.ai/api/mcp/auth_callback` redirects), ChatGPT `search`/`fetch` with CIMD, Copilot Studio (Streamable HTTP, tools + resources, OAuth DCR/manual), VS Code, Cursor, ServiceNow AI Agent Studio (2025-06-18, tools only; resources support for the Universal MCP Client UNVERIFIED (verifier notes disagree; correction C.4 item 14), prompts not supported). Any ServiceNow-facing flow must work with tools alone.
- **Precedents:** netbox-mcp-server (Apache-2.0; `netbox_get_objects`, `netbox_get_object_by_id`, `netbox_get_changelogs`, `netbox_search_objects`; field filtering as a token budget pattern) for the inventory read shape; NetBox Labs' governed writes ship as "NetBox Agents" (public preview 2026-08-27, SaaS), not as MCP; Nautobot's official server is commercial and read-only; ServiceNow's MCP Server Console (Zurich P9/Australia P2; Now Assist SKUs; OAuth 2.0 authorization code with CIMD from ZP7/AP1; no client credentials or DCR; writes governed by ACLs/roles and optionally AI Control Tower) plus out-of-the-box ITSM/ITOM/CMDB/SPM MCP servers reportedly GA 2026-09-10 (UNVERIFIED verifier note, no URL; correction C.4 item 7), so a UnumDCIM MCP server can be consumed by ServiceNow agents and a ServiceNow-facing tool set need not depend on the customer's Now Assist entitlement.
- **Roadmap:** Phase 1 read-only inventory, capacity, runway and twin tools plus prompts and `search`/`fetch`; Phase 2 change-intent, demand, receiving and sync tools with elicitation confirmations and Tasks; Phase 3 MCP Apps rack/heat-map viewer (`io.modelcontextprotocol/ui`, Apache-2.0; three.js example server exists), enterprise-managed authorization (ID-JAG) and the client-credentials extension for `unum-monitor`.
- **Open-core placement:** the MCP server, all read tools, change-intent tools, receiving tools and the core demand/forecast tools are Apache-2.0 core; only tools over `ee/` objects (portfolio forecasting, AI placement) live in `ee/` and appear in `tools/list` only when the entitlement is present.

**Rationale.** Tools, annotations, resources, pagination, caching, `_meta`, MRTR and elicitation: https://modelcontextprotocol.io/specification/latest/server/tools, https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2026-07-28/schema.ts, https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr, https://modelcontextprotocol.io/specification/latest/client/elicitation, https://modelcontextprotocol.io/specification/latest/server/resources, https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching, https://modelcontextprotocol.io/specification/2026-07-28/basic, https://modelcontextprotocol.io/specification/latest/basic/security_best_practices. Extensions: https://modelcontextprotocol.io/docs/extensions/overview, https://modelcontextprotocol.io/extensions/client-matrix. Precedents: https://github.com/netboxlabs/netbox-mcp-server, https://docs.nautobot.com/projects/nautobot-mcp-server/en/stable/faq/, https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-opens-its-full-system-of-action-to-every-AI-Agent-in-the-enterprise/default.aspx, https://www.servicenow.com/community/servicenow-otto-articles/mcp-server-console-faq/ta-p/3550125, https://github.com/jschuller/mcp-server-servicenow (MIT reference for a 2026-07-28 FastMCP 4 server with CIMD). Poisoning guidance: https://owasp.org/www-community/attacks/MCP_Tool_Poisoning. Client constraints: https://code.claude.com/docs/en/mcp, https://claude.com/docs/connectors/building, https://developers.openai.com/api/docs/mcp.

**Depends on:** D12, D25b, D30, D47, D59, D70, D71, D72, D73.

**Door:** two-way for catalog contents (versioned); one-way for "writes are intents" (follows from D12).

**Evidence that would change it.** Founder question 16 answered "never apply via MCP" (removes `unum.change.apply`); a client ecosystem shift where resources/prompts become universally supported (would let ServiceNow-facing flows use resources); a Registry GA with durability guarantees (moves `server.json` publication into Phase 1).

---


#### Round-3 corrections to D74 (from `Addendum B corrections` C.1; where these differ from the text above, these win)

1. **Injection controls (gap 38).** Labeling is not a control; the following are added: per-field allowlists via `fields=` with a conservative default field set per object type (identifiers, class, placement, numeric capacity; free-text `description`/`comments` excluded unless requested); length caps on any free-text field returned (default 512 characters, truncated with a marker); stripping of control characters, zero-width characters and known instruction-pattern prefixes from external free text; an opt-in **"names only" mode** per sync peer for peers the operator marks untrusted; and a written statement in the safety policy that residual tool-result injection risk is accepted and logged, since clients do not validate descriptions.
2. **Tasks state (gap 39).** Task records live in PostgreSQL under RLS, bound to `(tenant_id, client_id, sub)` and a random 128-bit `taskId`; `tasks/get`, `tasks/cancel` re-authorize against the presented token's subject and grants; TTL default 24 hours, results retained 7 days then purged; mirrors the MRTR `requestState` rules.
3. **`unum.sync.trigger` (gap 40).** Restricted to **pull** runs and dry-run diffs; write-back (push) is never triggerable through MCP and runs only from the UI/CLI under D47.
4. **Override scope (gap 41; conflict with D12).** D12 wins. `unum.change.propose_field_update` on an externally owned field produces a **staged value plus a logged discrepancy override** (D12 semantics), never a canonical write; the scope is renamed `mcp:discrepancy.override` and the tool result states which system owns the field.
5. **Missing tools (gap 42).** Added to the Phase 2 catalog: `unum.telemetry.latest` (readOnly), `unum.alarms.list` (readOnly), `unum.alarms.acknowledge` (intent; acknowledgement is recorded as proposed-by-agent and confirmed by a user in the UI or by elicitation on clients that support it), `unum.cabling.trace` (readOnly), `unum.library.search` (readOnly), `unum.circuits.list` (readOnly).
6. **`unum.twin.snapshot` (gap 43).** Scoped to the D54 SVG/PDF exporter (plan, elevation, rack views from scene data); 3D renders are deferred and a headless-renderer sidecar is not part of the reference install.
7. **Second-principal approval (conflict with D25b).** The MCP `unum.change.apply` tool is renamed `unum.change.execute` and only executes an intent that has **already been approved by a different principal in the UI or by the ServiceNow change gate**; elicitation confirms execution, it does not constitute approval. An intent proposed by principal P cannot be approved by P through any surface, including a second MCP session; the check is on the intent record, not the session.
8. **Now Assist licensing split (gap 10).** UnumDCIM calling ServiceNow REST needs no Assist consumption. ServiceNow AI Agents calling UnumDCIM's MCP need Now Assist Pro Plus/Enterprise Plus and consume Assists per call. Both statements appear in risk 21 and the docs.
9. **Unverified citations.** "Out-of-the-box ITSM/ITOM/CMDB/SPM MCP servers GA 2026-09-10", "Role Masking mandatory on Australia", and "Universal MCP Client resources support from June 2026" are marked **UNVERIFIED (verifier note, no URL)**; the roadmap does not depend on ServiceNow resources support in either direction.

---

## B.7 Roadmap amendments with exit criteria

**Phase 0 (months 0 to 3) additions.**
Schema: `SpaceClass` enum with applicability profiles (D67); `Client` entity, `client_id` column, FORCE RLS policies, non-owner app role, composite FKs (D68); `Asset`/`Device` split and procurement objects (D70); `ResourcePool`/`Reservation` (D71); ExternalReference targets for ServiceNow tables (D63/D64). Spikes: ServiceNow PDI in CI with IRE payload fixtures and `/query` dry-run; django-oauth-toolkit 3.4 RFC 8707/9728/CIMD conformance spike; MCP dual-era spike (Claude Code v2 runtime on 2026-07-28 and a 2025-06-18 client such as the ServiceNow client or an SDK 1.x client) against the mounted `/mcp`; MapLibre with a bundled basemap in the twin shell; Nominatim container in the Compose reference (optional profile). Docs: open-core rule text updated per D72 before any public README; ADRs 0015 to 0019 drafted.
*Exit:* isolation test suite passes for two synthetic clients across every list/search/export/import/API endpoint; IRE dry-run round-trips a 100-CI payload (racks, PDUs, outlets, devices with relations) on the PDI with zero `maskedAttributes` under default rules; `/mcp` answers `server/discover` from a 2026-07-28 client and `initialize` from a 2025-06-18 client in one deployment with DOT-issued tokens; SpaceClass projects to a Nautobot `LocationType` fixture losslessly and to NetBox with a custom field in CI.

**Phase 1 (months 3 to 10) additions.**
ServiceNow pull (CMDB classes, `cmdb_rel_ci`, HAM, Change, `cmn_location`, `core_company`, models) and IRE push with the D47-extended safety protocol; inbound webhook endpoint with the documented Business Rule; Asset lifecycle with ASN/CSV importer and ServiceNow HAM slip import; minimal desktop receiving form; linear runway on the capacity ladder with prediction intervals and the "show the math" panel; MCP read-only tools, `search`/`fetch`, prompts; edge-site UX (rack list, elevation, procedural closet scene, map view); bulk site onboarding template with self-hosted geocoding; TIA-606-style identifier templates; MSP mode behind a flag with the client selector in every list.
*Exit:* a ServiceNow partner's CMDB racks, PDUs and devices render in the twin within one hour from a read-only integration user, and a confirmed placement in UnumDCIM appears in the partner's CMDB through IRE with `discovery_source = UnumDCIM` and no duplicate CIs after 30 days; a 300-closet CSV onboards in under 30 minutes with map pins and procedural scenes; a received asset (from CSV or a receiving slip) reaches `installed` via a ChangeRequest with the NetBox and ServiceNow projections flipped; Claude Code and one non-Anthropic client complete a capacity question and a rack lookup against `/mcp` with per-org scoping proven by a negative test.

**Phase 2 (months 10 to 20) additions.**
ServiceNow change attachment (`change_request`, `task_ci`, `change_task`, approval gating), Event Management alerts, SPM demand mirror; demand intake, reservations with expiry and decommission release, runway alerts with lead times, hierarchical reconciliation, Scenario comparison including OpenDC runs; MCP change-intent, demand, receiving and sync tools with elicitation and Tasks; MSP read-only client portal, per-client metering snapshots in OData/SQL views, per-client export; vendor entitlement connectors (Dell, Cisco, Lenovo; HPE CSV); first-power Redfish/LLDP hooks in `unum-monitor`; D69 metering unit published.
*Exit:* a MAC work order executes only after its ServiceNow change reaches Implement, and the change closes from UnumDCIM; a DemandRequest approved in UnumDCIM (or mirrored from `dmn_demand`) creates Reservations that move the runway date on the affected pools, and the runway alert fires when exhaustion − lead time enters the horizon on a partner's real series; an MSP operator sees a cross-client rollup while a client-portal user of client A cannot enumerate client B through UI, API, export or MCP (automated negative tests in CI); a Redfish-discovered server on a staging VLAN is matched to its `inbound` asset and proposed as `staged` without auto-promotion.

**Phase 3 (months 20 to 36) additions.**
Technician PWA receiving dock with HID/camera scanning, offline queue and label printing; RFID collectors; `ee/` portfolio forecasting, ML ensembles, AI placement, portfolio Monte Carlo, revenue analytics; MCP Apps viewer, ID-JAG enterprise-managed authorization, client-credentials extension for `unum-monitor`; per-client branding (logo, colours, domain); Store/SGC scoped app only on customer demand (D66); Keycloak-as-MCP-AS option if 26.8 ships supported RFC 8707 + CIMD.
*Exit:* a dock audit of one closet site is completed on the PWA offline and reconciled on reconnect with zero lost scans; at least one MSP runs UnumDCIM for ≥ 10 clients with pass-through billing from the metering views; an `ee/` customer runs portfolio forecasting across ≥ 3 Organizations; the MCP server is listed in the Registry and passes the published client matrix.

---

## B.8 New risks (21 to 32)

21. **ServiceNow licensing traps.** IntegrationHub free tier not guaranteed; SGC needs ITOM or ITAM SU SKUs; MCP Server consumes Assists and needs Now Assist SKUs; "Unrestricted User" counting unless the integration user is Web Service Access Only. *Mitigation:* D63 auth defaults, D66 posture, a per-customer licensing checklist in the docs.
22. **IRE gotchas.** Discovery source must be pre-registered; dependent CIs need parents in the same payload and cannot go through Import Sets; reconciliation rules silently mask writes; per-user hourly rate limits and the small `API_INT` pool throttle initial loads; the OOB `cmdb_rel_rollup` fights pushed rack totals. *Mitigation:* D41 staging, `/query` dry-run, `maskedAttributes` as provenance conflicts, "let ServiceNow roll up" default (D64).
23. **Bidirectional loops** between UnumDCIM and ServiceNow business rules. *Mitigation:* `sys_object_source_info`, `last_discovered`, `sys_updated_by` filtering, two-snapshot persistence.
24. **MSP cross-client leak** via RLS bypass paths (owner without FORCE, BYPASSRLS, FK/unique probes) or unscoped code paths (dropdowns, exports, imports, MCP). *Mitigation:* D68 enforcement stack, `pgrls` lint, per-release isolation tests, non-owner BI roles.
25. **Metering-unit collision** between per-cabinet (D57) and per-asset (D69). *Mitigation:* publish D69 first; MSP-level floor.
26. **Vendor entitlement API terms** may forbid MSP/third-party use; HPE's API is request-only. *Mitigation:* customer-credentialed recipes, per-client credentials, graceful degradation, CSV.
27. **Statistical over-claiming** on short, step-like series; conformal bands unavailable for new sites; Sunbird's patent-pending measured-budget method. *Mitigation:* bands and planned overlay always shown, "show the math", independent documented budgeting policy with a freedom-to-operate note.
28. **MCP protocol churn and tool poisoning.** 2026-07-28 shipped six weeks before this plan; SDK v2 and FastMCP 4 are weeks old; clients split across eras; DCIM free text is an injection channel. *Mitigation:* dual-era serving, pinned SDK, D74 safety rules, structured outputs, re-approval on tool-list change.
29. **Authorization-server immaturity.** DOT's RFC 8707/9728/CIMD landed July/August 2026; Keycloak's support is experimental. *Mitigation:* Phase 0 conformance spike, opt-in strict flags on, DOT pinned, Keycloak behind DOT until 26.8 is verified.
30. **GPL geocoder in the reference stack.** Nominatim (GPL-3.0-or-later Python, GPL-2.0 data files) must never be linked in-process. *Mitigation:* isolated container with an HTTP boundary, optional Compose profile, pluggable provider interface.
31. **Receiving-record ownership in MSP shared docks** (MSP tenant vs client tenant vs client's ServiceNow). *Mitigation:* MSP-owned ReceivingRecord with per-line client assignment and provenance shown side by side; OwnershipPolicy per client.
32. **Legacy MCP clients and elicitation.** `stateless_http=True` breaks elicitation for 2025-era clients, so approval flows differ by client. *Mitigation:* handle-plus-poll fallbacks, documented client matrix, approval enforced out-of-band regardless of client.

---

## B.9 Founder questions added (13 to 22)

13. **MSP unit of tenancy:** Client as a sub-organization inside the MSP Organization (recommended, D68 N1) or Client as a full Organization with an umbrella role?
14. **Per-client data residency** (EU vs US) inside one install? If yes, instance-per-region packaging.
15. **Does the design partner run ServiceNow HAM Pro and SPM?** Decides whether receiving slips, model normalization and `dmn_demand` exist on their side, and whether UnumDCIM masters or mirrors DemandRequest.
16. **MCP write policy:** `unum.change.apply` never via MCP (UI-only), or allowed with elicitation plus a second approver?
17. **Which MCP clients must be supported at launch** (Claude Code/Claude.ai, ChatGPT, Copilot Studio, ServiceNow AI Agent Studio)? Decides whether resources and prompts can be relied on for ServiceNow-facing flows.
18. **Metering unit MSPs will accept for pass-through billing:** per managed asset (recommended), per site, per client or per user; and the closet weighting.
19. **Which ServiceNow instance is the Phase 0 test target:** a Personal Developer Instance only, or a partner's sub-production instance with HAM/SPM/Class Models installed? The PDI lacks HAM Pro and SPM, so several D65 paths cannot be exercised without a partner.
20. **Should the closet-first technician workflow (audit and receiving on the PWA) move ahead of Phase 3** if an MSP design partner signs? It trades twin polish for edge-estate adoption.
21. **Budgeting policy defaults** (percentile, window, margin) and whether measured-load budgeting should be opt-in per tenant until the freedom-to-operate note is reviewed by counsel.
22. **ServiceNow CSDM 5 Facility Service Instances:** does any target customer model DCIM-managed rooms as Facility Service Instances? If so D64's `cmn_location` + `cmdb_ci_computer_room` mapping needs a CSDM layer.

---

## B.10 Fact sheet: newly verified facts (round 2, with URLs)

**ServiceNow**
- IRE REST endpoints `identifyreconcile`, `/enhanced`, `/query`, `/queryEnhanced`; caller needs `itil` or `asset`; `sysparm_data_source` must be an existing `cmdb_ci.discovery_source` choice; payload `items[]`/`relations[]`; response operations INSERT/UPDATE/NO_CHANGE/UPDATE_WITH_UPGRADE/UPDATE_WITH_DOWNGRADE. https://www.servicenow.com/docs/r/api-reference/rest-apis/c_IdentifyReconcileAPI.html
- IRE always updates `last_discovered`/`discovery_source`; `sys_object_source_info` (source_name, source_native_key) skips matching; dependent CIs need identified parents. https://github.com/ServiceNow/ServiceNowDocs/blob/australia/markdown/servicenow-platform/configuration-management-database-cmdb/ire.md
- Import Sets reach IRE via `CMDBTransformUtil.identifyAndReconcile`; one transform map; not for dependent CIs. https://github.com/ServiceNow/ServiceNowDocs/blob/australia/markdown/servicenow-platform/configuration-management-database-cmdb/identification-import-sets.md
- `sys_choice` does not extend `sys_metadata`, so a discovery source cannot ship as a scoped application file (fix script or admin step). https://www.servicenow.com/community/itom-forum/creating-discovery-source-via-scripts-from-application-scope/m-p/2681253
- Reconciliation rules are per class/attribute with per-source priority; masked writes return `maskedAttributes`. https://www.servicenow.com/community/cmdb-articles/understanding-ire-reconciliation-rules/ta-p/3289239
- Table API paging/query parameters, `X-Total-Count`, no multi-record insert, `sysparm_query_no_domain` role. https://www.servicenow.com/docs/bundle/zurich-api-reference/page/integrate/inbound-rest/concept/c_TableAPI.html
- Import Set API `insertMultiple`, string-only values. https://www.servicenow.com/docs/bundle/zurich-api-reference/page/integrate/inbound-rest/concept/c_ImportSetAPI.html
- Rate-limit rules per user/role/all, HTTP 429 with `Retry-After` and `X-RateLimit-*`. https://www.servicenow.com/docs/r/yokohama/api-reference/rest-api-explorer/inbound-REST-API-rate-limiting.html
- Batch API on the default semaphore pool; one transaction per session. https://www.servicenow.com/community/servicenow-ai-platform-articles/an-introduction-to-the-batch-rest-api-endpoint-api-now-batch/ta-p/2317136
- Base physical classes incl. `cmdb_ci_rack` with rack units / in use / power consumption, `cmdb_ci_pdu_outlet`, `cmdb_ci_crac`. https://www.servicenow.com/docs/r/servicenow-platform/configuration-management-database-cmdb/cmdb-tables-details.html
- CI Class Models container/panel classes. https://www.servicenow.com/docs/r/servicenow-platform/configuration-management-database-cmdb/cmdb-ci-class-model-list-of-classes.html
- Community rack-elevation pattern (custom RU fields + "Rack contains"); verification adds the OOB `cmdb_rel_rollup` (KB0788463) and TNI's licensed rack view. https://www.servicenow.com/community/cmdb-forum/tracking-racks-in-servicenow-as-cis-and-creating-relationships/m-p/3480774
- `cmn_location` parent hierarchy; docs mirror is Apache-2.0. https://github.com/ServiceNow/ServiceNowDocs/blob/australia/markdown/platform-administration/table-administration-and-data-management/data-hierarchies.md
- CSDM 5 white paper (May 2025). https://www.servicenow.com/community/common-service-data-model/csdm-5-finally-get-the-csdm-5-white-paper-here/ta-p/3254967
- SGCs built on IntegrationHub ETL, all use IRE, Store-delivered. https://blog.glidefast.com/what-are-service-graph-connectors-in-servicenow
- SGC entitlement via ITOM Visibility/Discovery SUs (and, per verification, ITAM SU SKUs). https://www.servicenow.com/community/itom-forum/service-graph-connector-entitlement/td-p/3245107
- IntegrationHub free transactions no longer guaranteed; Flow REST step needs IntegrationHub; `RESTMessageV2` does not. https://www.servicenow.com/community/servicenow-ai-platform-forum/do-we-need-any-licenses-for-integration-hub-etl/m-p/2703296
- MID Server outbound-only HTTPS 443. https://www.servicenow.com/community/itom-forum/mid-server-port-details-connection-between-instance-and-mid-and/m-p/2616197
- Event Management inbound `/api/global/em/jsonv2`, `evt_mgmt_integration`, `message_key`. https://www.rapdev.io/blog/send-test-events-to-servicenow-event-management-with-postman
- Change Management API paths and roles; affected CIs in `task_ci`. https://www.servicenow.com/docs/bundle/zurich-api-reference/page/integrate/inbound-rest/concept/change-management-api.html
- HAM tables, plugins, receiving slips per receipt, PO statuses. https://www.servicenow.com/community/ham-forum/essential-plugins-and-terminology-for-streamlined-hardware-asset/m-p/3239979; https://www.servicenow.com/docs/bundle/xanadu-it-asset-management/page/product/procurement/task/t_ReceiveAnAsset.html
- Asset states/substates; "You shouldn't modify state values". https://www.servicenow.com/docs/r/it-asset-management/asset-management/t_SettingAssetStatesAndSubstates.html
- Transfer orders and hardware disposal stages. https://www.servicenow.com/docs/bundle/yokohama-it-asset-management/page/product/asset-management/concept/transfer-orders-for-am.html; https://www.servicenow.com/docs/bundle/yokohama-it-asset-management/page/product/hardware-asset-management/reference/hardware-disposal-stages.html
- Model normalization is HAM Pro (`com.sn_hwnorm` with `sn_hamp`). https://www.servicenow.com/docs/r/yokohama/it-asset-management/hardware-asset-management/hardware-normalization.html
- Inbound OAuth client credentials (Washington DC+), Web Service Access Only guidance. https://www.servicenow.com/community/developer-blog/up-your-oauth2-0-game-inbound-client-credentials-with-washington/ba-p/2816891
- Release cadence and names (Zurich, Australia GA 2026-05-05, Brazil Q4 2026). https://snowcoder.ai/blog/servicenow-release-cycle-2026
- MCP Server press release 2026-05-05; MCP Server Console FAQ (Zurich P9/Australia P2, auth-code only, GET/POST/PUT). https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-opens-its-full-system-of-action-to-every-AI-Agent-in-the-enterprise/default.aspx; https://www.servicenow.com/community/servicenow-otto-articles/mcp-server-console-faq/ta-p/3550125
- AI Agent Studio MCP client: 2025-06-18, Streamable HTTP/SSE, no stdio, no prompts, Now Assist SKU, +1 assist per call. https://www.servicenow.com/community/now-assist-articles/enable-mcp-and-a2a-for-your-agentic-workflows-with-faqs-updated/ta-p/3373907
- Domain separation: disable-able, not removable; request-gated plugin. https://www.servicenow.com/docs/csh?topicname=c_DomainSeparation.html&version=latest; https://www.servicenow.com/docs/r/washingtondc/platform-security/domain-sep-plugin.html
- SPM demand lifecycle (default states; configurable since Australia). https://www.servicenow.com/community/spm-forum/understanding-demand-management-in-servicenow-spm-end-to-end/m-p/3544948
- Precedents: Nlyte Asset Sync ownership split https://www.nlyte.com/blog/master-your-assets-nlyte-servicenow-cmdb-integration/; Sunbird connector https://www.sunbirddcim.com/blog/how-data-center-experts-are-integrating-dcim-servicenow; NetBox Labs scoped app and v2.0 certification https://netboxlabs.com/docs/servicenow/.

**Edge and MSP**
- TIA-942-C (May 2024), µEDC, 5 kPa for rooms < 20 m². https://www.tiafotc.org/tia-standards-update/tia-942-c/; https://www.cablinginstall.com/standards/article/55245177/tia-942-c-data-center-standard-brings-a-host-of-changes-and-updates
- TIA-569-E (May 2019, E-1 June 2022). https://www.tiafotc.org/tia-standards-update/tia-569-e/
- TIA-606-C classes 1 to 4 and identifier grammar. https://www.cablinginstall.com/cable/article/14035166/tia-606-c-standard-requirements-for-cable-plant-administration
- ISO/IEC 11801 distributor vocabulary. https://en.wikipedia.org/wiki/ISO/IEC_11801
- NetBox Location fields (no type); RackType and form factors. https://netboxlabs.com/docs/netbox/models/dcim/location/; https://netboxlabs.com/docs/netbox/models/dcim/racktype/; https://raw.githubusercontent.com/netbox-community/netbox/main/netbox/dcim/choices.py
- NetBox tenancy and permission constraints; token limits. https://netboxlabs.com/docs/netbox/features/tenancy/; https://netboxlabs.com/docs/netbox/administration/permissions/
- Nautobot LocationType and Location. https://docs.nautobot.com/projects/core/en/stable/user-guide/core-data-model/dcim/locationtype/; https://docs.nautobot.com/projects/core/en/stable/user-guide/core-data-model/dcim/location/
- Device42 hierarchy and object permissions. https://docs.device42.com/infrastructure-management/buildings-rooms-and-racks/buildings-and-rooms/; https://docs.device42.com/administration/role-based-access-control/
- dcTrack hierarchy. https://www.sunbirddcim.com/help/dcTrack/v810/API/en/Content/dcTrack/dcTrack_Hierarchy.htm
- Closet-scale customer references. https://www.sunbirddcim.com/blog/how-does-dcim-software-support-edge-computing-it-closets-and-distributed-it-environments
- Sunbird pricing; Hyperview pricing and billable assets. https://www.sunbirddcim.com/pricing; https://hyperviewhq.com/pricing/
- Hyperview Location container and sensor-level access. https://docs.hyperviewhq.com/user-guide/layout-management/topics/location-layouts.html; https://hyperviewhq.com/blog/sensor-level-access-control-a-game-changer-for-colocation-providers/
- Hudu pricing; IT Glue API (Enterprise) and regional endpoints; MyGlue branding. https://www.hudu.com/pricing; https://help.itglue.kaseya.com/help/Content/1-admin/it-glue-api/getting-started-with-the-it-glue-api.html; https://help.itglue.kaseya.com/help/Content/5-myglue/using-myglue/myglue-faq.html
- Snipe-IT FMCS; GLPI entities. https://snipe-it.readme.io/docs/multi-tenancy-ish; https://help.glpi-project.org/documentation/modules/administration/entities
- PostgreSQL RLS semantics and bypasses (confirmed). https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- Django tenancy libraries. https://github.com/django-tenants/django-tenants; https://github.com/citusdata/django-multitenant; https://github.com/kdpisda/django-rls; https://github.com/pgrls/pgrls
- Geocoding and map policies. https://operations.osmfoundation.org/policies/nominatim/; https://developers.google.com/maps/documentation/geocoding/policies; https://github.com/maplibre/maplibre-gl-js
- Nominatim license mix (verified 2026-09-11). https://github.com/osm-search/Nominatim
- netbox-qrcode label coverage. https://github.com/netbox-community/netbox-qrcode

**Receiving and onboarding**
- Nlyte Receiving datasheet. https://www.nlyte.com/web/wp-content/uploads/2019/09/nlyte-receiving.pdf
- RF Code/Nlyte bidirectional sync. https://www.rfcode.com/blog/optimize-nlyte-dcim-integration-rf-code-centerscape
- dcTrack statuses and request lifecycle. https://www.sunbirddcim.com/help/dcTrack/v710c/en/Content/dcTrack/Item_and_Connection_Statuses.htm; https://www.sunbirddcim.com/help/dcTrack/v600/en/Content/dcTrack/Asset_Lifecycle_and_Workflow.htm
- Device42 lifecycle events. https://docs.device42.com/infrastructure-management/devices/device-lifecycle-tab/
- Hyperview `assetLifecycleState`. https://docs.hyperviewhq.com/redoc-static.html
- NetBox Labs Asset Lifecycle preview (2026-05-19) and GA (2026-06-30, Cloud and Enterprise Premium). https://netboxlabs.com/blog/asset-lifecycle-public-preview/; https://netboxlabs.com/blog/netbox-asset-lifecycle-ga/
- netbox-inventory (MIT), netbox-inventory-plus (MIT), CESNET inventory-monitor-plugin (Apache-2.0). https://github.com/ArnesSI/netbox-inventory/blob/master/README.md; https://github.com/sol1/netbox-inventory-plus; https://github.com/CESNET/inventory-monitor-plugin
- Cisco PnP planned → staged → active pattern. https://netboxlabs.com/blog/how-to-auto-provision-devices-with-netbox-and-cisco-pnp-provision/
- Ironic provision states, auto-discovery caveats; LLDP fields. https://docs.openstack.org/ironic/latest/user/states.html; https://specs.openstack.org/openstack/ironic-inspector-specs/specs/lldp-reporting.html
- Redfish ComputerSystem writable `AssetTag` (and `HostName`), read-only serial/SKU/UUID; SSDP optional. https://redfish.dmtf.org/schemas/v1/ComputerSystem.v1_1_0.json
- Dell TechDirect APIs (100 tags/query). https://www.dell.com/support/contents/en-us/article/product-support/self-support-knowledgebase/technologies-and-tools/techdirect/self-dispatch-and-apis
- Cisco SN2INFO v2 (75 serials/call; SNTC/PSS). https://developer.cisco.com/docs/support-apis/serial-number-to-information/
- Lenovo warranty endpoints. https://pubs.lenovo.com/lxca/support_viewwarranty
- X12 856 structure with `REF*SE` per unit (confirmed). https://www.insight.com/content/dam/insight/en_US/pdfs/insight/support/edi/insight-edi-vendor-856-guidelines.pdf
- Snipe-IT status-label model (AGPL; pattern only). https://raw.githubusercontent.com/grokability/snipe-it/master/app/Models/Statuslabel.php

**Demand and forecast**
- Nlyte placement/optimization, pre-leasing, colo, operational AI. https://www.nlyte.com/solutions/nlyte-placement-and-optimization-ai/; https://www.nlyte.com/blog/power-has-become-the-new-real-estate-modeling-constraints-pre-leasing-with-nlyte/; https://www.nlyte.com/solutions/colocation-solution/; https://www.nlyte.com/operational-ai/
- Sunbird capacity, dcTrack 6.1 reservations/decommission dates, Power IQ 9.1 days-of-supply, Auto Power Budget, 60% default budget, glossary. https://www.sunbirddcim.com/product/data-center-capacity-management; https://www.sunbirddcim.com/blog/introducing-dctrack-61; https://www.sunbirddcim.com/sites/default/files/FB003_Sunbird_FAQ_poweriq-features-and-benefits_9_1.pdf; https://www.sunbirddcim.com/sites/default/files/DS022_Sunbird_DataSheet_Auto_Power_Budget.pdf; https://www.sunbirddcim.com/help/dcTrack/v700/en/Content/dcTrack/Bulk_Update_Power_Budget.htm; https://www.sunbirddcim.com/glossary/data-center-capacity-planning
- Schneider IT Advisor capabilities; Capacity SKUs (sunsetting per verification). https://www.se.com/us/en/product-range/66103-ecostruxure-it-advisor/
- FNT Data Center Cockpit; Device42 what-if; Hyperview capacity; EkkoSense stranded capacity. https://www.fntsoftware.com/en/products/fnt-command/c-logic/data-center-cockpit; https://www.device42.com/use-cases/capacity-planning/; https://hyperviewhq.com/capacity-planning/; https://www.ekkosense.com/resources/industry-insight/how-to-find-stranded-capacity-in-data-centers/
- Uptime 2025 survey (confirmed) and 2024; M&O criteria. https://datacenter.uptimeinstitute.com/rs/711-RIA-145/images/2025.Annual.Survey.Report.pdf; https://intelligence.uptimeinstitute.com/resource/uptime-institute-global-data-center-survey-2024; https://uptimeinstitute.com/professional-services/management-operations/mando-criteria
- ITIL 4 practices and ITIL (Version 5) listing (confirmed). https://itsm.tools/34-itil-4-management-practices/; https://www.peoplecert.org/browse-certifications/it-governance-and-service-management/ITIL-1
- ISO/IEC 30134 parts and dates (confirmed). https://ucsiso.com/iso-iec-30134-2/; https://webstore.iec.ch/en/publication/75152; https://www.iso.org/standard/77691.html
- Libraries and licenses (confirmed): https://pypi.org/project/statsmodels/; https://github.com/Nixtla/statsforecast; https://github.com/Nixtla/hierarchicalforecast; https://pypi.org/project/scikit-learn/; https://pypi.org/project/sktime/; https://pypi.org/project/darts/; https://pypi.org/project/gluonts/; https://github.com/facebook/prophet; https://github.com/ourownstory/neural_prophet/releases; https://github.com/timescale/timescaledb-toolkit; https://www.tigerdata.com/docs/learn/hyperfunctions/about-hyperfunctions
- Colo contracted-vs-drawn semantics. https://www.sunbirddcim.com/blog/tips-manage-your-colocation-data-center-costs

**MCP**
- Spec 2026-07-28 changelog, release post, deprecations, transport, authorization, client registration, security considerations, best practices, tools, schema, MRTR, elicitation, resources, caching, `_meta`, versioning (all confirmed). https://modelcontextprotocol.io/specification/latest/changelog; https://blog.modelcontextprotocol.io/posts/2026-07-28/; https://modelcontextprotocol.io/specification/2026-07-28/deprecated; https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http; https://modelcontextprotocol.io/specification/latest/basic/authorization; https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/client-registration; https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations; https://modelcontextprotocol.io/specification/latest/basic/security_best_practices; https://modelcontextprotocol.io/specification/latest/server/tools; https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2026-07-28/schema.ts; https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr; https://modelcontextprotocol.io/specification/latest/client/elicitation; https://modelcontextprotocol.io/specification/latest/server/resources; https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching; https://modelcontextprotocol.io/specification/2026-07-28/basic; https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning
- Extensions and client matrix. https://modelcontextprotocol.io/docs/extensions/overview; https://modelcontextprotocol.io/extensions/client-matrix
- Python SDK v2 migration, ASGI, legacy clients, structured output. https://py.sdk.modelcontextprotocol.io/migration/; https://py.sdk.modelcontextprotocol.io/run/asgi/; https://py.sdk.modelcontextprotocol.io/run/legacy-clients/; https://py.sdk.modelcontextprotocol.io/servers/structured-output/
- TypeScript SDK v2 license split. https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/LICENSE
- FastMCP 4 changelog. https://gofastmcp.com/changelog
- django-mcp-server (PyPI). https://pypi.org/project/django-mcp-server/
- django-oauth-toolkit 3.4 changelog; license BSD-2-Clause (verified 2026-09-11). https://django-oauth-toolkit.readthedocs.io/en/latest/changelog.html; https://raw.githubusercontent.com/jazzband/django-oauth-toolkit/master/LICENSE
- netbox-mcp-server; Nautobot MCP FAQ; jschuller reference server. https://github.com/netboxlabs/netbox-mcp-server; https://docs.nautobot.com/projects/nautobot-mcp-server/en/stable/faq/; https://github.com/jschuller/mcp-server-servicenow
- Claude Code MCP docs; Claude.ai connectors; OpenAI MCP docs. https://code.claude.com/docs/en/mcp; https://claude.com/docs/connectors/building; https://developers.openai.com/api/docs/mcp
- OWASP MCP Tool Poisoning. https://owasp.org/www-community/attacks/MCP_Tool_Poisoning

---

## B.11 Refuted or disputed claims from round 2 (do not rely on the original wording)

1. **"IRE REST is the only IRE-compatible push path and a scoped app cannot create the discovery source."** Refuted. Import Sets + `CMDBTransformUtil`, IntegrationHub ETL/RTE and the scoped `sn_cmdb.IdentificationEngine` API also reach IRE; a scoped app can insert the choice via an install-time Fix Script (subject to cross-scope access); ServiceNow certifies the pull/import-set pattern, not external IRE REST pushes. Design conclusion (IRE payloads, never Table writes to `cmdb_ci`) stands.
2. **"ServiceNow MCP Server GA on 2026-05-05 with auth-code only, no client credentials/DCR."** Disputed on detail. MCP Server Console first shipped December 2025 (Zurich); the May 2026 press release declared the full-platform server GA; CIMD (public client + PKCE) is supported from Zurich P7 / Australia P1; client credentials and RFC 7591 DCR remain unsupported; Streamable HTTP with SSE optional; the AI Agent Studio client speaks 2025-06-18.
3. **"SGC certification requires TPP membership, two beta customers, per-release recertification (n-3), and customers must hold ITOM Visibility/Discovery."** Refuted on detail. Design review, two customer validations, Store release and per-release maintenance are documented; the program was restructured on 20 Jan 2026 into the Build Partner Program (Access/Registered/Select/Premier/Elite; fees unverified); ITAM SU SKUs can also entitle SGCs; "n-3" is not confirmed by a primary source.
4. **"Base CMDB has no rack-units-in-use calculator and no power-path model."** Refuted on detail. `cmdb_rel_rollup` on "In Rack::Rack contains" computes `rack_units_in_use`/`power_consumption` OOB (KB0788463); `cmdb_ci_circuit` and `powers::powered by` exist; Telecom Network Inventory (licensed) has native rack elevation. Still no OOB U-position on device CIs.
5. **"NetBox Labs, Sunbird and Nlyte all converge on per-field SoR, IRE, scoped attributes table and serial as natural key."** Refuted. NetBox Labs: per-object-type SoR, Correlation ID key, attributes table, IRE referenced; Sunbird 9.3: OAuth2 and custom tables only (SoR granularity, IRE and serial keying unverified); Nlyte: fixed ownership split, serial among synced fields. Only Nlyte documents the "ServiceNow masters asset, DCIM masters location/rack/U" split.
6. **"ServiceNow domain separation is a one-way, MSP-entitlement-gated switch requiring sys_domain on every push."** Refuted on detail. It can be disabled but not removed; activation is request-gated with no documented entitlement; Zurich added a post-production activation utility and Delete-by-Domain; IRE does not require `sys_domain` in the payload (CI domain defaults to the integration user's domain), so per-client domain-scoped integration users are the mechanism.
7. **"Nautobot 2.x LocationType is the only NetBox-family typed location construct."** Refuted on detail. LocationType dates from Nautobot 1.4 (2022); NetBox can carry an unenforced label via SiteGroup or a selection custom field; NetBox declined native location classes (issue #21041, Dec 2025). Typed class remains a written deviation.
8. **"A 1-cabinet IDF costs the same as a 42U hall cabinet under Sunbird's per-cabinet pricing."** Refuted on detail. dcTrack 8.0 introduced RU-weighted fractional (quarter-rack) licensing, unpublished and negotiated; Hyperview's 500-asset floor is itself hostile to single closets. The MSP unit remains a design choice (D69), justified by unpublished vs published terms and the MSP-level floor.
9. **"Hudu includes unlimited companies and per-client export; IT Glue has two regional endpoints."** Refuted on detail. Hudu's pricing page confirms $27/user/month (annual) with API included; "unlimited companies" and per-client export are unverified from primary pages; IT Glue has three endpoints (US, EU, AU) and restricts the API to Enterprise ($44/user, 5-user minimum) or legacy Classic plans.
10. **"NetBox Labs Asset Lifecycle is preview-only on Cloud Premium, Enterprise at GA."** Refuted on detail. GA on 2026-06-30 on both NetBox Cloud and NetBox Enterprise Premium; plugin v0.3.x with a breaking model reset at v0.3.0; no public repo, PyPI or license. D06 conclusion (no dependency) stands.
11. **"Vendor entitlement APIs: HPE has no API."** Refuted on detail. HPE has a request-only, undocumented warranty-check endpoint and a GreenLake COM beta limited to onboarded servers; Cisco's 75-serial limit is on the SN2INFO reference page, not the onboarding page; Lenovo's ClientID issuance is attested only by secondary sources.
12. **"ServiceNow's hardware asset lifecycle is a fixed 8-state enum with Build, mapped by a scripted synchronizer including CSDM stage."** Refuted on detail. Hardware has 7 states (Build is for bundles); mappings are table-driven (`alm_asset_ci_state_mapping`, `alm_hardware_state_mapping`) executed by `AssetAndCISynchronizer`; CSDM life-cycle uses a separate `life_cycle_mapping`; OOTB tables lack rows for Build/Design (KB2701442); the cited infocard is community-authored.
13. **"Redfish `AssetTag` is the only writable identity property; Ironic maps nodes via LLDP port-description rules."** Refuted on detail. `HostName` is also writable; SSDP is optional; ironic-inspector is retired (in-tree inspection); Ironic uses Chassis ID/Port ID/System Name for `local_link_connection`, not the Port Description TLV.
14. **"Schneider sells Capacity as a separate per-10-rack module; no DCIM vendor offers demand intake; runway/reservations are base at Device42 and FNT."** Refuted on detail. IT Advisor 10.0 (June 2026) unified Base/Capacity/Change into one per-rack subscription with the old SKUs discontinued 26 Feb 2027; Device42 and FNT reservation/runway features are not confirmed from primary sources; Nlyte and Hyperview market demand-oriented forecasting, so the narrowed claim is "no DCIM vendor offers a structured demand-request intake workflow".
15. **"SPM Demand Management exposes a fixed seven-state lifecycle."** Disputed. Seven default states on `dmn_demand`, but the Australia release lets customers rename/add stages via playbooks; conversion targets depend on installed plugins (Agile 2.0, Strategic Planning, SAFe).
16. **"The official Python SDK mounts via ASGI, serves both eras, ships `TokenVerifier`; django-mcp-server is stuck on 2025-03-26."** Disputed on detail. The SDK claims hold (cite the legacy-clients page); django-mcp-server merely links the 2025-03-26 spec and depends on `mcp>=1.8.0`, so it is written against the 1.x API rather than pinned to a spec, and still receives commits (latest 2026-03-10).
17. **"django-oauth-toolkit 3.4.0 implements the full MCP AS stack; Keycloak cannot parse RFC 8707 at all."** Refuted on detail. DOT's RFC 9207 `iss` and S256-only PKCE are opt-in flags until 4.0; PAR and `private_key_jwt` are unreleased; Keycloak 26.6/26.7 ships an undocumented experimental `resource-indicators` feature (PR #46763) that does not cover CIMD clients (issue #51413, milestone 26.8), and its own guide still rates RFC 8707 "Not supported". Conclusion (DOT as the MCP AS, Keycloak behind it) stands.
18. **"Precedents: netbox-mcp-server tools are `get_objects`/…; writes deferred to a 'NetBox Cloud Platform MCP'; ServiceNow governs writes through 'role-based tool packages'."** Refuted on detail. Tools are prefixed `netbox_`; NetBox Labs' governed writes are "NetBox Agents" (preview 2026-08-27), not MCP; ServiceNow write governance is ACL/role-based (`sn_mcp_server.admin`/`tools_admin`, Role Masking) with AI Control Tower optional; out-of-the-box ITSM/ITOM/CMDB/SPM MCP servers went GA 2026-09-10.
19. **"Claude.ai connectors: 2025-03-26..2025-11-25 auth specs, 240-second timeout; Copilot Studio OAuth DCR or manual."** Refuted on detail. Claude.ai auth types are `oauth_dcr`, `oauth_cimd`, `oauth_anthropic_creds`, `custom_connection`, `static_headers` (beta), `none`; the timeout is 240 s; Copilot Studio offers Dynamic discovery, Dynamic and Manual OAuth modes plus API key and none; DCR is not deprecated by any client, only by the spec.
20. **Condensed-text corrections applied in this document:** D70 "AssetTag is the only writable identity property" → only writable inventory-tag property (`HostName` also writable); D74 "240-second timeout" → 240 s; D66 Store/SGC wording aligned to the Build Partner Program restructuring; D64 rollup behavior added; D63 discovery-source registration via fix script recognized.

**Still unverifiable (round 2):** exact Build Partner fees and whether the Access Tier can publish to the Store; whether non-SGC IRE-created CIs count against ITOM subscription units; the Change API `POST /api/sn_chg_rest/v1/change/{sys_id}/ci` endpoint and body; ServiceNow MCP Server endpoint format `/sncapps/mcp-server/mcp/<server>`; whether Nlyte Receiving data is visible via OData; Nlyte Asset Sync's current Store listing and mechanism; Hudu API rate limits and per-company key scoping; TIA-569-E numeric sizing rules and TIA-606-D status; ISO/IEC 11801-5 definitions; BICSI 002-2024 H.13/H.14 and ISO 55000:2024 vocabulary; the Wood Mackenzie transformer lead-time figures; whether the official Python SDK 2.2.0 implements the Tasks extension server-side; ServiceNow's Universal MCP Client resources support (two verifications disagree); vendor API terms on MSP third-party use.

---

# Addendum B, round 3: conflict resolutions, new decisions D75 to D83, roadmap, risks and founder questions

## C.2 Conflicts with existing decisions: resolutions

| # | Conflict | Resolution and winner |
|---|---|---|
| 1 | D05 (forecasting, AI placement, multi-site executive dashboards in `ee/`) vs D72/D68 | **D72 wins.** D05 plan text is rewritten: `ee/` fences "multi-Organization portfolio rollups (cross-tenant aggregation), ML auto-model selection and ensembles, AI placement optimization, portfolio Monte Carlo, procurement-lead-time optimization, colo revenue analytics with rate plans, audit-event streaming, hosted control plane, certified-connector packaging, extended-support backports." Single-Organization forecasting, runway, reservations, demand intake and MSP client/site rollups are core. One rule, one text. |
| 2 | D30 (ticket adapters, approval UI, work orders in Phase 3) vs Addendum B Phase 2 change attachment | **Addendum B wins for ServiceNow only.** D30 is revised: ServiceNow Change attachment and the approval gate move to Phase 2 because D63's pull already lands the tables; Jira and BMC remain Phase 3; the approval UI needed by the gate is the minimal "approve/reject intent" screen already required by D12, not the full D30 workflow designer. |
| 3 | D57 (Supported tier per site; site = any building/campus Location with ≥ 1 rack) vs D67/D69 | **D69 wins and D57 is revised.** Site definition: a *billable site* is a building or campus containing at least one `data_hall`, `computer_room`, `micro_edge_dc` or `server_room`; closet-class Locations roll up to their parent building and are never sites on their own. In MSP mode and for any estate where closet-class assets exceed 50% of weighted assets, the Supported tier is priced on the D69 weighted-asset unit instead of per site. The per-cabinet trigger in D57 is retired; D69's weighted asset is the only usage unit. |
| 4 | D12 (only the owning system writes a field) vs D74 override scope | **D12 wins.** See D74 correction 4. |
| 5 | D64 (HAM masters asset state) vs D65/D70 (UnumDCIM pushes install_status) | **Split by lifecycle segment** (D64 correction 1): HAM masters the procurement segment; UnumDCIM masters the placement segment; request mode as fallback. |
| 6 | D40 (NetBox owns serial/asset tag), D64 (ServiceNow masters serial/asset tag), D70 (serial born at the dock) | **D76 (new) wins** with a per-tenant precedence list; D40 remains the default for NetBox-only estates. |
| 7 | D50 (Row/Aisle/TenantAllocation as objects) vs D67 enum | **D50 wins.** Enum corrected. |
| 8 | D58 (monitor as separate service over REST) vs D71 forecast reads and D68 client portal | **D58 is extended, not overturned:** bulk rollup read endpoint, tenant/client labels on series, client-scoped tokens for portal reads (D80, D77). |
| 9 | D26/D37 (no phone-home, air-gap) vs D73 CIMD/DCR and hosted-client callbacks | **D26/D37 win for defaults.** Pre-registered clients by default; CIMD behind an egress allowlist; DCR off; hosted clients require a deliberately published endpoint (D81). |
| 10 | D31/D38 (partner program and 9 FTE) vs Addendum B Phase 1 scope | **D82 (new):** IRE push and MSP mode move to Phase 2; Phase 1 keeps pull, the data model, read-only MCP and the edge UX; a fourth (ServiceNow-shop) design partner is sought but is not a Phase 1 exit dependency; D38 gains one integration engineer from Phase 1 month 6 only if that partner signs. |
| 11 | D41 (100k assets/hour import) vs D63 rate limit | **Both stand, scoped differently:** D41 governs UnumDCIM's own importer; D63 bulk mode (correction 8) governs the ServiceNow push with a documented estimate. |
| 12 | D25b (second-role approval) vs D74 apply-with-elicitation | **D25b wins.** See D74 correction 7. |
| 13 | D59 (hash-chained change log, 7-year retention) vs D68 purge | **D77 (new):** per-client audit chain under the MSP tenant, anchored in the tenant chain; offboarding exports the client chain to WORM and detaches it, leaving a tombstone. Content is retained by the exporting party, not by the MSP install. |
| 14 | D21 (Nlyte Asset Sync customers; sync via ServiceNow CMDB) vs D63 second writer | **D12 single-owner principle wins at the ServiceNow end:** D63 correction 6 (pull-only default, D21b cut-over switch). |
| 15 | D14/D35 (single three.js context, VDI presets) vs D67 MapLibre | **D14/D35 win:** map on a separate route with a static fallback; spike extended (D67 correction 3). |

---

## C.3 New decisions

### D75 ServiceNow setup kit and connect-time probe

**Area:** `unum-sync` ServiceNow adapter (D63), docs, CI fixtures.

**Why it matters.** IRE rejects classes without an identification rule, reconciliation rules decide whether our writes land, relationship types must exist, custom elevation fields must be defined, and half of D65's paths depend on plugins the customer may not hold. Without a versioned, checkable setup kit, every deployment is bespoke and the "no duplicate CIs after 30 days" exit is luck.

**Options.**

| Option | Strongest objection |
|---|---|
| K1. Versioned setup kit (documents + an XML update set of dictionary entries and rules the admin reviews and imports) plus a connect-time probe that refuses push until the kit's preconditions are met | Update sets are frowned upon for third-party apps; the customer's CMDB team must review every rule. |
| K2. Docs only; the adapter pushes whatever it can | Unpredictable masking and identification failures; support load. |
| K3. Scoped app now | D66 defers this. |

**Recommendation.** K1. Contents: (1) the `UnumDCIM` discovery-source choice (admin step); (2) a class table listing, for each mapped class, the required identification rule (OOB or kit-supplied `cmdb_identifier` entries for `cmdb_ci_pdu_outlet`, `cmdb_ci_zone`, `cmdb_ci_circuit` and the CI Class Models containers, with lookup on `sys_object_source_info`); (3) a recommended reconciliation-rule set mirroring the D64 ownership table (UnumDCIM priority 100 on placement and install-state attributes; ServiceNow/Discovery/HAM priority 100 on asset, financial and model attributes); (4) required `cmdb_rel_type` entries (`In Rack::Rack contains`, `Powers::Powered by`; `Cools::Cooled by` optional, **UNVERIFIED**); (5) the `u_` dictionary entries (`u_rack_position`, `u_rack_height_u`, `u_rack_face`, `u_space_class`, `u_unum_model_slug`) with tenant-configurable names; (6) the OAuth application registry entity, the Web-Service-Access-Only integration user and its roles; (7) the `RESTMessageV2` business rule and OAuth profile for the inbound hint; (8) a rate-limit rule for the integration user; (9) the "let ServiceNow roll up" toggle documentation for `cmdb_rel_rollup`. The connect-time probe checks each item and produces a readiness report; push is disabled until items 1 to 5 pass; items 6 to 9 produce warnings. The probe also detects Event Management, SPM, Procurement, HAM Pro, CI Class Models, Domain Separation, Multisource CMDB, TNI, the asset auto-creation settings, foreign DCIM discovery sources (D63 correction 6) and `cmn_location` population (D64 correction 2). The kit is versioned per family release with fixtures in CI.

**Rationale.** IRE selects rules from `sys_class_name` and requires identification rules per class (https://www.servicenow.com/docs/r/api-reference/rest-apis/c_IdentifyReconcileAPI.html; https://www.servicenow.com/community/cmdb-articles/understanding-ire-reconciliation-rules/ta-p/3289239); the discovery source is a global `sys_choice` (https://www.servicenow.com/community/itom-forum/creating-discovery-source-via-scripts-from-application-scope/m-p/2681253); NetBox Labs' certified app similarly ships a Class Manager to register classes (https://netboxlabs.com/docs/servicenow/).

**Depends on:** D63, D64, D65, D66.

**Door:** two-way (kit contents are data).

**Evidence that would change it.** A scoped app (D66) that can bundle the rules; ServiceNow shipping OOB identification rules for the facility classes.

---

### D76 Identity-field ownership across NetBox, ServiceNow HAM and the UnumDCIM Asset

**Area:** OwnershipPolicy (D12, D40, D64), Asset model (D70).

**Why it matters.** Serial number and asset tag are the join keys for every sync (D46) and now have three candidate owners. A field with two owners is the split-brain D12 forbids; a field with no defined owner cannot be reconciled.

**Options.**

| Option | Strongest objection |
|---|---|
| I1. Ordered precedence list per tenant with a "first recorder" tie-break; one owner per field per Asset; NetBox always receives the value | Precedence must be explained on every conflict; three-peer estates still see discrepancies at first sync. |
| I2. UnumDCIM Asset always owns serial/asset tag | Contradicts HAM's mastery of asset tags in ITAM shops and NetBox users' expectations (D40). |
| I3. Per-Asset owner chosen manually | Unworkable at scale. |

**Recommendation.** I1. Default precedence for `serial_number` and `asset_tag`: **ServiceNow HAM** (if the tenant has HAM and a matching `alm_hardware` row exists) → **UnumDCIM Asset** (dock scan or ASN, D70) → **NetBox device** (D40). Tie-break when two systems each hold a value and the precedence owner has none: the *first recorder* (earliest provenance timestamp) owns; the other value is a discrepancy. A per-tenant override may reorder the list (e.g., NetBox-only estates keep D40 verbatim; Nlyte estates insert Nlyte after HAM). `mac_address` follows the same list with NetBox interfaces ahead of the Asset. The owner is stored per field on the Asset's provenance record and shown in `unum.inventory.provenance`. Any peer that is not the owner receives the value as a projection; conflicts never overwrite the owner's value.

**Rationale.** Nlyte's precedent keeps ServiceNow as asset-attribute master (https://www.nlyte.com/blog/master-your-assets-nlyte-servicenow-cmdb-integration/); NetBox is the only source in NetBox-only estates (D40); serial-first matching is D46.

**Depends on:** D12, D40, D46, D64, D70.

**Door:** two-way for the default order; one-way for "one owner per field".

**Evidence that would change it.** A design partner whose HAM asset tags are unreliable (would demote HAM below the Asset for `asset_tag`).

---

### D77 MSP shared-versus-scoped record inventory, session scoping and per-client audit chains

**Area:** tenancy (D68), audit (D59), database access (D10/D25).

**Why it matters.** The addendum named the Snipe-IT/GLPI scoping risk without stating which tables carry a client, how MSP staff sessions holding several clients are expressed to PostgreSQL under connection pooling, and how a client can be purged without breaking the tenant's hash chain.

**Options.**

| Option | Strongest objection |
|---|---|
| X1. Explicit inventory: client-scoped tables carry NOT NULL `client_id` with composite keys; MSP-shared tables have no `client_id` (not nullable); per-request `SET LOCAL` of a client-id array inside the transaction; per-client audit chain anchored in the tenant chain | Two table families double the migration discipline; `SET LOCAL` requires transaction-mode pooling and one transaction per request. |
| X2. Nullable `client_id` everywhere, NULL = shared | NULL semantics in RLS policies are the classic leak (NULL never equals anything); MSP-shared rows leak or vanish depending on policy wording. |
| X3. Single tenant-wide audit chain, client content retained | Cannot honor a client deletion demand; contract and GDPR exposure. |

**Recommendation.** X1.

- **Client-scoped tables (NOT NULL `client_id`, composite `(id, tenant_id, client_id)` keys):** Location, Row, Aisle, Rack, Device, Asset and all D70 procurement objects, Cable, PowerFeed/PowerPanel and power-chain nodes, ResourcePool, Reservation, DemandRequest, Forecast, Scenario, ChangeRequest/WorkOrder intents, ReceivingRecord (owner MSP, see below), TenantAllocation, ExternalReference, alarm instances, attachments, MCP task records.
- **MSP-shared tables (no `client_id` column):** Organization, Client/Party, users and RBAC grants, the library sidecar and RackTypes/DeviceTypes (D17), custom-field definitions, alarm channel definitions, sync connection profiles (ServiceNow profiles are per client and therefore *client-scoped*, the exception), license files, the audit index.
- **Shared physical resources** (an MSP-owned dock, staging room or shared rack row): these are `Location`s scoped to a reserved **MSP-self client** (`client_id = <msp_self>`); ReceivingRecords at a shared dock belong to the MSP-self client, and each ReceivingLine carries the target `client_id`; RLS lets a client see lines addressed to it and nothing else on the record.
- **Session mechanism:** the application opens one transaction per request and issues `SET LOCAL unum.tenant_id = …; SET LOCAL unum.client_ids = '{…}'` (an array; MSP staff get the union of their grants; MSP superusers get `*`, which policies treat as "any client of this tenant"); policies use `client_id = ANY(current_setting('unum.client_ids')::uuid[])`. PgBouncer, if used, must run in **transaction** pooling mode, and session-mode features are forbidden; the Helm chart enforces it. Background workers set the same variables from the job's recorded scope.
- **Audit:** one hash chain per `(tenant_id, client_id)`, each chain's periodic head hash anchored into the tenant chain (D59). Offboarding: freeze → export (per-client D44 bundle + the client chain, verifiable stand-alone) → hand the WORM export to the client or the MSP's escrow → detach the client chain and purge client-scoped rows; the tenant chain keeps a tombstone (client id, final head hash, export digest, actor, timestamp), so the tenant chain verifies without the detached content. Change-log snapshots for the client live in the client chain and therefore leave with it. The MSP contract template states this.

**Rationale.** PostgreSQL RLS semantics and NULL behavior (https://www.postgresql.org/docs/current/ddl-rowsecurity.html); scoping-bug loci in Snipe-IT and GLPI (https://snipe-it.readme.io/docs/multi-tenancy-ish; https://help.glpi-project.org/documentation/modules/administration/entities); D59's chain design.

**Depends on:** D10, D25, D25b, D44, D59, D68.

**Door:** one-way for the two-family table rule and per-client chains (ADR 0017 amended).

**Evidence that would change it.** A pooling constraint in the Helm reference that cannot run transaction mode (would force session variables via a per-request connection).

---

### D78 Attachment storage

**Area:** deployment (D26), data model (D11), receiving (D70), export (D44).

**Why it matters.** Damage photos, packing lists, label PDFs and change evidence need a home in Phase 1; D26 only provisions object storage for asset packs.

**Options.**

| Option | Strongest objection |
|---|---|
| H1. `Attachment` model (tenant/client-scoped, content hash, MIME allowlist, size cap, virus-scan hook) with a pluggable backend: local filesystem volume by default, any customer-provided S3-compatible endpoint optional | Two backends to test; local volumes complicate multi-replica deployments. |
| H2. Bundle an object store in the reference stack | MinIO is AGPL-3.0 (D04 forbids in-process but a container is allowed; still adds an operational component and licensing questions for redistribution); Ceph is too heavy. |
| H3. Store blobs in PostgreSQL | Backup bloat; fine for tiny files only. |

**Recommendation.** H1. Filesystem backend on a shared volume (Compose) or ReadWriteMany PVC (Helm) by default; S3-compatible backend configured by URL and credentials from the D25b store, with the customer supplying the endpoint (no object store is bundled). Attachments are included in the D44 bundle and the per-client export (D77); the Phase 1 desktop receiving form supports photo upload; the PWA queues photos offline (Phase 3).

**Rationale.** Keeps the reference stack to PostgreSQL + Valkey + the app containers (D26); avoids redistributing AGPL software.

**Depends on:** D04, D25b, D26, D44, D70, D77.

**Door:** two-way.

---

### D79 First-power listener component and BMC credential bootstrap

**Area:** monitoring (D10/D25b/D58), receiving (D70), security.

**Why it matters.** Telegraf cannot listen for SSDP multicast or DHCP leases, `unum-monitor` is central, and Redfish requires credentials the addendum never provisioned. Without both, the Phase 2 "matched and proposed as staged" exit is unreachable.

**Options.**

| Option | Strongest objection |
|---|---|
| E1. A small Python **staging listener** in the UnumDCIM Collector image, one instance per staging VLAN, site-scoped lease per D25b, reporting candidates to core over the collector API; per-manufacturer default-credential recipes for first contact, immediate rotation to a per-device generated password stored in the D25b vault | Default vendor credentials vary by model and shipment; some vendors ship unique per-device passwords (Dell iDRAC label, HPE iLO label) that must be entered or scanned at the dock. |
| E2. Rely on the customer's DHCP server logs and ZTP system | Not present at closets; couples onboarding to third-party tooling. |
| E3. Skip first-power matching; dock scan only | Loses the automatic serial confirmation and the LLDP placement proposal. |

**Recommendation.** E1. The listener: SSDP M-SEARCH for `urn:dmtf-org:service:redfish-rest:1` plus passive DHCP-lease observation (via a DHCP relay/snoop interface or the site DHCP server's lease API where available) and ARP/ND sweep of the staging subnet as fallback; for each candidate it reads `/redfish/v1/Systems` `SerialNumber`, `SKU`, `UUID`, `Manufacturer`, `Model` using the credential ladder below; it posts candidates to core; core matches to `inbound`/`in_stock` assets and proposes `staged` into the discrepancy queue (D51). Credential ladder: (1) per-device password captured at the dock (scanned from the vendor label into the Asset's vault entry, D70 label-parsing rules extended); (2) per-manufacturer default-credential recipe (Apache-2.0 data file; documented, not bundled secrets); (3) none, candidate reported as "found, unauthenticated". On first successful authentication the listener rotates to a generated per-device password stored in the vault and, only after an approved WorkOrder under D25b, writes `AssetTag`. Listeners are confined to staging VLANs by configuration and the collector lease; production VLANs are refused. Rate and candidate caps mitigate the Ironic-style DoS vector.

**Rationale.** Redfish SSDP is optional and requires an on-segment listener (https://redfish.dmtf.org/schemas/v1/ComputerSystem.v1_1_0.json; DSP0266); Ironic documents manual BMC credentials and the auto-discovery DoS caveat (https://docs.openstack.org/ironic/latest/user/states.html).

**Depends on:** D25b, D50, D51, D58, D70.

**Door:** two-way.

**Evidence that would change it.** Vendors converging on Redfish device-registration (e.g., a standard first-contact credential exchange) would remove the recipe ladder.

---

### D80 Forecast series sources, cross-service reads and history gates

**Area:** forecasting (D71), telemetry (D28/D58), change log (D59).

**Why it matters.** Most Phase 1 users have no telemetry, and the forecast engine lives in `unum-core` while measured rollups live in `unum-monitor`.

**Options.**

| Option | Strongest objection |
|---|---|
| Q1. Inventory-derived series as the universal input (committed and planned per pool per day reconstructed from the change log), measured series added when present via a bulk rollup read endpoint on `unum-monitor` | Reconstructing series from the change log is a batch job over D59 data; step-like by nature. |
| Q2. Measured series only | Empty runway for the NetBox funnel and closets. |
| Q3. Move rollups into the core database | Contradicts D58's service split and the TelemetryStore abstraction. |

**Recommendation.** Q1. A nightly job materializes `pool_series(pool_id, date, committed, planned, budgeted)` from the change log (D59) and current intents; `unum-monitor` exposes `GET /api/v1/rollups/bulk?pools=…&from=…&to=…&agg=daily_p95` returning measured series with tenant/client labels enforced by the core-issued token; the ForecastEngine consumes both. Gates: no statistical forecast below 8 weekly points; segmented trend default for inventory series; measured series required for the budgeted rung. The "show the math" panel names the series source.

**Depends on:** D28, D58, D59, D71, D77.

**Door:** two-way.

---

### D81 MCP token model, client registration defaults and reachability matrix

**Area:** MCP authorization (D73), deployment (D26), security (D25).

**Why it matters.** Stock django-oauth-toolkit issues opaque tokens, has a static scope list, and its DCR endpoint is unauthenticated; hosted MCP clients need an internet-reachable endpoint the self-hosted story never admitted.

**Options.**

| Option | Strongest objection |
|---|---|
| T1. Opaque DOT tokens verified in-process; grants resolved from RBAC at verification; capability scopes only; DCR off / CIMD allowlisted by default; explicit reachability matrix | External resource servers later need introspection (DOT provides it); consent screen must render grants. |
| T2. JWT access tokens with custom claims | Requires a custom token generator and key management; grants baked into tokens go stale on revocation. |
| T3. Dynamic scopes for org/client/site | Not supported by DOT's static `SCOPES`; consent UX for hundreds of sites is unusable. |

**Recommendation.** T1.

- **Tokens:** opaque; `TokenVerifier` performs a DB lookup, checks expiry, RFC 8707 resource binding (`https://<instance>/mcp`) and scopes, then loads the subject's RBAC grants (Organization, Clients, sites) into the request context; the consent screen lists the grants that will apply. Introspection (RFC 7662) is enabled for future external resource servers only.
- **Registration defaults:** enterprise/air-gap profile: pre-registered clients only, DCR off, CIMD off; cloud-connected profile: CIMD on with an egress allowlist (`claude.ai`, `openai.com`, `microsoft.com`, customer domains), DCR on only with an admin-issued initial access token. The Claude Code loopback redirect and the `https://claude.ai/api/mcp/auth_callback` redirect are pre-registered client templates in the docs.
- **Reachability matrix (published in the docs):** *Local clients* (Claude Code, VS Code, Cursor, desktop agents on the LAN/VPN): work with no inbound exposure. *Hosted clients* (Claude.ai/Desktop connectors, ChatGPT, Copilot Studio): require the customer to publish `/mcp` and the DOT endpoints through a reverse proxy with TLS, IP allowlists where the client publishes ranges, and the hardening guide; explicitly optional. *ServiceNow AI Agent Studio* → UnumDCIM: requires a published endpoint; a MID-Server-relayed path is **UNVERIFIED** and not promised. The D26 no-inbound-holes posture is unchanged for the reference install; publishing `/mcp` is a documented deviation the operator chooses.

**Rationale.** MCP authorization requirements (https://modelcontextprotocol.io/specification/latest/basic/authorization; https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/client-registration); DOT 3.4 features (https://django-oauth-toolkit.readthedocs.io/en/latest/changelog.html); Claude.ai callback and client types (https://claude.com/docs/connectors/building).

**Depends on:** D23, D25, D26, D37, D68, D73, D77.

**Door:** two-way for defaults; one-way for "grants are not scopes".

**Evidence that would change it.** A DOT release with first-class dynamic resource scoping; a ServiceNow-documented MID Server path for MCP.

---

### D82 Phase 1 scope rebalancing, staffing and partner program (revises D31, D38, section B.7)

**Area:** roadmap, staffing, design-partner program.

**Why it matters.** Addendum B added six workstreams and a ServiceNow partner dependency to Phase 1 with no staffing change; unfunded scope is the failure mode D01 warns about.

**Options.**

| Option | Strongest objection |
|---|---|
| R1. Move IRE push, change attachment and MSP mode to Phase 2; keep pull, the data model, read-only MCP, edge UX and bulk onboarding in Phase 1; seek a ServiceNow-shop partner without making it a Phase 1 gate; +1 integration engineer only when that partner signs | Delays the visible "bidirectional" demo to Phase 2. |
| R2. Fund everything in Phase 1 (+3 FTE) | Cash and hiring risk before any revenue; contradicts D38's ramp. |
| R3. Keep Phase 1 as written and hope | Trellis pattern. |

**Recommendation.** R1. Phase 1 exit criteria are revised: the ServiceNow criterion becomes "a partner's or vendor instance's CMDB racks, PDUs and devices render in the twin within one hour from a read-only integration user; IRE push is demonstrated on the test instance with the setup kit applied (not on a customer instance)"; the MSP criterion moves to Phase 2; the runway, edge-UX, receiving-data-model and MCP-read criteria stay. D31 adds a fourth design-partner profile (ServiceNow shop with HAM, ideally SPM) targeted for Phase 1 month 6; D38 adds one integration engineer from that date if the partner signs, otherwise the Phase 2 plan absorbs the work with the existing team. The D30/D63 change-attachment work is Phase 2 (C.2 item 2).

**Depends on:** D01, D31, D38, D63, D65, D68.

**Door:** two-way.

---

### D83 Retirement and archival semantics for ServiceNow-projected objects (formalizes D63 correction 1)

**Area:** ServiceNow adapter, ADR 0019.

**Why it matters.** Recorded separately so ADR 0019's one-way rule has a precise statement: *UnumDCIM creates and updates `cmdb_ci` rows only through IRE; it never inserts `cmdb_ci` via the Table API; it retires by state update, never by deletion; it removes only relationships it created, and only when IRE partial payloads cannot prune them.* The Phase 0 spike records the IRE relation-pruning behavior as the deciding evidence; if pruning works, the Table API `DELETE` exception is never enabled.

**Depends on:** D63, D64, D75. **Door:** one-way (ADR 0019 as amended).

---

## C.4 Unsupported claims: corrections

| # | Claim in Addendum B | Disposition |
|---|---|---|
| 1 | Hudu "per-client export" and "companies as root" as verified MSP precedent (D68) | Re-labeled UNVERIFIED; rationale now rests on Snipe-IT, GLPI, Device42. |
| 2 | "5 to 8 weeks certification" (D66) | Struck; no source. |
| 3 | "apps that push via the IRE REST API cannot be Store-certified" (D63) | Re-labeled UNVERIFIED (verifier paraphrase, no URL); not load-bearing. |
| 4 | `cools::cooled by` relationship type (D64) | Re-labeled UNVERIFIED; used only if present. |
| 5 | TokenVerifier "validates DOT-issued JWTs" (D73) | Withdrawn; opaque tokens per D81. |
| 6 | `stateless_http=True` still serves 2025-06-18 elicitation-free tools (D73) | Re-labeled "per the SDK legacy-clients page; confirm in the Phase 0 spike"; cite https://py.sdk.modelcontextprotocol.io/run/legacy-clients/ not the ASGI page. |
| 7 | ServiceNow OOB MCP servers GA 2026-09-10; Role Masking mandatory (D74) | Re-labeled UNVERIFIED (verifier note, no URL). |
| 8 | Official SDK Tasks support assumed for Phase 2 (D73/D74) | Made conditional on the Phase 0 probe; FastMCP 4 is the fallback. |
| 9 | DOT BSD-2-Clause and Nominatim license mix "checked 2026-09-11" (header) | Carried in the fact sheet as **addendum-author assertions with URLs**, not panel-verified facts; added to the Phase 0 license-allowlist CI check for mechanical confirmation. |
| 10 | `telecom_room` = HDA/IDA, `main_telecom_room` = MDA/ENI/MD (D67) | Presented as editorial vocabulary choices. |
| 11 | Transformer lead time ~128 weeks as a default (D71) | Removed from defaults; placeholder only. |
| 12 | Sunbird fractional terms "negotiated, not published" (D69) | Reworded to "exists since dcTrack 8.0, not on the public price page." |
| 13 | Cisco SN2INFO "may paginate at 50" (D70) | Re-labeled UNVERIFIED. |
| 14 | ServiceNow Universal MCP Client resources "from June 2026" (D74) | Re-labeled UNVERIFIED; roadmap independent of it. |
| 15 | "Full white-label is not the norm" from MyGlue alone (D68) | Withdrawn as a generalization. |

---

## C.5 Roadmap amendments (supersede B.7 where they differ)

**Phase 0 additions.** IRE relation-pruning spike (D83); setup-kit v0 and probe (D75); DOT opaque-token verifier and consent-screen grant rendering (D81); Tasks-support probe in `mcp` 2.x; map route on the VDI preset (D67); license-allowlist check extended to DOT, Nominatim (container only), the in-house EDI reader. *Exit:* the revised D63 correction 11 criterion; `/mcp` dual-era test with opaque DOT tokens and a negative cross-client test; Tasks support recorded as present/absent.

**Phase 1 (per D82).** ServiceNow **pull** with the probe and readiness report; IRE push demonstrated on the test instance only; Asset lifecycle with child assets, ASN/CSV importer, attachments (D78), desktop receiving form; inventory-derived runway (D80) with the 8-point gate; MCP read tools including `search`/`fetch`; edge UX and map route; bulk onboarding with CSV coordinates by default. MSP mode is **not** in Phase 1. *Exit:* as revised in D82.

**Phase 2.** IRE push on customer instances with the setup kit; change attachment with the state-mapping table; Event Management (where licensed); demand mirror; reverse receipt into HAM (D65 correction 2); MSP mode with D77 inventory, per-client chains, client portal and monitor scoping; staging listener and BMC bootstrap (D79); bulk rollup endpoint (D80); MCP intent, telemetry/alarm, cabling, receiving and pull-only sync tools with Tasks (or FastMCP 4); D69 published. *Exit:* B.7 Phase 2 criteria plus: a client offboarding produces a verifiable detached chain and the tenant chain still verifies; a cancelled ServiceNow change withdraws the ghost and releases reservations.

**Phase 3.** Unchanged, plus the optional Hudu adapter and the D66 scoped app on customer demand.

---

## C.6 Risks added (33 to 40)

33. **IRE relation pruning unknown.** If partial payloads do not prune relations and the customer forbids the `cmdb_rel_ci` DELETE exception, stale edges accumulate. *Mitigation:* D83 spike; discrepancy surfacing; customer archival job guidance.
34. **ServiceNow asset auto-creation** produces duplicate assets despite D64. *Mitigation:* D63 correction 5 serial resolution and probe.
35. **Multiple DCIM writers into one CMDB** (Nlyte Asset Sync coexistence). *Mitigation:* D63 correction 6 pull-only default and D21b cut-over.
36. **Test-instance availability and PDI terms.** *Mitigation:* partner sub-production instance; PDI for smoke only; N-1 promise restated.
37. **ODbL exposure** from persisted geocodes. *Mitigation:* counsel review; CSV coordinates default; attribution stored.
38. **Published `/mcp` for hosted clients** widens the attack surface of a self-hosted install. *Mitigation:* D81 matrix, hardening guide, pre-registered clients, DCR off.
39. **Per-client audit chains** add operational complexity (chain rotation, anchoring). *Mitigation:* D77 design with tombstones; verification tooling in the CLI.
40. **Staging-listener abuse** (phantom candidates, credential-ladder misuse). *Mitigation:* VLAN confinement, candidate caps, no production VLANs, vault-only credentials, D25b approval for `AssetTag` writes.

Risk 21 is extended with Event Management, SPM, Procurement, HAM Pro and the Now Assist requirement for ServiceNow agents calling UnumDCIM. Risk 29 is extended with the DCR/CIMD defaults.

---

## C.7 Founder questions added (23 to 28)

23. **Table API DELETE exception for `cmdb_rel_ci`:** acceptable in principle if IRE cannot prune relations, or never (stale edges left to the customer's archival job)?
24. **Demand push to SPM:** should UnumDCIM ever write `dmn_demand`, or is mirror-only the permanent posture?
25. **Hosted MCP clients:** will target customers publish `/mcp`, or should the launch client list be local clients only (Claude Code, VS Code, Cursor) with hosted clients as a documented deviation?
26. **Per-client audit chain detachment on offboarding:** does the MSP contract template's "content leaves with the client" wording satisfy the founder's expected MSP customers, or must the MSP retain a sealed copy?
27. **Staffing trigger (D82):** confirm the +1 integration engineer is contingent on a signed ServiceNow-shop partner rather than scheduled.
28. **Supported-tier unit (C.2 item 3):** confirm the 50%-weighted-closet threshold that switches an estate from per-site to weighted-asset pricing, or choose a simpler "MSP mode always weighted-asset" rule.
