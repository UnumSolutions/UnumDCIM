# ADR 0013: Full-fidelity site bundle guaranteed for every LTS

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D44, D39, D77.

## Context

The exit path (anti-lock-in), the demo and seed mechanism, the backup of last resort, instance migration and ownership demotion all need one portable format.

## Decision

A versioned unumdcim-site bundle (manifest, newline-delimited JSON per entity in dependency order, optional Parquet telemetry, sidecar assets with per-file SPDX ids, attribution manifest, attachments) with forward-compatible loaders within a major, guaranteed for every LTS, exercised in CI on every commit. Per-client subsets exist for MSP offboarding. NetBox YAML/JSON and openDCIM XSD exports are derived views.

## Consequences

Every schema change must keep the loader forward-compatible within a major.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
