"""Connection-scoped v1 reconciliation. Unknown optional fields are ignored.

This is a pure planner. Remote side effects remain the adapter executor's job.
"""
from dataclasses import dataclass
from typing import Any, Mapping
from .reconcile import Decision, Scope, digest, PLACEMENT_PARTS, validate_observation


@dataclass(frozen=True)
class Observation:
    scope: Scope
    connection: str
    observation_id: str
    revision: str
    values: Mapping[str, Any]
    contract: str = "unum.observation/1"
    complete: bool = True


@dataclass(frozen=True)
class MappingContract:
    version: str
    field_types: Mapping[str, str]
    owners: Mapping[str, str]


TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool,
         "object": dict, "array": list}


def _validate_observation(observation, scope, connection):
    validate_observation(observation, scope)
    if (not isinstance(observation.connection, str) or not observation.connection.strip()
            or observation.connection != connection):
        raise ValueError("Invalid observation connection")
    if observation.contract != "unum.observation/1":
        raise ValueError("Unsupported observation contract")


def _field_digest(values, field, kind):
    """Return no digest for missing, incompatible or non-JSON field values."""
    if field not in values:
        return None
    value = values[field]
    if value is not None and (not isinstance(value, TYPES[kind]) or
            (kind in {"integer", "number"} and isinstance(value, bool))):
        return None
    try:
        return digest(value)
    except (ValueError, TypeError):
        return None


def reconcile(scope, baseline, peers, mapping, writable, previous=None):
    if len(peers) != 2 or len({p.connection for p in peers}) != 2:
        raise ValueError("One reconciliation pair requires two distinct connections")
    if mapping.version != "unum.mapping/1":
        raise ValueError("Unsupported mapping contract")
    if set(mapping.field_types) & PLACEMENT_PARTS:
        raise ValueError("Normalize rack placement into one atomic placement field")
    if not isinstance(baseline, Mapping):
        raise ValueError("Baseline must contain mapped field values")
    connections = {p.connection for p in peers}
    for p in peers:
        _validate_observation(p, scope, p.connection)
    if previous is not None:
        if set(previous) != connections:
            raise ValueError("Previous observations do not match connections")
        for name, p in previous.items():
            _validate_observation(p, scope, name)
    result = []
    for field, kind in sorted(mapping.field_types.items()):
        owner = mapping.owners.get(field)
        if owner not in connections or kind not in TYPES or field not in baseline:
            result.append(Decision(field, "quarantined", "Missing baseline, owner or supported field type"))
            continue
        baseline_hash = _field_digest(baseline, field, kind)
        current_hashes = {p.connection: _field_digest(p.values, field, kind) for p in peers}
        previous_hashes = {name: _field_digest(p.values, field, kind)
                           for name, p in previous.items()} if previous is not None else {}
        if any(value is None for value in
               (baseline_hash, *current_hashes.values(), *previous_hashes.values())):
            result.append(Decision(field, "quarantined", "Mapped field missing or incompatible; other fields continue"))
            continue
        a, b = peers
        if current_hashes[a.connection] == current_hashes[b.connection]:
            result.append(Decision(field, "converged", "Both peers agree", value=a.values[field]))
            continue
        stable = previous is not None and all(
            previous[p.connection].observation_id != p.observation_id and
            previous_hashes[p.connection] == current_hashes[p.connection] for p in peers)
        if not stable:
            result.append(Decision(field, "pending", "Await repeated divergence"))
            continue
        changed = [p for p in peers if current_hashes[p.connection] != baseline_hash]
        if len(changed) == 2:
            result.append(Decision(field, "conflict", "Both connections changed; review required"))
            continue
        source = changed[0]
        target = b if source is a else a
        if field not in writable.get(target.connection, set()):
            result.append(Decision(field, "blocked", "Write capability not verified", target.connection))
            continue
        value = source.values[field]
        preimage = current_hashes[target.connection]
        key = digest([scope.tenant, scope.connection, scope.entity, mapping.version,
                      field, source.connection, target.connection, owner, value, target.revision, preimage])
        result.append(Decision(field, "mirror" if owner == source.connection else "intent",
            "Owner projection" if owner == source.connection else "Stage through owner",
            target.connection, value, target.revision, preimage, key))
    return tuple(result)
