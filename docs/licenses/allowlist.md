# Inbound license allowlist

The core is Apache-2.0 (ADR 0001). A CI check (to be added with the Phase 0 scaffold) rejects dependencies outside this list.

## Permitted in-process

Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, MPL-2.0 (file-level copyleft: modified MPL files are published), CC0-1.0 and CC-BY-4.0 for data and art, Khronos royalty-free specifications (glTF), Python-2.0, PSF-2.0, Zlib, Unlicense.

Named components already vetted: three.js, react-three-fiber, drei (note: drei's detect-gpu must point at a self-hosted benchmark URL; hls.js in its tree is Apache-2.0), Babylon.js, Telegraf, snmp_exporter, ipmi_exporter, gofish, pymodbus, BACpypes3, Keycloak, OpenFGA, OpenBao, ClickHouse, Valkey, NATS, statsmodels, statsforecast, hierarchicalforecast, scikit-learn, sktime, Darts, GluonTS, the official MCP Python SDK (`mcp`), FastMCP 4, django-oauth-toolkit (BSD-2-Clause), django-rls, pgrls, MapLibre GL JS, ezdxf, dxf-parser, three-dxf, web-ifc (MPL-2.0), ThatOpen components, ACadSharp (MIT, .NET, isolated by choice), OpenDC (MIT, JVM, isolated by choice), FlowGate's Nlyte client (BSD-2, attribution retained), pshenok/datacenter-survival simulation modules (MIT, attribution retained), draw.io VSSX importer logic (Apache-2.0), Apache POI, netbox-inventory, CESNET inventory-monitor-plugin, netbox-lifecycle, netbox-qrcode, html5-qrcode, quagga2, netbox-mcp-server (as a reference shape), the netbox-community and nautobot devicetype-library corpora (CC0-1.0), Nautobot SSoT and DiffSync, nautobot-app-data-validation-engine, Ironic (reference only), Apache Kafka (Apache-2.0; optional at scale, Confluent add-ons excluded), pyVmomi (Apache-2.0), Kopf (MIT), PixiJS, Konva and Fabric.js (MIT; not selected but permitted), django-tenants and django-multitenant (MIT; schema and composite-key patterns only), python vsdx (BSD-3-Clause), OpenUSD (Tomorrow Open Source Technology License 1.0, Apache-2.0-derived; server-side export only), the ServiceNow/ServiceNowDocs documentation mirror (Apache-2.0; documentation, not code), jschuller/mcp-server-servicenow (MIT; reference only), django-mcp-server and mcp-django (MIT; evaluated and rejected as runtimes), Prophet and NeuralProphet (MIT; evaluated and rejected, not to be adopted).

First-party components declared here so the allowlist check can name them: the in-house X12 856 segment reader; the Visio OOXML reader; the staging-VLAN listener; the per-manufacturer default-credential recipe data file.

## Permitted only as an isolated container or command-line process (never linked)

libvisio2svg and libemf2svg (GPL-2.0), LibreDWG (GPL-3.0-or-later), OpenFOAM (GPL), Nominatim (GPL-3.0-or-later Python, GPL-2.0 other files; OpenStreetMap data under ODbL is a separate question with counsel), Grafana server (AGPL-3.0; only dashboard JSON is shipped), Zabbix (AGPL-3.0; not shipped), MinIO (AGPL-3.0; not bundled; customers supply their own S3-compatible endpoint).

## Not permitted

GNU GPL or AGPL code copied into the core in any form (openDCIM, RackTables, GLPI, i-doit, Snipe-IT, dctycoon sprites and models); unlicensed repositories (championswimmer/datacenter-tycoon, OpenDT); NetBox Limited Use License components (Diode server and plugin, netbox-branching); HashiCorp Vault (BSL 1.1; supported only as a customer-provided backend); Redis 8 under SSPL or RSAL (use Valkey); TimescaleDB Toolkit and the `tsl/` tree in any hosted offering without counsel review; Aspose.Diagram and other commercial OEM SDKs; Icecat data merged into `library-core`; vendor Visio stencil art, NetZoom or ShapeSource stencils, GrabCAD models, non-CC Sketchfab models; ODA Drawings SDK; NVIDIA Omniverse and Kit as a dependency (non-OSI, NVIDIA-platform-only; OpenUSD export-only interoperability is permitted).

## Data and art in `library-core`

CC0-1.0 definitions and CC-BY-4.0 authored art only, each file carrying its SPDX identifier and provenance; CC-BY-SA assets are quarantined to a share-alike-marked pack; everything else lives in the tenant-private `library-sidecar` and is never redistributed.
