# ADR 0003: Stack: Python/Django control plane, TypeScript/React + three.js twin, isolated JVM and .NET sidecars

- **Status:** accepted
- **Date:** 2026-09-12
- **Related decisions:** D09, D14, D28, D29, D79.

## Context

The DCIM/source-of-truth segment is overwhelmingly Python/Django (NetBox, Nautobot); the reusable integration libraries (pynetbox, DiffSync, ezdxf, vsdx, BACpypes3, pymodbus, usd-core, statsmodels, statsforecast, the official MCP Python SDK, django-oauth-toolkit) are Python; browser twins need TypeScript and a WebGL engine; OpenDC is JVM-only and ACadSharp is .NET.

## Decision

Python 3.12 / Django 5.2 LTS with DRF, drf-spectacular and Strawberry for the control plane; TypeScript/React/Vite with three.js, react-three-fiber and drei for the twin; a deterministic simulation core in TypeScript; Go only as an unmodified Telegraf binary plus a small Redfish poller if needed; JVM (OpenDC) and .NET (ACadSharp) only as isolated containers; a small Python staging listener in the Collector image.

## Consequences

Two application languages only. The ORM and migration language is fixed for the life of the product.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
