# ADR 0007: Provenance, one owner per field, placement as one fact, identity precedence

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D12, D40, D46, D64, D76; Addendum B corrections C.2 items 4, 5, 6.

## Context

Coexistence with Nlyte, NetBox and ServiceNow means the same asset has several candidate owners per field. A field with two owners is split-brain; a field with no defined owner cannot be reconciled. Rack placement encoded twice (metric geometry versus a peer's grid reference) would reopen a discrepancy on every snapshot.

## Decision

Every object carries a Provenance mixin. An OwnershipPolicy names exactly one owning system per (tenant, entity, field); only the owner writes canonical values, other systems' values land in staging and surface in a discrepancy queue with owner-wins default and logged overrides. External IDs live in an ExternalReference crosswalk and are never primary keys. Placement is one fact: a twin edit is a ChangeRequest intent rendered as a ghost until the owner confirms. Identity fields (serial number, asset tag, MAC) follow an ordered per-tenant precedence list (default ServiceNow HAM, then the UnumDCIM Asset, then NetBox; first recorder breaks ties). Any override of an externally owned field is a staged value plus a logged discrepancy override, never a canonical write. Ownership is promoted to UnumDCIM per site and per entity type through a reversible, audited promotion (the ratchet of D01/D12/D39); demotion is allowed only where a verified write-back path exists.

## Consequences

Ownership is visible everywhere in the UI, API and MCP; sync engines are snapshot-hash based with a two-snapshot persistence rule.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
