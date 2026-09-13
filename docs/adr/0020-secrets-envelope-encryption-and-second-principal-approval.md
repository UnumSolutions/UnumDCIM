# ADR 0020: Secrets: envelope encryption with a pluggable KMS; control actions need a second principal

- **Status:** proposed
- **Date:** 2026-09-12
- **Related decisions:** D25b, D79, D74 correction 7; Addendum A D25b.

## Context

A DCIM stores thousands of SNMPv3 keys, Modbus and BACnet endpoints, Redfish and IPMI passwords, Nlyte, NetBox and ServiceNow API credentials and, later, outlet-control, door-lock and BMC credentials. FIPS and FedRAMP reviews fail without key management, rotation and scoped delivery; a single Django field key offers none of these.

## Decision

Credential fields are protected by envelope encryption: per-tenant data keys wrapped by a master key from a pluggable backend (local key file for the reference install, OpenBao, a customer-provided HashiCorp Vault, or a cloud KMS). Credentials reach collectors and the staging listener only as short-lived, site-scoped leases; rotation is a workflow that re-encrypts and re-leases; a documented FIPS mode selects a validated OpenSSL provider. Any control action (outlet switch, door unlock, firmware push, BMC AssetTag write) and any execution of a ChangeRequest intent requires approval by a principal other than the proposer, an execution window and an immutable audit record; an elicitation or confirmation in the same session never counts as approval.

## Consequences

Envelope encryption is a one-way schema decision; backends are swappable. MCP clients can propose but never approve their own proposals.

## Evidence

See `docs/decisions/01-addendum-a.md` D25b and `docs/decisions/02-addendum-b.md` D74 correction 7 and D79.
