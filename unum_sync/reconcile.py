"""Conservative three-way reconciliation of explicitly linked asset records.

Snapshots contain normalized, allowlisted business fields only. The baseline is
the last value verified equal in BOTH peers, never merely the last poll.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Optional, Tuple


SYSTEMS = frozenset({"nlyte", "unum"})
PLACEMENT_PARTS = frozenset({"rack", "rack_id", "u", "position", "face"})


def digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def validate_observation(snapshot, scope):
    """Require the same complete poll provenance for current and prior data."""
    if (snapshot.scope != scope or snapshot.complete is not True or
            not all(isinstance(value, str) and value.strip()
                    for value in (snapshot.revision, snapshot.observation_id)) or
            not isinstance(snapshot.values, Mapping)):
        raise ValueError("Incomplete or mismatched observation")


@dataclass(frozen=True)
class Scope:
    tenant: str
    connection: str
    entity: str

    def __post_init__(self):
        if not all(isinstance(v, str) and v.strip() for v in
                   (self.tenant, self.connection, self.entity)):
            raise ValueError("Tenant, connection and linked entity are required")


@dataclass(frozen=True)
class Snapshot:
    scope: Scope
    system: str
    revision: str
    observation_id: str
    values: Mapping[str, Any]
    complete: bool = True


@dataclass(frozen=True)
class Decision:
    field: str
    kind: str
    reason: str
    target: Optional[str] = None
    value: Any = None
    expected_revision: Optional[str] = None
    expected_hash: Optional[str] = None
    operation_key: Optional[str] = None


def plan(*, scope: Scope, baseline: Mapping[str, Any], nlyte: Snapshot,
         unum: Snapshot, owners: Mapping[str, str],
         writable: Mapping[str, frozenset],
         previous: Optional[Mapping[str, Snapshot]] = None) -> Tuple[Decision, ...]:
    """Return reviewable decisions only; never execute or acknowledge writes.

    Non-owner edits become change intents to the owner. Conflicting edits stay
    unresolved. A repeated divergence must be seen in two distinct complete
    snapshots before it surfaces. `writable` is verified adapter capability,
    not authorization. Execution additionally requires D47 controls.
    """
    peers = {"nlyte": nlyte, "unum": unum}
    fields = set(baseline)
    if not fields or fields != set(owners) or not set(owners.values()) <= SYSTEMS:
        raise ValueError("Every baseline field needs exactly one valid owner")
    if fields & PLACEMENT_PARTS:
        raise ValueError("Normalize all rack placement components into placement")
    for system, snapshot in peers.items():
        validate_observation(snapshot, scope)
        if snapshot.system != system:
            raise ValueError("Snapshot scope/system mismatch")
        if set(snapshot.values) != fields:
            raise ValueError("Incomplete snapshot or schema drift; pause reconciliation")
        digest(snapshot.values)  # Reject non-JSON data and nonfinite numbers.
    digest(baseline)
    if previous is not None:
        if set(previous) != SYSTEMS:
            raise ValueError("Previous poll must include both peers")
        for system, snapshot in previous.items():
            validate_observation(snapshot, scope)
            if snapshot.system != system or set(snapshot.values) != fields:
                raise ValueError("Invalid previous snapshot")
            digest(snapshot.values)

    decisions = []
    for field in sorted(fields):
        left, right, base = nlyte.values[field], unum.values[field], baseline[field]
        if digest(left) == digest(right):
            decisions.append(Decision(field, "converged", "Both peers agree", value=left))
            continue
        stable = previous is not None and all(
            previous[s].observation_id != peers[s].observation_id and
            digest(previous[s].values[field]) == digest(peers[s].values[field])
            for s in SYSTEMS)
        if not stable:
            decisions.append(Decision(field, "pending", "Await a second distinct complete observation"))
            continue
        changed = {s for s in SYSTEMS if digest(peers[s].values[field]) != digest(base)}
        if len(changed) == 2:
            decisions.append(Decision(field, "conflict", "Both systems changed since verified agreement"))
            continue
        source = next(iter(changed))
        target = next(iter(SYSTEMS - {source}))
        owner = owners[field]
        if field not in writable.get(target, frozenset()):
            decisions.append(Decision(field, "blocked", "Target write capability is unverified", target))
            continue
        value = peers[source].values[field]
        preimage = digest(peers[target].values[field])
        key = digest([scope.tenant, scope.connection, scope.entity, field, source,
                      target, owner, value, peers[target].revision, preimage])
        decisions.append(Decision(
            field, "mirror" if source == owner else "intent",
            "Project owner value" if source == owner else
            "Stage edit for owner approval; canonical value remains unchanged",
            target, value, peers[target].revision, preimage, key))
    return tuple(decisions)
