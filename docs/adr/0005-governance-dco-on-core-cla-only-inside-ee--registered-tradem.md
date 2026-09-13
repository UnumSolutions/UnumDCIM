# ADR 0005: Governance: DCO on core, CLA only inside ee/, registered trademark, foundation revisited later

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D06, D31.

## Context

CLA-versus-DCO, vendor-versus-foundation and trademark ownership are linked decisions. CNCF requires Apache-2.0, DCO and trademark transfer; the NATS/Synadia dispute ended with the mark assigned to the Linux Foundation; GitLab uses DCO outside ee/ and a CLA inside it.

## Decision

Contributions to the core are accepted under the Developer Certificate of Origin; contributions to ee/ require a CLA. The UnumDCIM mark is registered now with a Grafana/LF-style policy (referential use allowed; no marks on modified derivatives, product names or domains). The product never uses the NetBox mark. No dependency on NetBox Labs' Limited-Use-licensed components. Foundation donation of the Apache core is revisited at three or more independent maintainers.

## Consequences

Two contribution regimes to explain. The CLA decision must precede the first external pull request.

## Evidence

See `docs/decisions/00-walkthrough.md`, `docs/decisions/01-addendum-a.md` and `docs/decisions/02-addendum-b.md` for the options considered, the objections to each, the cited sources and the verification status of every claim; `docs/fact-sheet.md` lists the verified facts with URLs.
