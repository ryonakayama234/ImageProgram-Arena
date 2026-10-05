import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.consume_h4_matrix import (
    consume_h4_matrix,
    validate_matrix_public_bundle,
)

SOURCE_COMMIT = "1cbc861641f5948347d885f8a781cd3fe8e314e7"

LINEAGES = (
    ("jaw", "safe", "original", 49, 4.264503592, 90, 8.519007184),
    ("jaw", "safe", "affine_x_plus_0_10", 45, 3.843093389, 82, 7.676186779),
    ("hair", "safe", "original", 39, 3.662863535, 76, 7.315727070),
    ("hair", "safe", "affine_x_plus_0_10", 39, 3.587420432, 75, 7.164840864),
    (
        "neck_shoulders",
        "safe",
        "original",
        103,
        9.273600504,
        194,
        18.517201009,
    ),
    (
        "neck_shoulders",
        "safe",
        "affine_x_plus_0_10",
        98,
        8.837852166,
        185,
        17.645704332,
    ),
    ("jaw", "rejected", "original", 0, 0.0, 0, 0.0),
    ("neck_shoulders", "rejected", "original", 0, 0.0, 0, 0.0),
)


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


def _input(
    *,
    body_id: str,
    target: str,
    variant: str,
    case: str,
) -> dict:
    is_a = body_id == "body_a"
    return {
        "request_id": f"h4-matrix-public-{target}-{variant}-{case}-{body_id}",
        "observation": {
            "image_sha256": "sha256:" + target[0] * 64,
            "tip_position_m": {"x": 0.152, "y": 0.201},
            "tool": "pen",
            "sim_time_s": 46.0 if is_a else 112.0,
        },
        "scaffold": {
            "scaffold_id": f"character-bust-v0-{target}-{variant}",
            "nodes": [{"node_id": target, "realization": "missing"}],
        },
        "goal": {
            "goal_id": f"h3c-{target}-{variant}-{case}",
            "regions": [{"region_id": "h3c-guard"}],
            "conditions": [{"condition_id": "h3c-protect-guard"}],
        },
        "body": _body(0.1 if is_a else 0.025),
        "budget": {
            "max_sim_time_s": 90.0,
            "max_motor_commands": 256,
        },
        "profile": {
            "tool": "pen",
            "pressure": 0.5,
            "speed_m_s": 0.05 if is_a else 0.025,
        },
    }


def _summary(
    *,
    body_id: str,
    target: str,
    variant: str,
    case: str,
    actions: int,
    sim_time_s: float,
) -> dict:
    is_a = body_id == "body_a"
    initial = "sha256:" + ("1" if is_a else "2") * 64
    if case == "rejected":
        return {
            "body_id": body_id,
            "target_fixture": target,
            "variant": variant,
            "case": case,
            "status": "rejected",
            "preflight_status": "rejected",
            "initial_state_hash": initial,
            "final_state_hash": initial,
            "initial_image_sha256": "sha256:" + target[0] * 64,
            "motor_program_sha256": None,
            "accepted_actions": 0,
            "continuation_control_ticks": 0,
            "endpoint_error_m": None,
            "protection_added_ink": 0.0,
            "newly_darkened_pixels": 0,
            "replay_verified": True,
            "replay_kind": "identity_no_execution",
            "execution_budget_absolute": None,
            "policy_private_data_access": 0,
            "continuation_cost": {
                "motor_commands": 0,
                "sim_time_s": 0.0,
            },
        }

    return {
        "body_id": body_id,
        "target_fixture": target,
        "variant": variant,
        "case": case,
        "status": "completed",
        "preflight_status": "safe",
        "initial_state_hash": initial,
        "final_state_hash": "sha256:" + ("3" if is_a else "4") * 64,
        "initial_image_sha256": "sha256:" + target[0] * 64,
        "motor_program_sha256": "sha256:" + ("5" if is_a else "6") * 64,
        "accepted_actions": actions,
        "continuation_control_ticks": actions * 9,
        "endpoint_error_m": 0.0,
        "protection_added_ink": 0.0,
        "newly_darkened_pixels": 10,
        "replay_verified": True,
        "replay_kind": "deterministic_execution",
        "execution_budget_absolute": {"max_sim_time_s": 136.0 if is_a else 202.0},
        "policy_private_data_access": 0,
        "continuation_cost": {
            "motor_commands": actions,
            "sim_time_s": sim_time_s,
        },
    }


def _write_bundle(
    public_dir: Path,
    *,
    body_id: str,
    target: str,
    variant: str,
    case: str,
    actions: int,
    sim_time_s: float,
) -> None:
    _write_json(
        public_dir / "input.json",
        _input(body_id=body_id, target=target, variant=variant, case=case),
    )
    _write_json(
        public_dir / "summary.json",
        _summary(
            body_id=body_id,
            target=target,
            variant=variant,
            case=case,
            actions=actions,
            sim_time_s=sim_time_s,
        ),
    )
    _write_json(
        public_dir / "preflight.json",
        {"status": "safe" if case == "safe" else "rejected"},
    )
    _write_json(
        public_dir / "replay_report.json",
        {
            "verified": True,
            "kind": (
                "deterministic_execution"
                if case == "safe"
                else "identity_no_execution"
            ),
        },
    )
    names = [
        "input.json",
        "preflight.json",
        "replay_report.json",
        "summary.json",
    ]
    if case == "safe":
        _write_json(public_dir / "program.json", {"body_id": body_id})
        names.append("program.json")

    files = {name: _hash(public_dir / name) for name in names}
    _write_json(
        public_dir / "manifest.json",
        {
            "format": "imageprogram-h4-matrix-body-public-1",
            "public_files": files,
        },
    )


def _write_fixture(root: Path, manifest_path: Path) -> None:
    manifest_lineages = []
    for target, case, variant, a_actions, a_time, b_actions, b_time in LINEAGES:
        folder = f"{target}-{variant}-{case}"
        lineage_id = f"character-bust-v0/{target}/{variant}/{case}/h4-embodiment"
        _write_bundle(
            root / folder / "body-a" / "public",
            body_id="body_a",
            target=target,
            variant=variant,
            case=case,
            actions=a_actions,
            sim_time_s=a_time,
        )
        _write_bundle(
            root / folder / "body-b" / "public",
            body_id="body_b",
            target=target,
            variant=variant,
            case=case,
            actions=b_actions,
            sim_time_s=b_time,
        )
        manifest_lineages.append(
            {
                "lineage_id": lineage_id,
                "folder": folder,
                "target_fixture": target,
                "variant": variant,
                "case": case,
                "expected": {
                    "body_a": {
                        "accepted_actions": a_actions,
                        "sim_time_s": a_time,
                        "sim_time_tolerance_s": 1e-6,
                    },
                    "body_b": {
                        "accepted_actions": b_actions,
                        "sim_time_s": b_time,
                        "sim_time_tolerance_s": 1e-6,
                    },
                },
            }
        )

    _write_json(
        manifest_path,
        {
            "format": "imageprogram-arena-h4-matrix-manifest-1",
            "benchmark": "complete_structure_v0",
            "split": "h4_full_matrix",
            "source": {
                "repository": "ryonakayama234/ImageProgram",
                "commit": SOURCE_COMMIT,
                "artifact_format": "imageprogram-h4-matrix-body-public-1",
            },
            "lineages": manifest_lineages,
        },
    )


class H4MatrixConsumerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.matrix = self.root / "matrix"
        self.manifest = self.root / "benchmark.json"
        _write_fixture(self.matrix, self.manifest)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _consume(self) -> dict:
        return consume_h4_matrix(
            matrix_root=self.matrix,
            benchmark_manifest_path=self.manifest,
            source_commit=SOURCE_COMMIT,
        )

    def test_consumes_exact_eight_lineages_and_sixteen_runs(self) -> None:
        result = self._consume()
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["lineages"]), 8)
        self.assertTrue(result["checks"]["independent_lineages"])
        self.assertTrue(result["checks"]["total_runs"])
        self.assertTrue(result["checks"]["safe_lineages"])
        self.assertTrue(result["checks"]["negative_lineages"])
        self.assertTrue(result["checks"]["suite_motorization_excited"])
        self.assertTrue(result["checks"]["all_lineages_pass"])

    def test_negative_bundles_require_identity_no_execution(self) -> None:
        result = self._consume()
        negatives = [x for x in result["lineages"] if x["case"] == "rejected"]
        self.assertEqual(len(negatives), 2)
        for lineage in negatives:
            with self.subTest(lineage=lineage["lineage_id"]):
                self.assertTrue(lineage["passed"])
                self.assertTrue(lineage["checks"]["body_a_completion_valid"])
                self.assertTrue(lineage["checks"]["body_b_completion_valid"])

    def test_rejected_bundle_with_program_is_rejected(self) -> None:
        public = self.matrix / "jaw-original-rejected" / "body-a" / "public"
        _write_json(public / "program.json", {"must_not_exist": True})
        manifest = json.loads((public / "manifest.json").read_text(encoding="utf-8"))
        manifest["public_files"]["program.json"] = _hash(public / "program.json")
        _write_json(public / "manifest.json", manifest)

        with self.assertRaisesRegex(ValueError, "must not contain program.json"):
            validate_matrix_public_bundle(public, case="rejected")

    def test_sibling_private_directory_is_not_consumed(self) -> None:
        secret = (
            self.matrix
            / "neck_shoulders-original-safe"
            / "body-b"
            / "private"
            / "secret.json"
        )
        _write_json(secret, {"known_continuation": "must remain unreachable"})
        self.assertTrue(self._consume()["passed"])

    def test_changed_scaffold_breaks_only_that_lineage_gate(self) -> None:
        public = self.matrix / "hair-original-safe" / "body-b" / "public"
        changed = _input(
            body_id="body_b",
            target="hair",
            variant="original",
            case="safe",
        )
        changed["scaffold"]["scaffold_id"] = "body-specific-shortcut"
        _write_json(public / "input.json", changed)
        manifest = json.loads((public / "manifest.json").read_text(encoding="utf-8"))
        manifest["public_files"]["input.json"] = _hash(public / "input.json")
        _write_json(public / "manifest.json", manifest)

        result = self._consume()
        self.assertFalse(result["passed"])
        lineage = next(
            x
            for x in result["lineages"]
            if x["folder"] == "hair-original-safe"
        )
        self.assertFalse(lineage["checks"]["same_public_semantics"])

    def test_wrong_prediction_fails_matrix(self) -> None:
        public = self.matrix / "jaw-affine_x_plus_0_10-safe" / "body-b" / "public"
        changed = _summary(
            body_id="body_b",
            target="jaw",
            variant="affine_x_plus_0_10",
            case="safe",
            actions=81,
            sim_time_s=7.676186779,
        )
        _write_json(public / "summary.json", changed)
        manifest = json.loads((public / "manifest.json").read_text(encoding="utf-8"))
        manifest["public_files"]["summary.json"] = _hash(public / "summary.json")
        _write_json(public / "manifest.json", manifest)

        result = self._consume()
        self.assertFalse(result["passed"])
        lineage = next(
            x
            for x in result["lineages"]
            if x["folder"] == "jaw-affine_x_plus_0_10-safe"
        )
        self.assertFalse(lineage["checks"]["body_b_frozen_prediction"])

    def test_wrong_source_commit_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "source commit mismatch"):
            consume_h4_matrix(
                matrix_root=self.matrix,
                benchmark_manifest_path=self.manifest,
                source_commit="deadbeef",
            )


if __name__ == "__main__":
    unittest.main()
