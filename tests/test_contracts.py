from dataclasses import replace
from datetime import date
import pytest
from unum_sync.contracts import MappingContract, Observation, reconcile
from unum_sync.reconcile import Scope
from platform_core.compatibility import check_install


def inputs():
    scope = Scope("t", "customer-instance-7", "asset-a")
    a = Observation(scope, "nlyte-instance-7", "poll-2", "etag-a", {"name": "new", "tag": "old", "future_optional": 42})
    b = Observation(scope, "unum-site-1", "poll-2", "etag-b", {"name": "old", "tag": "old"})
    mapping = MappingContract("unum.mapping/1", {"name": "string", "tag": "string"}, {"name": a.connection, "tag": a.connection})
    return dict(scope=scope, baseline={"name": "old", "tag": "old"}, peers=[a, b], mapping=mapping,
                writable={b.connection: {"name", "tag"}}, previous={p.connection: replace(p, observation_id="poll-1") for p in (a, b)})


def test_optional_fields_and_connection_ids():
    result = reconcile(**inputs())
    assert [(d.field, d.kind) for d in result] == [("name", "mirror"), ("tag", "converged")]
    assert result[0].target == "unum-site-1"


def test_quarantine_one_field_without_blocking_other():
    args = inputs()
    args["peers"][0] = replace(args["peers"][0], values={"name": "new", "tag": {"unexpected": True}})
    assert [d.kind for d in reconcile(**args)] == ["mirror", "quarantined"]


def test_missing_field_is_not_deletion():
    args = inputs()
    args["peers"][0] = replace(args["peers"][0], values={"name": "new"})
    assert reconcile(**args)[1].kind == "quarantined"


def test_unknown_major_fails_closed():
    args = inputs()
    args["peers"][0] = replace(args["peers"][0], contract="unum.observation/2")
    with pytest.raises(ValueError):
        reconcile(**args)


def test_partial_snapshot_cannot_advance():
    args = inputs()
    args["peers"][0] = replace(args["peers"][0], complete=False)
    with pytest.raises(ValueError):
        reconcile(**args)


@pytest.mark.parametrize("poll", ["current", "previous"])
@pytest.mark.parametrize("field", ["observation_id", "revision"])
@pytest.mark.parametrize("invalid", ["", " ", None, 1])
def test_invalid_poll_provenance_cannot_confirm_divergence(poll, field, invalid):
    args = inputs()
    if poll == "current":
        args["peers"][0] = replace(args["peers"][0], **{field: invalid})
    else:
        connection = args["peers"][0].connection
        args["previous"][connection] = replace(args["previous"][connection], **{field: invalid})
    with pytest.raises(ValueError, match="Incomplete or mismatched observation"):
        reconcile(**args)


@pytest.mark.parametrize("source", ["baseline", "current", "previous"])
@pytest.mark.parametrize("kind,old,new,invalid", [
    ("string", "old", "new", 42),
    ("integer", 1, 2, True),
    ("number", 1, 2, float("nan")),
    ("object", {"value": 1}, {"value": 2}, {"value": float("inf")}),
    ("array", [1], [2], [object()]),
])
def test_invalid_field_is_quarantined_across_all_observations(source, kind, old, new, invalid):
    args = inputs()
    args["mapping"] = replace(args["mapping"], field_types={"name": kind, "tag": "string"})
    args["baseline"] = {"name": old, "tag": "old"}
    args["peers"] = [replace(args["peers"][0], values={"name": new, "tag": "new"}),
                     replace(args["peers"][1], values={"name": old, "tag": "old"})]
    args["previous"] = {p.connection: replace(p, observation_id="poll-1") for p in args["peers"]}
    if source == "baseline":
        args["baseline"]["name"] = invalid
    elif source == "current":
        args["peers"][0] = replace(args["peers"][0], values={"name": invalid, "tag": "new"})
    else:
        connection = args["peers"][0].connection
        args["previous"][connection] = replace(args["previous"][connection],
                                                values={"name": invalid, "tag": "new"})
    assert [(d.field, d.kind) for d in reconcile(**args)] == [("name", "quarantined"), ("tag", "mirror")]


def test_missing_historical_field_is_quarantined():
    args = inputs()
    connection = args["peers"][0].connection
    args["previous"][connection] = replace(args["previous"][connection], values={"tag": "old"})
    assert [(d.field, d.kind) for d in reconcile(**args)] == [("name", "quarantined"), ("tag", "converged")]


def test_explicit_null_can_clear_a_mapped_field():
    args = inputs()
    args["peers"][0] = replace(args["peers"][0], values={"name": None, "tag": "old"})
    args["previous"] = {p.connection: replace(p, observation_id="poll-1") for p in args["peers"]}
    decision = reconcile(**args)[0]
    assert decision.kind == "mirror"
    assert decision.value is None


def test_both_changes_conflict():
    args = inputs()
    args["peers"][1] = replace(args["peers"][1], values={"name": "another", "tag": "old"})
    args["previous"] = {p.connection: replace(p, observation_id="poll-1") for p in args["peers"]}
    assert reconcile(**args)[0].kind == "conflict"


def candidate():
    return {"manifest_version": 1, "status": "implemented", "artifact": "registry/example@sha256:" + "a" * 64,
            "signature_verified": True, "supported_until": "2029-09-12",
            "requires": {"inventory": "unum.inventory/1"}, "tested_with": {"inventory": ["1.0.0", "1.1.0"]}}


def test_supported_mixed_versions():
    assert check_install(candidate(), {"inventory": {"version": "1.1.0", "provides": ["unum.inventory/1"]}}, date(2026, 9, 12)) == []


@pytest.mark.parametrize("artifact", [
    None, 1, "registry/example:latest", "registry/example@sha256:",
    "registry/example@sha256:" + "a" * 63,
    "registry/example@sha256:" + "a" * 65,
    "registry/example@sha256:" + "g" * 64,
    "registry/example@sha256:" + "a" * 64 + ":latest",
    "@sha256:" + "a" * 64,
    "registry/example@sha256:" + "a" * 64 + "\n",
])
def test_artifact_requires_a_complete_immutable_digest(artifact):
    c = candidate() | {"artifact": artifact}
    errors = check_install(c, {"inventory": {"version": "1.0.0", "provides": ["unum.inventory/1"]}})
    assert errors == ["An immutable artifact digest is required for installation"]


def test_untested_or_incompatible_dependency_rejected():
    for peer in ({"version": "2.0.0", "provides": ["unum.inventory/1"]}, {"version": "1.0.0", "provides": ["unum.inventory/2"]}):
        assert check_install(candidate(), {"inventory": peer}, date(2026, 9, 12))


def test_unsigned_or_expired_cannot_install():
    c = candidate() | {"signature_verified": False, "supported_until": "2025-01-01"}
    errors = check_install(c, {}, date(2026, 9, 12))
    assert any("signature" in e for e in errors)
    assert any("support window" in e for e in errors)
