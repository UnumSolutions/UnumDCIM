import unittest
from dataclasses import replace

from unum_sync.reconcile import Scope, Snapshot, plan


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("tenant-a", "nlyte-a", "asset-1")

    def run_plan(self, left="old", right="old", owner="nlyte", stable=True,
                 writable=None, field="name", base="old"):
        peers = {s: Snapshot(self.scope, s, "etag-1", "poll-2", {field: v})
                 for s, v in (("nlyte", left), ("unum", right))}
        self.arguments = dict(
            scope=self.scope, baseline={field: base}, owners={field: owner},
            nlyte=peers["nlyte"], unum=peers["unum"],
            previous={s: replace(v, observation_id="poll-1") for s, v in peers.items()}
            if stable else None,
            writable=writable if writable is not None else
            {s: frozenset({field}) for s in peers})
        return plan(**self.arguments)[0]

    def test_owner_change_mirrors_both_directions(self):
        for owner, left, right, target in (("nlyte", "new", "old", "unum"),
                                           ("unum", "old", "new", "nlyte")):
            result = self.run_plan(left, right, owner)
            self.assertEqual((result.kind, result.target, result.value), ("mirror", target, "new"))
            self.assertEqual(result.expected_revision, "etag-1")
            self.assertIsNotNone(result.expected_hash)

    def test_non_owner_edit_is_intent(self):
        self.assertEqual(self.run_plan(right="new").kind, "intent")
        self.assertEqual(self.run_plan(left="new", owner="unum").kind, "intent")

    def test_concurrent_edits_are_conflicts(self):
        self.assertEqual(self.run_plan("left", "right").kind, "conflict")

    def test_echo_is_converged(self):
        result = self.run_plan("new", "new")
        self.assertEqual(result.kind, "converged")
        self.assertIsNone(result.operation_key)

    def test_first_observation_waits(self):
        self.assertEqual(self.run_plan(left="new", stable=False).kind, "pending")

    def test_replaying_same_poll_does_not_confirm_drift(self):
        self.run_plan(left="new")
        self.arguments["previous"] = {s: self.arguments[s] for s in ("nlyte", "unum")}
        self.assertEqual(plan(**self.arguments)[0].kind, "pending")

    def test_current_and_previous_polls_require_valid_provenance(self):
        for poll in ("current", "previous"):
            for field in ("observation_id", "revision"):
                for invalid in ("", " ", None, 1):
                    with self.subTest(poll=poll, field=field, invalid=invalid):
                        self.run_plan(left="new")
                        snapshots = self.arguments if poll == "current" else self.arguments["previous"]
                        snapshots["nlyte"] = replace(snapshots["nlyte"], **{field: invalid})
                        with self.assertRaises(ValueError):
                            plan(**self.arguments)

    def test_changing_drift_waits(self):
        self.run_plan(left="new")
        self.arguments["previous"]["nlyte"] = replace(
            self.arguments["previous"]["nlyte"], values={"name": "transient"})
        self.assertEqual(plan(**self.arguments)[0].kind, "pending")

    def test_no_unverified_write(self):
        self.assertEqual(self.run_plan(left="new", writable={}).kind, "blocked")
        self.assertEqual(self.run_plan(right="new", writable={}).kind, "blocked")

    def test_scope_mismatch_fails_closed(self):
        self.run_plan(left="new")
        for scope in (Scope("tenant-b", "nlyte-a", "asset-1"),
                      Scope("tenant-a", "nlyte-b", "asset-1"),
                      Scope("tenant-a", "nlyte-a", "asset-2")):
            self.arguments["nlyte"] = replace(self.arguments["nlyte"], scope=scope)
            with self.assertRaises(ValueError):
                plan(**self.arguments)

    def test_schema_drift_and_partial_snapshot_fail_closed(self):
        self.run_plan(left="new")
        for snapshot in (replace(self.arguments["nlyte"], complete=False),
                         replace(self.arguments["nlyte"], values={}),
                         replace(self.arguments["nlyte"], values={"name": "new", "extra": 1})):
            with self.assertRaises(ValueError):
                plan(**dict(self.arguments, nlyte=snapshot))

    def test_missing_or_invalid_owner_fails(self):
        self.run_plan()
        for owners in ({}, {"name": "unknown"}):
            with self.assertRaises(ValueError):
                plan(**dict(self.arguments, owners=owners))

    def test_placement_is_atomic(self):
        old = {"rack_id": "rack-1", "u": 1, "face": "front"}
        new = {"rack_id": "rack-2", "u": 2, "face": "rear"}
        result = self.run_plan(new, old, field="placement", base=old)
        self.assertEqual(result.value, new)
        with self.assertRaises(ValueError):
            self.run_plan(field="rack_id")

    def test_null_is_explicit_clear_not_missing(self):
        self.assertEqual(self.run_plan(left=None).value, None)
        self.assertEqual(self.run_plan(left=None).kind, "mirror")

    def test_keys_are_repeatable_and_scoped(self):
        first = self.run_plan(left="new").operation_key
        self.assertEqual(first, self.run_plan(left="new").operation_key)
        self.scope = Scope("tenant-b", "nlyte-a", "asset-1")
        self.assertNotEqual(first, self.run_plan(left="new").operation_key)

    def test_json_types_not_python_equality(self):
        self.assertEqual(self.run_plan(True, 1, base=0).kind, "conflict")

    def test_nonfinite_values_fail(self):
        with self.assertRaises(ValueError):
            self.run_plan(left=float("nan"))


if __name__ == "__main__":
    unittest.main()
