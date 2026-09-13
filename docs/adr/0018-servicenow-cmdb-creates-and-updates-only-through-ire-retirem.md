# ADR 0018: ServiceNow CMDB: creates and updates only through IRE, retirement by state update

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D63, D64, D75, D83; founder question 23.

## Context

The Identification and Reconciliation Engine is ServiceNow's sanctioned door into the CMDB; Table API writes to cmdb_ci bypass identification and reconciliation and create duplicates; IRE has no delete operation; other DCIM writers may already own placement attributes in the same CMDB.

## Decision

UnumDCIM creates and updates cmdb_ci rows only through IRE payloads with a registered discovery source and native keys; it never inserts cmdb_ci via the Table API; it retires by state update (install_status Retired or Absent, operational_status, hardware_status, life_cycle_stage), never by deletion; it removes only relationships it created, and only if the Phase 0 spike shows IRE partial payloads cannot prune them, under a narrowly scoped Table API DELETE exception on cmdb_rel_ci. Push is disabled until the setup kit's identification rules, reconciliation rules, relationship types and dictionary entries pass the connect-time probe. When another DCIM discovery source owns placement attributes, those attributes default to pull-only until a named-admin cut-over.

## Consequences

A stale foreign relation becomes a discrepancy; the customer's own archival job handles physical deletion.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
