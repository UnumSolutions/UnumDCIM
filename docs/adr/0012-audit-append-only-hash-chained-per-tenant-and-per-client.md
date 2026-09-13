# ADR 0012: Audit: append-only, hash-chained per tenant and per client

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D59, D77.

## Context

Compliance buyers require tamper-evident trails and documented retention. MSP clients may demand deletion at contract end, which a single tenant-wide chain cannot honor without breaking.

## Decision

Change log and audit events are append-only tables with no UPDATE or DELETE grants for application roles. One hash chain per (tenant, client), each chain's periodic head anchored into the tenant chain, with WORM export. Retention defaults to seven years for audit and change log. GDPR erasure pseudonymizes user identity rather than deleting rows. Client offboarding exports the client chain and detaches it, leaving a tombstone in the tenant chain.

## Consequences

Chain rotation and anchoring need CLI verification tooling.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
