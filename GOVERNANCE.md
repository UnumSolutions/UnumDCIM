# Governance

## Licensing promise

The UnumDCIM core, its connectors, asset tooling, collectors and MCP server are licensed under the Apache License 2.0 and will not be relicensed. Software under the GNU GPL or AGPL is used only as process-isolated services with an HTTP or command-line boundary, never linked in-process. The open-core boundary is published in `README.md` and ADR 0004 and has exactly one form; items on the free list are never moved behind the fence.

## Contribution agreements

- Core: Developer Certificate of Origin (sign-off on every commit). No CLA.
- `ee/`: a Contributor License Agreement is required, because that directory is licensed FSL-1.1-Apache-2.0.

## Decision making

Decisions that are one-way doors are recorded as ADRs in `docs/adr/` with status `proposed` or `accepted`. Changes to an accepted ADR require a new ADR that supersedes it. The founding decision record lives in `docs/decisions/`.

## Trademark

"UnumDCIM" is a trademark of the project's steward. Referential use (saying that a product integrates with UnumDCIM) is permitted. Using the mark on modified derivatives, product names or domains is not. The project never uses the NetBox mark in its own name.

## Maintainers and the foundation question

The project is single-vendor stewarded at launch with this public charter. Donation of the Apache-2.0 core to a neutral foundation is revisited when three or more independent maintainers are active. The library-contribution program grants a governance seat to top library contributors.

## Dependencies on third-party licensed components

The project does not depend on any component licensed under the NetBox Limited Use License (Diode server and plugin, netbox-branching) or on other non-OSI source-available components in the core. See `docs/licenses/allowlist.md`.
