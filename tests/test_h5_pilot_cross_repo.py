import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.h5_pilot_bundle import (
    EXPECTED_LINEAGES,
    PilotBundleError,
)
from adapters.imageprogram_reference.run_h5_pilot import (
    _canonical_hash,
    _file_hash,
    prepare_h5_pilot_inputs,
)

SOURCE_COMMIT = "1" * 40


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _descriptor() -> dict:
    return {
        "contract_ref": {
            "repository": "ryonakayama234/ImageProgram",
            "commit": SOURCE_COMMIT,
            "schema_version": "0.1.0",
            "record_contract_version": "construction-outcome-record-v0",
            "record_contract_hash": _digest("record"),
            "outcome_contract_version": "construction-outcome-v0",
            "outcome_contract_hash": _digest("outcome"),
        },
        "runtime_version": "h5-candidate-branch-runtime-v0",
        "evaluator_version": "h5-construction-outcome-evaluator-v0",
    }


def _public_lineage(index: int) -> dict:
    task = f"h5pilot/task/{index:02d}"
    source = f"h5pilot/source/{index:02d}"
    public_state = {
        "observation": {
            "observation_id": f"obs-{index:02d}",
            "image_sha256": _digest(f"image-{index}"),
        },
        "scaffold": {"scaffold_id": f"scaffold-{index:02d}"},
        "goal": {"goal_id": f"goal-{index:02d}"},
        "body": {"body_id": "body-a"},
    }
    profile = {"tool": "pen", "pressure": 0.5, "speed_m_s": 0.05}
    candidates = [
        {
            "candidate_id": f"cand-{slot}",
            "candidate_public_payload_hash": _digest(f"{task}/cand/{slot}"),
            "public_payload": {
                "schema_version": "h5-fixed-candidate-public-payload-v0",
                "feature_input": {"slot": slot},
            },
            "h3b_status": "safe",
        }
        for slot in range(4)
    ]
    return {
        "schema_version": "h5-fixed-candidate-lineage-v0",
        "task_lineage": task,
        "source_lineage": source,
        "parent_lineage": None,
        "public_task_hash": _digest(f"task-{index}"),
        "initial_public_state_hash": _digest(f"state-{index}"),
        "body_spec_hash": _digest("body"),
        "motor_profile_hash": _digest("profile"),
        "public_state": public_state,
        "profile": profile,
        "candidate_set_hash": _digest(f"candidate-set-{index}"),
        "candidates": candidates,
    }


def _public_input_hash(lineage: dict) -> str:
    return _canonical_hash(
        {
            "schema_version": "h5-fixed-candidate-lineage-input-v0",
            "task_lineage": lineage["task_lineage"],
            "source_lineage": lineage["source_lineage"],
            "parent_lineage": lineage["parent_lineage"],
            "public_state": lineage["public_state"],
            "profile": lineage["profile"],
        }
    )


def _fixture(root: Path) -> tuple[Path, Path]:
    lineages = [_public_lineage(index) for index in range(EXPECTED_LINEAGES)]
    corpus_path = root / "fixed_candidate_corpus.json"
    _write_json(
        corpus_path,
        {
            "schema_version": "h5-fixed-candidate-corpus-v0",
            "source_repository": "ryonakayama234/ImageProgram",
            "source_commit": SOURCE_COMMIT,
            "feature_version": "construction-features-v0",
            "feature_contract_hashes": {
                "S0": _digest("S0"),
                "S1": _digest("S1"),
                "S2": _digest("S2"),
            },
            "expected_lineages": 12,
            "expected_candidates_per_lineage": 4,
            "lineages": lineages,
            "corpus_hash": _digest("corpus"),
        },
    )

    private_lineages = []
    for index, lineage in enumerate(lineages):
        checkpoint_rel = f"private/seed-{index:04d}/final.npz"
        checkpoint = root / checkpoint_rel
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_bytes(f"checkpoint-{index}".encode("utf-8"))
        private_lineages.append(
            {
                "schema_version": "h5-pilot-private-lineage-summary-v0",
                "task_lineage": lineage["task_lineage"],
                "source_lineage": lineage["source_lineage"],
                "generation_seed": index,
                "public_input_hash": _public_input_hash(lineage),
                "initial_image_sha256": _digest(f"image-{index}"),
                "management_initial_state_hash": _digest(f"management-{index}"),
                "checkpoint_sha256": _file_hash(checkpoint),
                "initial_ink_pixels": 10 + index,
                "target_geometry_hash": _digest(f"geometry-{index}"),
                "source_program_hash": _digest(f"source-program-{index}"),
                "omission_program_hash": _digest(f"omission-program-{index}"),
                "preparation_replay_verified": True,
                "witness_replay_verified": True,
                "nominal_preflight_status": "safe",
                "checkpoint_relative_path": checkpoint_rel,
            }
        )

    _write_json(
        root / "private" / "summary.json",
        {
            "schema_version": "h5-pilot-excitation-summary-v0",
            "benchmark": "complete_structure_pilot_v0",
            "generator_version": "h5-pilot-lineage-excitation-v0",
            "source_repository": "ryonakayama234/ImageProgram",
            "source_commit": SOURCE_COMMIT,
            "seeds": list(range(12)),
            "lineages": private_lineages,
            "unique_public_states": 12,
            "unique_initial_images": 12,
            "unique_target_geometries": 12,
            "unique_source_programs": 12,
            "minimum_target_rms_distance_norm": 0.02,
            "passed": True,
        },
    )
    return root, corpus_path


class H5PilotCrossRepoPreparationTests(unittest.TestCase):
    def test_joins_exact_12_lineages_and_binds_corpus_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root, corpus = _fixture(Path(temp))
            source, lineages = prepare_h5_pilot_inputs(
                lineage_root=root,
                candidate_corpus_path=corpus,
                source_commit=SOURCE_COMMIT,
                descriptor=_descriptor(),
            )

            self.assertEqual(len(lineages), 12)
            self.assertEqual(len({x["source_lineage"] for x in lineages}), 12)
            self.assertEqual(
                source["candidate_corpus_version"],
                "h5-fixed-candidate-corpus-v0",
            )
            self.assertEqual(source["candidate_corpus_hash"], _digest("corpus"))
            for lineage in lineages:
                self.assertTrue(Path(lineage["checkpoint"]).is_file())
                self.assertNotIn(
                    "checkpoint",
                    json.dumps(lineage["spec"]["policy_input"]),
                )

    def test_checkpoint_tamper_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root, corpus = _fixture(Path(temp))
            checkpoint = root / "private" / "seed-0000" / "final.npz"
            checkpoint.write_bytes(b"tampered")

            with self.assertRaisesRegex(PilotBundleError, "checkpoint SHA-256 mismatch"):
                prepare_h5_pilot_inputs(
                    lineage_root=root,
                    candidate_corpus_path=corpus,
                    source_commit=SOURCE_COMMIT,
                    descriptor=_descriptor(),
                )

    def test_source_commit_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root, corpus = _fixture(Path(temp))
            with self.assertRaisesRegex(
                PilotBundleError,
                "candidate corpus source commit mismatch",
            ):
                prepare_h5_pilot_inputs(
                    lineage_root=root,
                    candidate_corpus_path=corpus,
                    source_commit="2" * 40,
                    descriptor=_descriptor(),
                )

    def test_duplicate_source_lineage_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root, corpus = _fixture(Path(temp))
            payload = json.loads(corpus.read_text(encoding="utf-8"))
            payload["lineages"][-1]["source_lineage"] = (
                payload["lineages"][0]["source_lineage"]
            )
            _write_json(root / "bad-corpus.json", payload)

            with self.assertRaisesRegex(PilotBundleError, "duplicate #46 source lineage"):
                prepare_h5_pilot_inputs(
                    lineage_root=root,
                    candidate_corpus_path=root / "bad-corpus.json",
                    source_commit=SOURCE_COMMIT,
                    descriptor=_descriptor(),
                )


if __name__ == "__main__":
    unittest.main()
