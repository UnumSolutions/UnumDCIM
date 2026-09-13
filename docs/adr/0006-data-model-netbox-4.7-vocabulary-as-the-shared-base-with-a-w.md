# ADR 0006: Data model: NetBox 4.7 vocabulary as the shared base with a written deviations list

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D11, D13, D50, D67, D70, D71.

## Context

The schema is the product in a greenfield system of record; it must round-trip NetBox 4.x/5.0 and Nautobot losslessly, map Nlyte and ServiceNow entities, and carry what none of them have (upstream power chain, cooling chain, metric geometry, typed spaces, procurement, demand).

## Decision

The shared subset is NetBox 4.7 vocabulary (Region/SiteGroup/Site/Location, RackGroup, RackType-first physical attributes, Rack, DeviceType/ModuleType, Module/ModuleBay, ports with mappings, Cable, PowerPanel/PowerFeed/PowerPort/PowerOutlet, Cooling objects, Tenant, CustomField, Tag). Extensions are recorded in a versioned deviations list: multi-port feeds, PowerSource above panels, cooling loops as connections, metric geometry, typed SpaceClass, Asset separate from Device, procurement objects, ResourcePool and demand objects, Client/Party. Library types are keyed by NetBox slug; instances by UUIDv7. The shared subset freezes at v1.0.

## Consequences

Every importer maps to and from the shared subset with version-pinned mappers; deviations are documented rather than silent.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
