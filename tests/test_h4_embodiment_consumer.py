import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.consume_h4 import (
    consume_h4_pair,
    validate_public_bundle,
)

SOURCE_COMMIT = "397869fe958325e7d60bf8f80ec37e7bbf764bdc"


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _body(max_speed: float) -> dict:
    return {
        "canvas_width_m": 0.256,
        "canvas_height_m": 0.256,
        "raster_width_px": 256,
        "raster_height_px": 256,
        "max_speed_m_s": max_speed,
        "control_dt_s": 0.01,
        "tools": ["pen", "opaque_brush"],
    }


def _input(body_id: str) -> dict:
    is_a = body_id == "body_a"
    return {
        "request_id": f"h4-public-jaw-{body_id}",
        "observation": {
            "image_sha256": "sha256:" + "a" * 64,
            "tip_position_m": {"x": 0.152, "y": 0.201},
            "tool": "pen",
            "sim_time_s": 10.0 if is_a else 25.0,
        },
        "scaffold": {
            "scaffold_id": "character-bust-v0",
            "nodes": [{"node_id": "opaque", "realization": "missing"}],
        },
        "goal": {
            "goal_id": "h3c-fixture-001-original-safe",
            "regions": [{"region_id": "h3c-guard"}],
            "conditions": [{"condition_id": "h3c-protect-guard"}],
        },
        "body": _body(0.1 if is_a else 0.025),
        "budget": {"max_motor_commands": 4096},
        "profile": {
            "tool": "pen",
            "pressure": 0.5,
            "speed_m_s": 0.05 if is_a else 0.025,
        },
    }


def _summary(body_id: str) -> dict:
    is_a = body_id == "body_a"
    return {
        "body_id": body_id,
        "status": "completed",
        "initial_state_hash": "sha256:" + ("1" if is_a else "2") * 64,
        "final_state_hash": "sha256:" + ("3" if is_a else "4") * 64,
        "initial_image_sha256": "sha256:" + "a" * 64,
        "initial_tip_x_m": 0.152,
        "initial_tip_y_m": 0.201,
        "initial_tool": "pen",
        "motor_program_sha256": "sha256:" + ("5" if is_a else "6") * 64,
        "accepted_actions": 49 if is_a else 90,
        "continuation_control_ticks": 427 if is_a else 852,
        "endpoint_error_m": 0.0,
        "protection_added_ink": 0.0,
        "replay_verified": True,
        "policy_private_data_access": 0,
        "continuation_cost": {
            "sim_time_s": 4.264503592 if is_a else 8.519007184,
        },
    }


def _write_bundle(public_dir: Path, body_id: str) -> None:
    _write_json(public_dir / "input.json", _input(body_id))
    _write_json(public_dir / "summary.json", _summary(body_id))
    _write_json(public_dir / "program.json", {"body_id": body_id})
    _write_json(public_dir / "replay_report.json", {"verified": True})
    files = {
        name: _hash(public_dir / name)
        for name in (
            "input.json",
            "program.json",
            "replay_report.json",
            "summary.json",
        )
    }
    _write_json(
        public_dir / "manifest.json",
        {"format": "imageprogram-h4-body-public-1", "public_files": files},
    )


def _write_benchmark_manifest(path: Path) -> None:
    _write_json(
        path,
        {
            "format": "imageprogram-arena-h4-pair-manifest-1",
            "benchmark": "complete_structure_v0",
            "lineage_id": "character-bust-v0/jaw/original/h4-embodiment",
            "split": "h4_phase1_control",
            "source": {
                "repository": "ryonakayama234/ImageProgram",
                "commit": SOURCE_COMMIT,
                "artifact_format": "imageprogram-h4-body-public-1",
            },
            "cells": {"body_a": "body-a", "body_b": "body-b"},
            "expected": {
                "body_a": {
                    "accepted_actions": 49,
                    "sim_time_s": 4.264503592,
                    "sim_time_tolerance_s": 1e-6,
                },
                "body_b": {
                    "accepted_actions": 90,
                    "sim_time_s": 8.519007184,
                    "sim_time_tolerance_s": 1e-6,
                },
            },
        },
    )


class H4EmbodimentConsumerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pair = self.root / "pair"
        self.manifest = self.root / "benchmark.json"
        _write_bundle(self.pair / "body-a" / "public", "body_a")
        _write_bundle(self.pair / "body-b" / "public", "body_b")
        _write_benchmark_manifest(self.manifest)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _consume(self) -> dict:
        return consume_h4_pair(
            pair_root=self.pair,
            benchmark_manifest_path=self.manifest,
            source_commit=SOURCE_COMMIT,
        )

    def test_consumes_pair_and_recomputes_h4_gate(self) -> None:
        result = self._consume()
        self.assertTrue(result["passed"])
        self.assertTrue(result["checks"]["same_public_semantics"])
        self.assertTrue(result["checks"]["same_public_initial_state"])
        self.assertTrue(result["checks"]["body_and_profile_excited"])
        self.assertTrue(result["checks"]["motorization_excited"])

    def test_sibling_private_directory_is_not_consumed(self) -> None:
        secret = self.pair / "body-b" / "private" / "secret.json"
        _write_json(secret, {"known_continuation": "must remain unreachable"})
        self.assertTrue(self._consume()["passed"])

    def test_wrong_source_commit_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "source commit mismatch"):
            consume_h4_pair(
                pair_root=self.pair,
                benchmark_manifest_path=self.manifest,
                source_commit="deadbeef",
            )

    def test_public_hash_tampering_is_rejected(self) -> None:
        public = self.pair / "body-a" / "public"
        (public / "summary.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_public_bundle(public)

    def test_changed_scaffold_fails_public_semantics_gate(self) -> None:
        public = self.pair / "body-b" / "public"
        changed = _input("body_b")
        changed["scaffold"]["scaffold_id"] = "body-specific-shortcut"
        _write_bundle(public, "body_b")
        _write_json(public / "input.json", changed)
        manifest = read_manifest = json.loads(
            (public / "manifest.json").read_text(encoding="utf-8")
        )
        read_manifest["public_files"]["input.json"] = _hash(public / "input.json")
        _write_json(public / "manifest.json", manifest)

        result = self._consume()
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["same_public_semantics"])

    def test_unexcited_body_profile_fails_gate(self) -> None:
        public = self.pair / "body-b" / "public"
        changed = _input("body_b")
        changed["body"] = _body(0.1)
        changed["profile"]["speed_m_s"] = 0.05
        _write_bundle(public, "body_b")
        _write_json(public / "input.json", changed)
        manifest = json.loads((public / "manifest.json").read_text(encoding="utf-8"))
        manifest["public_files"]["input.json"] = _hash(public / "input.json")
        _write_json(public / "manifest.json", manifest)

        result = self._consume()
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["body_and_profile_excited"])

    def test_wrong_body_b_prediction_fails_gate(self) -> None:
        public = self.pair / "body-b" / "public"
        changed = _summary("body_b")
        changed["accepted_actions"] = 89
        _write_bundle(public, "body_b")
        _write_json(public / "summary.json", changed)
        manifest = json.loads((public / "manifest.json").read_text(encoding="utf-8"))
        manifest["public_files"]["summary.json"] = _hash(public / "summary.json")
        _write_json(public / "manifest.json", manifest)

        result = self._consume()
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["body_b_frozen_prediction"])


if __name__ == "__main__":
    unittest.main()
