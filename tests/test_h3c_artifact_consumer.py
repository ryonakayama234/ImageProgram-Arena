import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.consume_h3c import (
    consume_golden_pair,
    validate_public_bundle,
)


SOURCE_COMMIT = "824cbefc14e3e1e4978f10fd687a0c80fb200f4d"


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _zero_cost() -> dict:
    return {
        "skill_calls": 0,
        "strokes": 0,
        "motor_commands": 0,
        "observations": 0,
        "rollout_count": 0,
        "tip_distance_m": 0.0,
        "sim_time_s": 0.0,
        "wall_time_s": 0.0,
    }


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _write_bundle(public_dir: Path, summary: dict) -> None:
    _write_json(public_dir / "summary.json", summary)
    _write_json(public_dir / "replay_report.json", {"verified": True})
    files = {
        "replay_report.json": _hash(public_dir / "replay_report.json"),
        "summary.json": _hash(public_dir / "summary.json"),
    }
    _write_json(
        public_dir / "manifest.json",
        {"format": "imageprogram-h3c-public-1", "public_files": files},
    )


def _safe_summary() -> dict:
    return {
        "case": "safe",
        "target_fixture": "jaw",
        "variant": "original",
        "status": "completed",
        "initial_state_hash": "sha256:initial",
        "final_state_hash": "sha256:final",
        "preflight_status": "safe",
        "accepted_actions": 49,
        "endpoint_error_m": 0.0,
        "protection_added_ink": 0.0,
        "replay_verified": True,
        "replay_kind": "deterministic_execution",
        "preparation_cost": {**_zero_cost(), "motor_commands": 104},
        "continuation_cost": {**_zero_cost(), "motor_commands": 49},
        "policy_private_data_access": 0,
    }


def _rejected_summary() -> dict:
    return {
        "case": "rejected",
        "target_fixture": "jaw",
        "variant": "original",
        "status": "rejected",
        "initial_state_hash": "sha256:initial",
        "final_state_hash": "sha256:initial",
        "preflight_status": "rejected",
        "accepted_actions": 0,
        "endpoint_error_m": None,
        "protection_added_ink": 0.0,
        "replay_verified": True,
        "replay_kind": "identity_no_execution",
        "preparation_cost": {**_zero_cost(), "motor_commands": 104},
        "continuation_cost": _zero_cost(),
        "policy_private_data_access": 0,
    }


def _write_benchmark_manifest(path: Path) -> None:
    _write_json(
        path,
        {
            "format": "imageprogram-arena-h3c-golden-pair-manifest-1",
            "benchmark": "complete_structure_v0",
            "lineage_id": "character-bust-v0/jaw/original",
            "split": "foundation_control",
            "source": {
                "repository": "ryonakayama234/ImageProgram",
                "commit": SOURCE_COMMIT,
                "artifact_format": "imageprogram-h3c-public-1",
            },
            "cells": {
                "safe": "jaw--original--safe",
                "rejected": "jaw--original--rejected",
            },
            "expected": {
                "safe": {"status": "completed", "accepted_actions": 49},
                "rejected": {"status": "rejected", "accepted_actions": 0},
            },
        },
    )


class H3cArtifactConsumerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.matrix = self.root / "matrix"
        self.manifest = self.root / "benchmark.json"
        _write_bundle(
            self.matrix / "jaw--original--safe" / "public",
            _safe_summary(),
        )
        _write_bundle(
            self.matrix / "jaw--original--rejected" / "public",
            _rejected_summary(),
        )
        _write_benchmark_manifest(self.manifest)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_consumes_pair_and_preserves_raw_summaries(self) -> None:
        result = consume_golden_pair(
            matrix_root=self.matrix,
            benchmark_manifest_path=self.manifest,
            source_commit=SOURCE_COMMIT,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["cells"]["safe"]["summary"], _safe_summary())
        self.assertEqual(result["cells"]["rejected"]["summary"], _rejected_summary())
        self.assertEqual(result["source"]["commit"], SOURCE_COMMIT)

    def test_wrong_source_commit_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "source commit mismatch"):
            consume_golden_pair(
                matrix_root=self.matrix,
                benchmark_manifest_path=self.manifest,
                source_commit="deadbeef",
            )

    def test_public_hash_tampering_is_rejected(self) -> None:
        path = self.matrix / "jaw--original--safe" / "public" / "summary.json"
        path.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_public_bundle(path.parent)

    def test_private_path_in_public_manifest_is_rejected(self) -> None:
        public_dir = self.matrix / "jaw--original--safe" / "public"
        secret = public_dir / "private" / "secret.json"
        _write_json(secret, {"value": 1})
        manifest = json.loads((public_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["public_files"]["private/secret.json"] = _hash(secret)
        _write_json(public_dir / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "non-public artifact path"):
            validate_public_bundle(public_dir)

    def test_rejected_nonzero_continuation_fails_pair_gate(self) -> None:
        public_dir = self.matrix / "jaw--original--rejected" / "public"
        summary = _rejected_summary()
        summary["continuation_cost"]["motor_commands"] = 1
        _write_bundle(public_dir, summary)

        result = consume_golden_pair(
            matrix_root=self.matrix,
            benchmark_manifest_path=self.manifest,
            source_commit=SOURCE_COMMIT,
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["rejected_continuation_zero"])

    def test_pair_must_share_initial_state(self) -> None:
        public_dir = self.matrix / "jaw--original--rejected" / "public"
        summary = _rejected_summary()
        summary["initial_state_hash"] = "sha256:different"
        summary["final_state_hash"] = "sha256:different"
        _write_bundle(public_dir, summary)

        result = consume_golden_pair(
            matrix_root=self.matrix,
            benchmark_manifest_path=self.manifest,
            source_commit=SOURCE_COMMIT,
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["same_initial_state"])


if __name__ == "__main__":
    unittest.main()
