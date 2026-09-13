# ADR 0015: SpaceClass: a typed class on Location only

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D67, D50, Addendum B corrections C.1 D67.

## Context

Server rooms, IT closets, IDF and MDF spaces need different feature sets from data halls; NetBox Location has no type field and NetBox declined native location classes; Nautobot LocationType alone enforces attachments; Row, Aisle and the colo cage are already distinct objects.

## Decision

A fixed SpaceClass enum applies to Location only: region, campus, building, floor, data_hall, computer_room, micro_edge_dc, server_room, equipment_room, telecom_room, main_telecom_room, entrance_facility, telecom_enclosure, and the stock locations dock, staging, burn-in and stockroom. Row, Aisle and Cage are not class values. Feature applicability (floor geometry, cooling chain, CFD, floor-plan-less UX) is defined per class. The class projects to Nautobot LocationType losslessly and to NetBox as a custom field or tag.

## Consequences

The vocabulary equivalences to TIA-942 distribution areas are editorial, not standards claims.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
