# ADR 0016: Client/Party entity and the two table families for MSP operation

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D68, D77, D69.

## Context

One MSP console must serve many clients with cross-client rollups for MSP staff, strict scoping for client users, per-client credentials, per-client export and reversible MSP mode. Nullable client columns are the classic RLS leak.

## Decision

Client is a Party with MSP scoping beneath an MSP Organization; TenantAllocation references a Party so colo tenants and MSP clients share one portal and scoping model. Tables are either client-scoped (NOT NULL client_id with composite (id, tenant_id, client_id) keys) or MSP-shared (no client_id column); shared physical resources belong to a reserved MSP-self client. Each request runs one transaction that sets the tenant id and an array of permitted client ids; policies test membership. MSP mode is reversible per install.

## Consequences

Two table families double the migration discipline; the isolation test suite includes monitor reads and MCP paths.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
