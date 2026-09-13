# Founder questions

Answered: 1 funnel (balanced), 2 hosted cloud (no, 24 months), 3 license (Apache-2.0), deliverable (docs + ADRs + hygiene).

Open, with the recommended default in parentheses:

4. Paywall owner: facilities operator free vs IT management/compliance paid (buyer-based rule as written).
5. Foundation trajectory: single-vendor with charter now (recommended) vs seeding an LF/CNCF path at launch.
6. Pursue the Nlyte Technology Partner Program? (Only after a design partner requests certified write-back.)
7. Thermal ambition ceiling: sensor/estimate only (recommended), isolated OpenFOAM, or vendor CFD connectors.
8. First-person walk mode: behind a toggle (recommended), deferred, or technician PWA first.
9. Launch-critical compliance gates: SOC 2 (cloud), WCAG 2.2 AA (public sector), FIPS/FedRAMP 20x (US federal).
10. Commission a CC-BY-4.0 stylized facility art set before launch? (Yes if budget allows.)
11. Binary .vss on day one? (Phase 2.)
12. Is there an Nlyte customer who can be the Phase 0 design partner? (Required for the balanced funnel.)
13. MSP unit of tenancy: Client as a Party beneath the MSP Organization (recommended) or Client as a full Organization with an umbrella role.
14. Per-client data residency inside one install? (If yes, instance-per-region packaging.)
15. Does the design partner run ServiceNow HAM Pro and SPM? (Decides receiving-slip, normalization and demand paths.)
16. MCP execution policy: `unum.change.execute` only after a different principal approves in the UI or ServiceNow (recommended) or never via MCP.
17. Which MCP clients must be supported at launch? (Local clients; hosted clients as a documented deviation.)
18. Metering unit MSPs will accept: weighted managed asset (recommended), per site, per client or per user.
19. Phase 0 ServiceNow test target: partner sub-production instance (recommended) or PDI only.
20. Move the closet-first technician workflow ahead of Phase 3 if an MSP design partner signs? (Yes if signed.)
21. Budgeting policy defaults (percentile, window, margin) and opt-in per tenant until counsel reviews the freedom-to-operate note.
22. Does any target customer model DCIM-managed rooms as CSDM 5 Facility Service Instances? (Adds a CSDM layer to D64 if so.)
23. Table API DELETE exception for `cmdb_rel_ci` when IRE cannot prune relations: acceptable (recommended, narrowly scoped) or never.
24. Demand push into `dmn_demand`: ever, or mirror-only permanently? (Mirror-only until a partner instance exists.)
25. Hosted MCP clients: will target customers publish `/mcp`? (Local clients only at launch.)
26. Per-client audit chain detachment: does "content leaves with the client" satisfy expected MSP customers, or must the MSP retain a sealed copy?
27. Staffing trigger: confirm the +1 integration engineer is contingent on a signed ServiceNow-shop partner.
28. Supported-tier unit switch: the 50%-weighted-closet threshold, or "MSP mode always weighted asset".

---


## Recorded answers (2026-09-08)

| Question | Answer | Effect |
|----------|--------|--------|
| Core license | Apache-2.0 | ADR 0001 accepted. |
| Hosted cloud within 24 months | No, self-hosted only | TimescaleDB Community default; SOC 2 slides to Phase 3; Cloud tier out of Phase 2. |
| Year-one funnel | Balanced | Phase 1 ships the NetBox twin and the Nlyte Collector; an Nlyte design partner must sign by end of Phase 0. |
| Deliverable on approval | Decision docs, ADRs, repo hygiene | This repository's `docs/` and root files; no application scaffold yet. |
