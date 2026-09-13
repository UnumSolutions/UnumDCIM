# ADR 0019: Supported-tier unit: billable site with closet rollup, weighted managed asset in MSP mode

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D57, D69, D07; Addendum B corrections C.2 item 3.

## Context

Per-cabinet pricing misprices a one-cabinet closet; per-site pricing turns a 300-closet estate into 300 sites; the metering unit becomes customer-visible after the first invoice and is effectively one-way.

## Decision

A billable site is a building or campus containing at least one data_hall, computer_room, micro_edge_dc or server_room; closet-class Locations roll up to their parent building. In MSP mode, or wherever closet-class assets exceed half of weighted assets, the Supported tier is priced on the weighted managed asset (weights 1.0 hall classes, 0.5 server room, 0.25 closet classes, 0.1 stock locations; floor of 500 weighted assets aggregated at MSP level). The per-cabinet trigger is retired. ee/ entitlements are licensed per Organization by an unweighted asset band.

## Consequences

The weight table is published before the first invoice; founder question 28 confirms the threshold.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
