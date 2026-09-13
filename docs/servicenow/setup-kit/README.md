# ServiceNow setup kit (placeholder)

Decision D75 (`docs/decisions/02-addendum-b.md`) defines a versioned setup kit that a customer's ServiceNow administrator reviews and applies before UnumDCIM is allowed to push into the CMDB. The kit will contain, per ServiceNow family release:

1. The one-time admin step that registers the `UnumDCIM` discovery source (`sys_choice` on `cmdb_ci.discovery_source`).
2. A per-class table of required identification rules, with kit-supplied `cmdb_identifier` entries for classes that lack them out of the box (`cmdb_ci_pdu_outlet`, `cmdb_ci_zone`, `cmdb_ci_circuit`, CI Class Models container classes), keyed on `sys_object_source_info`.
3. A recommended reconciliation-rule set mirroring the ownership table in D64: UnumDCIM priority on placement and install-state attributes; ServiceNow, Discovery and HAM priority on asset, financial and model attributes.
4. Required `cmdb_rel_type` entries (`In Rack::Rack contains`, `Powers::Powered by`; `Cools::Cooled by` only if present).
5. The `u_` dictionary entries for rack position, height, face, space class and model slug, with tenant-configurable names.
6. The OAuth application registry entity, the Web-Service-Access-Only integration user and its roles.
7. The `RESTMessageV2` business rule and OAuth profile for the inbound hint.
8. A rate-limit rule for the integration user.
9. Guidance on the out-of-the-box `cmdb_rel_rollup` ("let ServiceNow roll up").

The connect-time probe checks every item and produces a readiness report; push stays disabled until items 1 to 5 pass. The kit is versioned per family release with fixtures in CI. Contents will be added in Phase 0 against a partner sub-production instance.
