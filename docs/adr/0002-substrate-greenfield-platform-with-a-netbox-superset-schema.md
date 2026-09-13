# ADR 0002: Substrate: greenfield platform with a NetBox-superset schema

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D01, D02, D22, D40; judge panel verdict in 00-walkthrough.md.

## Context

NetBox's plugin API is documented-surface-only; facilities management is out of scope; the power model stops at the Power Panel; GraphQL is read-only; three minor releases a year carry infrastructure breaks and v5.0 changes the Rack model; NetBox Labs licenses Diode and Branching under a non-compete Limited Use License; Nautobot shows a fork is viable only with a sustaining company. A facilities buyer cannot make NetOps' upgrade schedule a precondition of a DCIM purchase.

## Decision

UnumDCIM is a greenfield Django platform whose schema is a strict superset of NetBox 4.7 vocabulary. NetBox, Nautobot, Nlyte and ServiceNow are sync peers with first-class adapters. No NetBox plugin bundle masters data inside NetBox; no fork. NetBox's vocabulary, permission-constraint design, change-log design and REST conventions are ported verbatim under Apache-2.0. A thin optional NetBox plugin (deep-link tab plus event-rule action) may ship later.

## Consequences

Rebuilds permissions, change log, bulk import and API conventions as ports rather than inventions. Requires versioned mappers per NetBox release and a compatibility policy (current and previous minor).

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
