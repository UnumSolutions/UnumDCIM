# ADR 0008: Floor geometry: metric-first with derived grid references

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D13, D33, D67.

## Context

Peers disagree on floor coordinates (Nlyte grid references, Nautobot and GLPI tile grids, openDCIM drawing coordinates, netbox-floorplan pixels, OpenDC tiles); the 3D twin needs metric coordinates; angled rows, containment and CAD underlays cannot be expressed on a tile grid.

## Decision

Per-room origin and rotation with a declared tile grid; rack footprints from RackType outer dimensions plus yaw; grid references derived, not stored; importers run a grid-calibration step and adapters exist for each peer convention.

## Consequences

Importing from grid-only systems needs the calibration step; exports to grid systems are lossless because the grid is declared.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
