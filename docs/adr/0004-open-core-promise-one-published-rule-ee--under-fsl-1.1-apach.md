# ADR 0004: Open-core promise: one published rule, ee/ under FSL-1.1-Apache-2.0

- **Status:** accepted
- **Date:** 2026-09-12
- **Related decisions:** D05, D72, D07.

## Context

Comparables disagree on where the paywall sits. The founder made demand and forecast management a key requirement, which moved forecasting from the paid tier into the core. The promise that the core and connectors are never fenced must be one-way and published before v1.

## Decision

Free forever (Apache-2.0 core): twin, library, all ingestion and sync connectors, OIDC/SAML/LDAP, MFA, SCIM 2.0, object and field-level RBAC, change log, webhooks, OpenDC integration, air-gap install, LTS releases, single-Organization demand and forecast management (ResourcePool, Reservation, DemandRequest, Runway, Scenario, runway with intervals, headroom dashboards, alerts, ServiceNow demand mirror, MSP client and site rollups within one Organization), and the MCP server with all its tools. The ee/ directory, licensed FSL-1.1-Apache-2.0 (each version converts to Apache-2.0 on its second anniversary), fences only: multi-Organization portfolio rollups (cross-tenant aggregation), ML auto-model selection and ensembles, AI placement optimization, portfolio Monte Carlo, procurement-lead-time optimization, colo revenue analytics with rate plans, audit-event streaming, hosted control plane, certified-connector packaging, extended-support backports. This rule appears in exactly one form in README.md, this ADR, 00-walkthrough.md D05 and 02-addendum-b.md D72.

## Consequences

Revenue comes from support tiers, services and the FSL tier; nothing in the free list may be moved behind the fence later.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
