# Feature-parity checklist (public roadmap contract)

"Parity" with enterprise DCIM suites (Nlyte, Sunbird dcTrack/Power IQ, Schneider EcoStruxure IT, Device42, Hyperview, FNT Command, CommScope iTRACS, Vertiv) is defined by this list, not by feeling. T = table stakes (every major suite ships it). D = differentiator (only some ship it). Phase numbers follow the roadmap in `decisions/00-walkthrough.md` section 4 as amended by `decisions/02-addendum-b.md` round 3 (C.5).

| # | Capability | Class | Phase | Notes |
|---|-----------|-------|-------|-------|
| 1 | Asset lifecycle (receiving to retirement), rack elevations with scaled front/rear images, vendor model library, custom fields, bulk import | T | 1 (lifecycle model, desktop receiving), 3 (technician PWA dock) | Asset separate from Device (D70); CC0 library seed with procedural art (D17) |
| 2 | Capacity: space (U), power, cooling, weight/floor load, ports at rack and upstream device level | T | 1 (ladder, linear runway), 2 (demand intake, alerts) | Capacity ladder and demand model (D43, D71) |
| 3 | Power chain utility to PSU with auto one-line diagrams and end-to-end trace (AC and DC, three-phase) | T | 1 (chain to rack PDU, one-line SVG), 3 (DC circuits, three-phase balance) | D11 extensions |
| 4 | Structured cabling: port-level connections, patch panels, media validation, circuit trace | T | 1 (pass-through ports, basic trace), 3 (cassettes, enclosures) | D49 |
| 5 | Change management: MAC requests with approvals, work orders, audit trail, ticketing connectors | T | 1 (ChangeRequest intent, approve/reject), 2 (ServiceNow Change attachment), 3 (Jira/BMC, full workflow UI) | D30, D65 |
| 6 | Monitoring: SNMP/Modbus/BACnet polling, thresholds, trap receipt, notification | T | 2 | D28, D52 |
| 7 | Energy/PUE/sustainability reporting | T | 2 (metering points, PUE overlays), 3 (EU EED template) | D55 |
| 8 | 2D floor plans, rack elevations, 3D | T | 1 | D14, D15; 3D is now table stakes |
| 9 | Dashboards, custom reports, BI export (SQL/ODBC views, BI feeds) | T | 2 | D54 |
| 10 | REST API with OpenAPI, tokens/OAuth2, webhooks; ServiceNow and VMware connectors | T | 1 (API, NetBox, Nlyte read, ServiceNow pull), 2 (ServiceNow push and change, vSphere) | D23, D63 |
| 11 | RBAC, SAML/OIDC SSO, MFA, audit logging | T | 1 | D25, moved into the MVP by the judges |
| 12 | Multi-site with tenant isolation | T | 1 (Organizations + RLS), 2 (MSP client mode) | D25, D68, D77 |
| 13 | Mobile/barcode/QR audit | T | 3 (technician PWA) | D70 |
| 14 | Demand intake and forecast management (reservations, runway, scenarios) | D (now a key requirement) | 1 (pools, reservations, runway), 2 (demand intake, alerts, reconciliation) | D71, D72; core, not paid |
| 15 | What-if simulation and automated placement; power-failure and redundancy simulation | D | 2 (OpenDC three questions), 3 (AI placement in ee/) | D29, D56 |
| 16 | Streaming telemetry API with replay; models-library CRUD API | D | 2 | D23, D28 |
| 17 | Browser-native game-grade twin with walkthrough; animated flow overlays | D | 1 | D15 |
| 18 | Agentless discovery | D | 2 | D51 |
| 19 | Natural-language and AI engagement (MCP server) | D | 1 (read tools), 2 (intent, operations and receiving tools), 3 (MCP Apps viewer) | D73, D74 |
| 20 | Bidirectional ServiceNow and Nlyte coexistence as first-class product features | D | 1 (read), 2 (IRE push, change, write-back where verified) | D21, D63 |
| 21 | Edge scope: server rooms, closets, IDF/MDF with floor-plan-less UX and map view | D | 1 | D67 |
| 22 | Multi-client (MSP) operation with per-client portals, metering and export | D | 2 (mode, portal, metering), 3 (branding) | D68, D69, D77 |
| 23 | Hardware receiving and onboarding with ASN import, vendor entitlements, first-power matching | D | 1 (model, importers), 2 (entitlements, staging listener), 3 (dock PWA) | D70, D79 |
