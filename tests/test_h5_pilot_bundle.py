import copy
import hashlib
import json
import unittest

from adapters.imageprogram_reference.h5_pilot_bundle import (
    EXPECTED_CANDIDATES_PER_LINEAGE,
    EXPECTED_LINEAGES,
    PilotBundleError,
    run_pilot_bundle,
    verify_pilot_bundle,
)

RECORD_HASH = "sha256:" + "a" * 64
OUTCOME_HASH = "sha256:" + "b" * 64


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _cost(wall_time: float) -> dict:
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


def _source() -> dict:
    return {
        "repository": "ryonakayama234/ImageProgram",
        "commit": "134d7cb8486373f3a70a1c506e3def0cb40d25c9",
        "candidate_corpus_issue": 46,
    }


def _lineage(index: int) -> dict:
    task_lineage = f"character/v0/pilot-{index:02d}"
    management_hash = _digest(f"management-{index}")
    spec = {
        "task_lineage": task_lineage,
        "public_task_hash": _digest(f"task-{index}"),
        "initial_public_state_hash": _digest(f"public-state-{index}"),
        "management_initial_state_hash": management_hash,
        "candidate_set_hash": _digest(f"candidate-set-{index}"),
        "body_spec_hash": _digest("body-a"),
        "motor_profile_hash": _digest("profile-a"),
        "adapter_version": "arena-reference-v0",
        "runtime_version": "imageprogram-runtime-v0",
        "evaluator_version": "construction-evaluator-v0",
        "contract_ref": {
            "repository": "ryonakayama234/ImageProgram",
            "commit": _source()["commit"],
            "schema_version": "0.1.0",
            "record_contract_version": "construction-outcome-record-v0",
            "record_contract_hash": RECORD_HASH,
            "outcome_contract_version": "construction-outcome-v0",
            "outcome_contract_hash": OUTCOME_HASH,
        },
        "policy_input": {
            "observation": {"artifact_id": f"public-{index}"},
            "goal": {"goal_id": "complete-structure"},
        },
    }
    candidates = []
    for candidate_id in ("A", "B", "C", "D"):
        candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_public_payload_hash": _digest(
                    f"{task_lineage}/{candidate_id}"
                ),
                "public_payload": {
                    "kind": "trace_polyline",
                    "variant": candidate_id,
                    "points_m": [[0.01, 0.01], [0.02 + 0.001 * index, 0.02]],
                },
            }
        )
    return {
        "source_lineage": f"character/v0/source-{index:02d}",
        "parent_lineage": f"character/v0/template-{index:02d}",
        "spec": spec,
        "checkpoint": {"hash": management_hash, "ink": 0, "lineage": index},
        "candidates": candidates,
    }


def _outcome_record(lineage, candidate, *, wall_time: float) -> dict:
    spec = lineage["spec"]
    return {
        "schema_version": spec["contract_ref"]["schema_version"],
        "kind": "construction_outcome_record",
        "record_contract_version": spec["contract_ref"]["record_contract_version"],
        "record_contract_hash": spec["contract_ref"]["record_contract_hash"],
        "outcome_contract_version": spec["contract_ref"]["outcome_contract_version"],
        "outcome_contract_hash": spec["contract_ref"]["outcome_contract_hash"],
        "record_id": f"{spec['task_lineage']}-{candidate['candidate_id']}",
        "task_lineage": spec["task_lineage"],
        "parent_lineage": lineage["parent_lineage"],
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
            "artifact_id": f"{spec['task_lineage']}/prediction",
            "sha256": spec["initial_public_state_hash"],
            "public_only": True,
        },
        "record_status": "observed",
        "outcome": {
            "execution_status": "completed",
            "stop_reason_code": "program_exhausted",
            "realization_error_m": 0.001,
            "endpoint_error_m": 0.0005,
            "darkened_existing_pixels": ord(candidate["candidate_id"]) - 64,
            "new_occupied_pixels": 4,
            "protection_delta": 0.0,
            "motor_commands": 2,
            "strokes": 1,
            "tip_distance_m": 0.01,
            "sim_time_s": 0.2,
            "completion_vector": {"goal": "satisfied"},
        },
        "replay_status": "verified",
        "branch_research_cost": _cost(wall_time),
        "missing_reason_code": None,
    }


class FakePilotAdapter:
    def __init__(self):
        self.restore_calls = 0
        self.execute_calls = 0

    def restore(self, lineage, checkpoint):
        self.restore_calls += 1
        return copy.deepcopy(checkpoint)

    def state_hash(self, lineage, state):
        if state["ink"] == 0:
            return state["hash"]
        return _digest(f"{lineage['spec']['task_lineage']}/ink/{state['ink']}")

    def execute(self, lineage, state, candidate, policy_input):
        self.execute_calls += 1
        initial = self.state_hash(lineage, state)
        state["ink"] += ord(candidate["candidate_id"]) - 64
        wall_time = self.execute_calls / 10000
        return {
            "initial_state_hash": initial,
            "final_state_hash": self.state_hash(lineage, state),
            "outcome_record": _outcome_record(
                lineage, candidate, wall_time=wall_time
            ),
            "policy_execution_cost": _cost(wall_time + 1.0),
        }


def _run(lineages):
    adapter = FakePilotAdapter()
    bundle = run_pilot_bundle(
        source=_source(),
        lineages=lineages,
        restore_checkpoint=adapter.restore,
        restored_state_hash=adapter.state_hash,
        execute_candidate=adapter.execute,
    )
    return adapter, bundle


class H5PilotBundleTests(unittest.TestCase):
    def test_exact_12x4_bundle_runs_48_branches_and_independent_consumer_passes(self):
        lineages = [_lineage(index) for index in range(EXPECTED_LINEAGES)]
        adapter, bundle = _run(lineages)
        audit = verify_pilot_bundle(bundle)

        self.assertEqual(adapter.restore_calls, 48)
        self.assertEqual(adapter.execute_calls, 48)
        self.assertEqual(audit["independent_lineages"], 12)
        self.assertEqual(audit["candidate_executions"], 48)
        self.assertEqual(audit["missing_branches"], 0)
        self.assertEqual(audit["replay_failures"], 0)
        self.assertTrue(audit["passed"])
        self.assertEqual(
            len(bundle["lineages"][0]["report"]["branches"]),
            EXPECTED_CANDIDATES_PER_LINEAGE,
        )

    def test_lineage_and_candidate_input_order_do_not_change_semantic_bundle_hash(self):
        original = [_lineage(index) for index in range(EXPECTED_LINEAGES)]
        reordered = copy.deepcopy(list(reversed(original)))
        for lineage in reordered:
            lineage["candidates"] = list(reversed(lineage["candidates"]))

        _, first = _run(original)
        _, second = _run(reordered)
        self.assertEqual(first["lineage_manifest_hash"], second["lineage_manifest_hash"])
        self.assertEqual(first["semantic_bundle_hash"], second["semantic_bundle_hash"])

    def test_duplicate_lineage_is_rejected_before_execution(self):
        lineages = [_lineage(index) for index in range(EXPECTED_LINEAGES)]
        lineages[-1]["spec"]["task_lineage"] = lineages[0]["spec"]["task_lineage"]
        adapter = FakePilotAdapter()
        with self.assertRaisesRegex(PilotBundleError, "duplicate task_lineage"):
            run_pilot_bundle(
                source=_source(),
                lineages=lineages,
                restore_checkpoint=adapter.restore,
                restored_state_hash=adapter.state_hash,
                execute_candidate=adapter.execute,
            )
        self.assertEqual(adapter.execute_calls, 0)

    def test_wrong_candidate_count_is_rejected_before_execution(self):
        lineages = [_lineage(index) for index in range(EXPECTED_LINEAGES)]
        lineages[3]["candidates"].pop()
        adapter = FakePilotAdapter()
        with self.assertRaisesRegex(PilotBundleError, "requires 4 candidates"):
            run_pilot_bundle(
                source=_source(),
                lineages=lineages,
                restore_checkpoint=adapter.restore,
                restored_state_hash=adapter.state_hash,
                execute_candidate=adapter.execute,
            )
        self.assertEqual(adapter.execute_calls, 0)

    def test_consumer_rejects_tampered_raw_branch_via_semantic_hash(self):
        lineages = [_lineage(index) for index in range(EXPECTED_LINEAGES)]
        _, bundle = _run(lineages)
        edited = copy.deepcopy(bundle)
        edited["lineages"][0]["report"]["branches"][0]["outcome_record"]["outcome"][
            "new_occupied_pixels"
        ] += 100

        audit = verify_pilot_bundle(edited)
        self.assertFalse(audit["checks"]["semantic_bundle_hash_matches"])
        self.assertFalse(audit["passed"])

    def test_measured_wall_time_does_not_define_semantic_bundle_identity(self):
        lineages = [_lineage(index) for index in range(EXPECTED_LINEAGES)]
        _, bundle = _run(lineages)
        edited = copy.deepcopy(bundle)
        edited["lineages"][0]["report"]["branches"][0]["outcome_record"][
            "branch_research_cost"
        ]["wall_time_s"] += 10.0

        audit = verify_pilot_bundle(edited)
        self.assertTrue(audit["checks"]["semantic_bundle_hash_matches"])
        self.assertTrue(audit["passed"])
        self.assertGreater(
            audit["total_branch_research_cost"]["wall_time_s"],
            verify_pilot_bundle(bundle)["total_branch_research_cost"]["wall_time_s"],
        )

    def test_bundle_is_json_serializable_and_contains_no_checkpoint(self):
        lineages = [_lineage(index) for index in range(EXPECTED_LINEAGES)]
        _, bundle = _run(lineages)
        payload = json.dumps(bundle, sort_keys=True)
        self.assertNotIn('"checkpoint"', payload)
        self.assertIn('"semantic_bundle_hash"', payload)


if __name__ == "__main__":
    unittest.main()
