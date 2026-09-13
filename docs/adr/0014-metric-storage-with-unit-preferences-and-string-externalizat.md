# ADR 0014: Metric storage with unit preferences and string externalization from Phase 1

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D36.

## Context

Nlyte and FNT customers include German-speaking estates; imperial versus metric display is a user preference; retrofitting string externalization and unit handling is far costlier than doing it first.

## Decision

All quantities are stored metric (mm, kg, W, degrees Celsius, litres) and rendered per user or tenant preference; the API is always metric with explicit unit fields; every UI string is externalized from Phase 1 with RTL-safe layouts.

## Consequences

Community translations follow in Phase 2.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
