import copy
import json
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.h5_branch_isolation import (
    BranchIsolationError,
    audit_order_invariance,
    candidate_manifest_hash,
    deterministic_audit_projection,
    run_exhaustive_branches,
    write_deterministic_audit,
)

RECORD_HASH = "sha256:" + "a" * 64
OUTCOME_HASH = "sha256:" + "b" * 64


def _spec():
    return {
        "task_lineage": "character/v0/lineage-001",
        "public_task_hash": "sha256:" + "1" * 64,
        "initial_public_state_hash": "sha256:" + "2" * 64,
        "management_initial_state_hash": "sha256:" + "3" * 64,
        "candidate_set_hash": "sha256:" + "4" * 64,
        "body_spec_hash": "sha256:" + "5" * 64,
        "motor_profile_hash": "sha256:" + "6" * 64,
        "adapter_version": "arena-reference-v0",
        "runtime_version": "imageprogram-runtime-v0",
        "evaluator_version": "construction-evaluator-v0",
        "contract_ref": {
            "repository": "ryonakayama234/ImageProgram",
            "commit": "134d7cb8486373f3a70a1c506e3def0cb40d25c9",
            "schema_version": "0.1.0",
            "record_contract_version": "construction-outcome-record-v0",
            "record_contract_hash": RECORD_HASH,
            "outcome_contract_version": "construction-outcome-v0",
            "outcome_contract_hash": OUTCOME_HASH,
        },
        "policy_input": {
            "observation": {"artifact_id": "public-initial"},
            "goal": {"goal_id": "complete-structure"},
        },
    }


def _candidates():
    return [
        {
            "candidate_id": candidate_id,
            "candidate_public_payload_hash": "sha256:" + digit * 64,
            "public_payload": {"kind": "trace_polyline", "variant": candidate_id},
        }
        for candidate_id, digit in zip(("A", "B", "C", "D"), "789a", strict=True)
    ]


def _cost(wall_time):
    return {
        "skill_calls": 1,
        "strokes": 1,
        "motor_commands": 2,
        "observations": 1,
        "rollout_count": 0,
        "tip_distance_m": 0.01,
        "sim_time_s": 0.2,
        "wall_time_s": wall_time,
    }


def _outcome_record(spec, candidate, *, status="completed", wall_time=0.01):
    outcome = {
        "execution_status": status,
        "stop_reason_code": f"{status}-for-{candidate['candidate_id']}",
        "realization_error_m": 0.01,
        "endpoint_error_m": 0.001,
        "darkened_existing_pixels": 1,
        "new_occupied_pixels": 3,
        "protection_delta": 0.0,
        "motor_commands": 2,
        "strokes": 1,
        "tip_distance_m": 0.01,
        "sim_time_s": 0.2,
        "completion_vector": {"goal": "satisfied"},
    }
    return {
        "schema_version": spec["contract_ref"]["schema_version"],
        "kind": "construction_outcome_record",
        "record_contract_version": spec["contract_ref"]["record_contract_version"],
        "record_contract_hash": spec["contract_ref"]["record_contract_hash"],
        "outcome_contract_version": spec["contract_ref"]["outcome_contract_version"],
        "outcome_contract_hash": spec["contract_ref"]["outcome_contract_hash"],
        "record_id": f"record-{candidate['candidate_id']}",
        "task_lineage": spec["task_lineage"],
        "parent_lineage": "character/v0",
        "public_task_hash": spec["public_task_hash"],
        "initial_public_state_hash": spec["initial_public_state_hash"],
        "candidate_set_hash": spec["candidate_set_hash"],
        "candidate_id": candidate["candidate_id"],
        "candidate_public_payload_hash": candidate["candidate_public_payload_hash"],
        "body_spec_hash": spec["body_spec_hash"],
        "motor_profile_hash": spec["motor_profile_hash"],
        "adapter_version": spec["adapter_version"],
        "runtime_version": spec["runtime_version"],
        "evaluator_version": spec["evaluator_version"],
        "prediction_input": {
            "artifact_id": "public-input",
            "sha256": spec["initial_public_state_hash"],
            "public_only": True,
        },
        "record_status": "observed",
        "outcome": outcome,
        "replay_status": "verified",
        "branch_research_cost": _cost(wall_time),
        "missing_reason_code": None,
    }


class FakeAdapter:
    def __init__(self, *, fail_a=False, sticky_restore=False, varying_wall_time=False):
        self.checkpoint = {"hash": _spec()["management_initial_state_hash"], "ink": 0}
        self.fail_a = fail_a
        self.sticky_restore = sticky_restore
        self.varying_wall_time = varying_wall_time
        self.restore_calls = 0
        self.execute_calls = 0

    def restore(self, checkpoint):
        self.restore_calls += 1
        if self.sticky_restore:
            return checkpoint
        return copy.deepcopy(checkpoint)

    def state_hash(self, state):
        if state["ink"] == 0:
            return state["hash"]
        return "sha256:" + str(state["ink"])[-1] * 64

    def execute(self, state, candidate, policy_input):
        self.execute_calls += 1
        initial = self.state_hash(state)
        if "hidden_witness" in policy_input:
            raise AssertionError("private policy input reached adapter")
        amount = ord(candidate["candidate_id"]) - 64
        state["ink"] += amount
        status = "failed" if self.fail_a and candidate["candidate_id"] == "A" else "completed"
        wall = self.execute_calls / 1000 if self.varying_wall_time else 0.01
        record = _outcome_record(_spec(), candidate, status=status, wall_time=wall)
        if self.varying_wall_time:
            record["record_id"] = f"record-{candidate['candidate_id']}-{self.execute_calls}"
        return {
            "initial_state_hash": initial,
            "final_state_hash": self.state_hash(state),
            "outcome_record": record,
            "policy_execution_cost": _cost(wall + 1.0),
        }


class H5BranchIsolationTests(unittest.TestCase):
    def test_private_candidate_fields_are_rejected_before_restore_or_execution(self):
        for extra in (
            {"hidden_witness": {"answer": "A"}},
            {"metadata": [{"oracle_outcome": "completed"}]},
            {"metadata": {"path": "private/checkpoint.npz"}},
        ):
            with self.subTest(extra=extra):
                candidates = _candidates()
                candidates[-1].update(extra)
                adapter = FakeAdapter()
                with self.assertRaises(BranchIsolationError):
                    run_exhaustive_branches(
                        spec=_spec(), checkpoint=adapter.checkpoint,
                        candidates=candidates, restore_checkpoint=adapter.restore,
                        restored_state_hash=adapter.state_hash,
                        execute_candidate=adapter.execute,
                    )
                self.assertEqual(adapter.restore_calls, 0)
                self.assertEqual(adapter.execute_calls, 0)

    def test_manifest_binds_payload_even_when_declared_hash_is_stale(self):
        original = _candidates()
        edited = copy.deepcopy(original)
        edited[0]["public_payload"]["variant"] = "changed"
        self.assertEqual(
            original[0]["candidate_public_payload_hash"],
            edited[0]["candidate_public_payload_hash"],
        )
        self.assertNotEqual(candidate_manifest_hash(original), candidate_manifest_hash(edited))

    def test_manifest_binds_extra_callback_visible_fields(self):
        original = _candidates()
        edited = copy.deepcopy(original)
        edited[0]["public_metadata"] = {"pressure": 0.5}
        self.assertNotEqual(candidate_manifest_hash(original), candidate_manifest_hash(edited))

    def test_manifest_is_canonical_across_candidate_and_mapping_order(self):
        original = _candidates()
        reordered = [dict(reversed(list(c.items()))) for c in reversed(original)]
        for candidate in reordered:
            candidate["public_payload"] = dict(reversed(list(candidate["public_payload"].items())))
        self.assertEqual(candidate_manifest_hash(original), candidate_manifest_hash(reordered))

    def test_audit_uses_frozen_candidates_when_callback_mutates_caller_input(self):
        candidates = _candidates()
        frozen = copy.deepcopy(candidates)
        expected_manifest = candidate_manifest_hash(frozen)
        adapter = FakeAdapter()

        def mutate_caller(state, candidate, policy_input):
            self.assertEqual(candidate, frozen[ord(candidate["candidate_id"]) - 65])
            candidates[-1]["hidden_witness"] = "must not enter frozen candidates"
            candidates[0]["public_payload"]["variant"] = "changed-by-callback"
            return adapter.execute(state, candidate, policy_input)

        audit = audit_order_invariance(
            spec=_spec(), checkpoint=adapter.checkpoint, candidates=candidates,
            restore_checkpoint=adapter.restore, restored_state_hash=adapter.state_hash,
            execute_candidate=mutate_caller,
        )
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["forward"]["candidate_manifest_hash"], expected_manifest)
        self.assertEqual(audit["reverse"]["candidate_manifest_hash"], expected_manifest)
        self.assertEqual(adapter.execute_calls, 8)

    def test_reports_bind_payload_edits_despite_unchanged_outcome_identifiers(self):
        def run(candidates):
            adapter = FakeAdapter()
            return run_exhaustive_branches(
                spec=_spec(), checkpoint=adapter.checkpoint, candidates=candidates,
                restore_checkpoint=adapter.restore, restored_state_hash=adapter.state_hash,
                execute_candidate=adapter.execute,
            )

        original = _candidates()
        edited = copy.deepcopy(original)
        edited[0]["public_payload"]["variant"] = "changed"
        first, second = run(original), run(edited)
        self.assertTrue(first["passed"] and second["passed"])
        self.assertEqual(first["branches"], second["branches"])
        self.assertNotEqual(first["candidate_manifest_hash"], second["candidate_manifest_hash"])

    def test_forward_reverse_audit_reverses_all_pairs_and_repeats_every_candidate(self):
        adapter = FakeAdapter()
        report = audit_order_invariance(
            spec=_spec(),
            checkpoint=adapter.checkpoint,
            candidates=_candidates(),
            restore_checkpoint=adapter.restore,
            restored_state_hash=adapter.state_hash,
            execute_candidate=adapter.execute,
        )
        self.assertTrue(report["passed"])
        self.assertEqual(report["verification_executions"], 8)
        self.assertTrue(report["checks"]["all_pairwise_relative_orders_reversed"])
        self.assertTrue(report["checks"]["candidate_repeat_deterministic"])
        self.assertEqual(adapter.restore_calls, 8)
        self.assertEqual(adapter.execute_calls, 8)

    def test_failed_branch_does_not_contaminate_next_candidate(self):
        adapter = FakeAdapter(fail_a=True)
        report = run_exhaustive_branches(
            spec=_spec(),
            checkpoint=adapter.checkpoint,
            candidates=_candidates(),
            restore_checkpoint=adapter.restore,
            restored_state_hash=adapter.state_hash,
            execute_candidate=adapter.execute,
        )
        self.assertTrue(report["passed"])
        self.assertEqual(
            {branch["initial_state_hash"] for branch in report["branches"]},
            {_spec()["management_initial_state_hash"]},
        )
        a = next(branch for branch in report["branches"] if branch["candidate_id"] == "A")
        self.assertEqual(a["outcome_record"]["outcome"]["execution_status"], "failed")

    def test_sticky_restore_is_detected_as_world_contamination(self):
        adapter = FakeAdapter(sticky_restore=True)
        with self.assertRaisesRegex(BranchIsolationError, "differs from frozen checkpoint"):
            run_exhaustive_branches(
                spec=_spec(),
                checkpoint=adapter.checkpoint,
                candidates=_candidates(),
                restore_checkpoint=adapter.restore,
                restored_state_hash=adapter.state_hash,
                execute_candidate=adapter.execute,
            )

    def test_private_oracle_key_is_rejected_before_execution(self):
        spec = _spec()
        spec["policy_input"]["hidden_witness"] = {"path": "secret"}
        adapter = FakeAdapter()
        with self.assertRaisesRegex(BranchIsolationError, "private/oracle key"):
            run_exhaustive_branches(
                spec=spec,
                checkpoint=adapter.checkpoint,
                candidates=_candidates(),
                restore_checkpoint=adapter.restore,
                restored_state_hash=adapter.state_hash,
                execute_candidate=adapter.execute,
            )
        self.assertEqual(adapter.execute_calls, 0)

    def test_contract_hash_mismatch_is_rejected(self):
        adapter = FakeAdapter()

        def wrong_record(state, candidate, policy_input):
            result = adapter.execute(state, candidate, policy_input)
            result["outcome_record"]["record_contract_hash"] = "sha256:" + "f" * 64
            return result

        with self.assertRaisesRegex(BranchIsolationError, "record_contract_hash mismatch"):
            run_exhaustive_branches(
                spec=_spec(),
                checkpoint=adapter.checkpoint,
                candidates=_candidates(),
                restore_checkpoint=adapter.restore,
                restored_state_hash=adapter.state_hash,
                execute_candidate=wrong_record,
            )

    def test_semantic_digest_ignores_measured_wall_time_but_preserves_raw_cost(self):
        adapter = FakeAdapter(varying_wall_time=True)
        report = audit_order_invariance(
            spec=_spec(),
            checkpoint=adapter.checkpoint,
            candidates=_candidates(),
            restore_checkpoint=adapter.restore,
            restored_state_hash=adapter.state_hash,
            execute_candidate=adapter.execute,
        )
        self.assertTrue(report["passed"])
        forward_a = next(
            x for x in report["forward"]["branches"] if x["candidate_id"] == "A"
        )
        reverse_a = next(
            x for x in report["reverse"]["branches"] if x["candidate_id"] == "A"
        )
        self.assertNotEqual(
            forward_a["outcome_record"]["branch_research_cost"]["wall_time_s"],
            reverse_a["outcome_record"]["branch_research_cost"]["wall_time_s"],
        )
        self.assertEqual(forward_a["semantic_digest"], reverse_a["semantic_digest"])

    def test_deterministic_audit_writer_removes_run_local_fields(self):
        adapter = FakeAdapter(varying_wall_time=True)
        audit = audit_order_invariance(
            spec=_spec(),
            checkpoint=adapter.checkpoint,
            candidates=_candidates(),
            restore_checkpoint=adapter.restore,
            restored_state_hash=adapter.state_hash,
            execute_candidate=adapter.execute,
        )
        projected = deterministic_audit_projection(audit)
        serialized = json.dumps(projected, sort_keys=True)
        self.assertNotIn("wall_time_s", serialized)
        self.assertNotIn("record_id", serialized)
        self.assertIn("sim_time_s", serialized)

        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first.json"
            write_deterministic_audit(audit, first)
            parsed = json.loads(first.read_text(encoding="utf-8"))
            self.assertTrue(parsed["passed"])
            written = first.read_text(encoding="utf-8")
            self.assertNotIn("wall_time_s", written)
            self.assertNotIn("record_id", written)


if __name__ == "__main__":
    unittest.main()
