# ADR 0001: License: Apache-2.0 core, permanent

- **Status:** accepted
- **Date:** 2026-09-12
- **Related decisions:** D04, D02, D06, D08; Addendum B corrections C.4 item 9 (license checks for django-oauth-toolkit and Nominatim).

## Context

The core license decides which upstream code and art can be vendored, whether enterprises and partners can embed the product, and whether hosted competitors can run it. Every relicensing away from an OSI license among the comparables that produced a fork did so at high cost (Terraform to OpenTofu, Redis to Valkey). All high-value reuse candidates found in research are MIT, BSD, Apache-2.0 or CC0; the GPL material (openDCIM, RackTables, GLPI, dctycoon art, libvisio2svg, LibreDWG, OpenFOAM, Nominatim) is only usable as isolated services.

## Decision

The core, connectors, asset tooling, collectors and the MCP server are licensed Apache-2.0, declared permanent in GOVERNANCE.md. GPL and AGPL software is admitted only as process-isolated containers with an HTTP or CLI boundary, never linked in-process, and never as an in-process theme or plugin. The core is never relicensed.

## Consequences

Enables reuse of the whole permissive ecosystem and upstream contributions to NetBox and Nautobot. Excludes dctycoon's isometric art and all GPL DCIM code. A CI license-allowlist check (docs/licenses/allowlist.md) enforces the rule.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
