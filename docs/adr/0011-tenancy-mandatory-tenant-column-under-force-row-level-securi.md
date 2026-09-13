# ADR 0011: Tenancy: mandatory tenant column under FORCE row-level security with a non-owner application role

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D25, D58, D68, D77.

## Context

Colocation and MSP buyers need hard isolation; NetBox-style label tenancy is not enough. PostgreSQL row-level security is bypassed by table owners unless forced, by superusers and BYPASSRLS roles, and by referential-integrity checks.

## Decision

Every table carries a mandatory tenant column; policies are created with FORCE ROW LEVEL SECURITY; the application connects as a non-owner role; BI views are exposed only through per-tenant non-owner roles; the OData feed runs through the application layer; composite (id, tenant_id) keys make cross-tenant references impossible at schema level; a lint and isolation test suite runs every release. Schema-per-tenant is reserved for instance-per-client packaging.

## Consequences

Query complexity increases; PgBouncer, if used, must run in transaction pooling mode.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
