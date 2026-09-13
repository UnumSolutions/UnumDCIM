# ADR 0017: MCP server placement and authorization model

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D73, D74, D81.

## Context

AI assistants must engage with the system directly; the current MCP specification (2026-07-28) is stateless with OAuth 2.1 authorization; stock django-oauth-toolkit issues opaque tokens with a static scope list and an unauthenticated dynamic-registration endpoint; hosted clients need an internet-reachable endpoint that the self-hosted posture does not admit by default.

## Decision

The MCP server is mounted inside unum-core at /mcp over Streamable HTTP only, targeting specification 2026-07-28 with dual-era serving of 2025-11-25 and 2025-06-18 clients. The endpoint is an OAuth 2.1 resource server; django-oauth-toolkit is the authorization server issuing opaque access tokens verified in-process; Organization, client and site grants are resolved from RBAC at verification time and shown on the consent screen, never encoded as scopes; only capability scopes are OAuth scopes. Enterprise and air-gap installs default to pre-registered clients with DCR off and CIMD off; hosted clients require a deliberately published endpoint. Reads are annotated read-only; writes create ChangeRequest intents; execution requires prior approval by a different principal.

## Consequences

Keycloak remains the air-gap IdP behind django-oauth-toolkit until its resource-indicator support is released. Client fragmentation across protocol eras is handled by the dual-era server and a published client matrix.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
