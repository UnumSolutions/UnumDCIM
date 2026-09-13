# ADR 0010: Asset library: two physical stores, CC0 core and tenant-private sidecar

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D08, D17, D18, D19, D45, D61.

## Context

Only the netbox-community and nautobot devicetype-library corpora are cleanly redistributable (CC0-1.0). Icecat, vendor Visio stencils, GrabCAD, most Sketchfab models and commercial DCIM libraries are not. CC0 cannot clear third-party rights in contributed images.

## Decision

library-core (CC0 definitions and CC-BY-4.0 authored art, shipped) and library-sidecar (per-tenant, user-fetched, SPDX-tagged, never merged) are two physical stores enforced in code and CI. Procedural SVG and glTF from dimensions are the always-available default. An image-rights audit, contributor attestation and a takedown policy precede the first public pack. Nothing vendor-derived is bundled; fetch recipes run user-side under the user's own credentials.

## Consequences

UnumDCIM-authored definitions flow upstream to netbox-community under CC0.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
