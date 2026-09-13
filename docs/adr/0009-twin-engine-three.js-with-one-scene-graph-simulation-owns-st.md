# ADR 0009: Twin engine: three.js with one scene graph, simulation owns state

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D14, D15, D29, D35, D67 correction 3.

## Context

Commercial data-center games are native Unity/Unreal titles, which an open-source, air-gapped, browser product cannot be. Dual 2D/3D scene state is the sync-bug factory the games' co-op changelogs document. The pshenok games prove a headless deterministic simulation with read-only renderers.

## Decision

three.js + react-three-fiber + drei (MIT), vendored and pinned, WebGL2 first-class with WebGPU optional; one scene graph serving plan, elevation, orbit and walk modes with an SVG/HTML overlay for labels and print; the map view is a separate route. A headless deterministic simulation owns state; renderers only read it and write only through ChangeRequest intents. Explicit budgets are validated in a Phase 0 spike on an Intel iGPU and a VDI software preset before product code is written.

## Consequences

Babylon.js remains a viable engine swap; the one-scene-graph and sim-owns-state rules do not change.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
