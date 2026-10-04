"""Consume ImageProgram H4 paired-embodiment public artifacts.

Arena re-checks the pair from the two body public bundles. It does not trust ImageProgram's
pair-level summary as PASS authority and never reads sibling private directories.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

PUBLIC_FORMAT = "imageprogram-h4-body-public-1"
OUTPUT_FORMAT = "imageprogram-arena-h4-pair-consume-1"
MANIFEST_FORMAT = "imageprogram-arena-h4-pair-manifest-1"

FORBIDDEN_PUBLIC_TOKENS = (
    "known_continuation",
    "witness_binding",
    "source_program",
    "private/",
    "private\\\\",
    ".npz",
)


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _safe_relative_path(name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or "private" in relative.parts:
        raise ValueError(f"non-public artifact path in manifest: {name}")
    return relative


def validate_public_bundle(
    public_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Verify one H4 public body bundle without consulting sibling private artifacts."""

    manifest = read_json(public_dir / "manifest.json")
    if manifest.get("format") != PUBLIC_FORMAT:
        raise ValueError(f"unsupported H4 public artifact format: {manifest.get('format')!r}")

    public_files = manifest.get("public_files")
    if not isinstance(public_files, dict) or not public_files:
        raise ValueError("public manifest must declare a non-empty public_files mapping")

    public_root = public_dir.resolve()
    declared: set[str] = set()
    for name, expected_hash in public_files.items():
        if not isinstance(name, str) or not isinstance(expected_hash, str):
            raise ValueError("public_files must map string paths to string hashes")
        relative = _safe_relative_path(name)
        declared.add(relative.as_posix())
        path = public_dir / relative
        if (
            not path.resolve().is_relative_to(public_root)
            or path.is_symlink()
            or not path.is_file()
        ):
            raise ValueError(f"invalid public artifact path: {name}")
        actual_hash = file_hash(path)
        if actual_hash != expected_hash:
            raise ValueError(
                f"public artifact hash mismatch for {name}: "
                f"expected {expected_hash}, got {actual_hash}"
            )

        if path.suffix in {".json", ".jsonl"}:
            text = path.read_text(encoding="utf-8").lower()
            for token in FORBIDDEN_PUBLIC_TOKENS:
                if token in text:
                    raise ValueError(f"public artifact leaked management token: {token}")

    actual = {
        path.relative_to(public_dir).as_posix()
        for path in public_dir.rglob("*")
        if path.is_file() and path.relative_to(public_dir) != Path("manifest.json")
    }
    if actual != declared:
        raise ValueError(
            "public manifest/file-set mismatch: "
            f"missing={sorted(declared - actual)}, undeclared={sorted(actual - declared)}"
        )

    for required in ("input.json", "summary.json", "program.json", "replay_report.json"):
        if required not in declared:
            raise ValueError(f"H4 public bundle must declare {required}")

    return (
        manifest,
        read_json(public_dir / "input.json"),
        read_json(public_dir / "summary.json"),
    )


def _same_public_semantics(a: dict[str, Any], b: dict[str, Any]) -> bool:
    body_a = a.get("body")
    body_b = b.get("body")
    if not isinstance(body_a, dict) or not isinstance(body_b, dict):
        return False

    same_canvas = all(
        body_a.get(field) == body_b.get(field)
        for field in (
            "canvas_width_m",
            "canvas_height_m",
            "raster_width_px",
            "raster_height_px",
            "control_dt_s",
            "tools",
        )
    )
    return (
        a.get("scaffold") == b.get("scaffold")
        and a.get("goal") == b.get("goal")
        and a.get("budget") == b.get("budget")
        and same_canvas
    )


def _same_public_initial_state(a: dict[str, Any], b: dict[str, Any]) -> bool:
    obs_a = a.get("observation")
    obs_b = b.get("observation")
    if not isinstance(obs_a, dict) or not isinstance(obs_b, dict):
        return False
    return all(
        obs_a.get(field) == obs_b.get(field)
        for field in ("image_sha256", "tip_position_m", "tool")
    )


def _body_and_profile_excited(a: dict[str, Any], b: dict[str, Any]) -> bool:
    body_a = a.get("body")
    body_b = b.get("body")
    profile_a = a.get("profile")
    profile_b = b.get("profile")
    if not all(isinstance(value, dict) for value in (body_a, body_b, profile_a, profile_b)):
        return False
    return (
        body_a.get("max_speed_m_s") != body_b.get("max_speed_m_s")
        and profile_a.get("speed_m_s") != profile_b.get("speed_m_s")
    )


def _completion_valid(summary: dict[str, Any]) -> bool:
    endpoint = summary.get("endpoint_error_m")
    return (
        summary.get("status") == "completed"
        and summary.get("replay_verified") is True
        and summary.get("protection_added_ink") == 0.0
        and isinstance(endpoint, (int, float))
        and float(endpoint) <= 1e-12
        and summary.get("policy_private_data_access") == 0
    )


def _motorization_excited(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("motor_program_sha256") == b.get("motor_program_sha256"):
        return False
    return any(
        (
            a.get("accepted_actions") != b.get("accepted_actions"),
            a.get("continuation_control_ticks") != b.get("continuation_control_ticks"),
            a.get("continuation_cost", {}).get("sim_time_s")
            != b.get("continuation_cost", {}).get("sim_time_s"),
        )
    )


def _matches_expected(
    summary: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    try:
        actual_time = float(summary["continuation_cost"]["sim_time_s"])
        expected_time = float(expected["sim_time_s"])
        tolerance = float(expected["sim_time_tolerance_s"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        summary.get("accepted_actions") == expected.get("accepted_actions")
        and math.isclose(
            actual_time,
            expected_time,
            rel_tol=0.0,
            abs_tol=tolerance,
        )
    )


def consume_h4_pair(
    *,
    pair_root: Path,
    benchmark_manifest_path: Path,
    source_commit: str,
) -> dict[str, Any]:
    """Consume and independently re-check the frozen H4 Phase 1 jaw pair."""

    benchmark = read_json(benchmark_manifest_path)
    if benchmark.get("format") != MANIFEST_FORMAT:
        raise ValueError("unsupported Arena H4 pair manifest format")

    source = benchmark.get("source")
    if not isinstance(source, dict):
        raise ValueError("H4 benchmark manifest requires source metadata")
    if source_commit != source.get("commit"):
        raise ValueError(
            f"source commit mismatch: expected {source.get('commit')}, got {source_commit}"
        )
    if source.get("artifact_format") != PUBLIC_FORMAT:
        raise ValueError("H4 benchmark manifest pins an unsupported artifact format")

    cells = benchmark.get("cells")
    if not isinstance(cells, dict) or set(cells) != {"body_a", "body_b"}:
        raise ValueError("H4 benchmark manifest must select exactly body_a and body_b")

    consumed: dict[str, dict[str, Any]] = {}
    for role in ("body_a", "body_b"):
        folder = cells[role]
        if not isinstance(folder, str):
            raise ValueError(f"H4 cell path for {role} must be a string")
        public_dir = pair_root / folder / "public"
        public_manifest, public_input, summary = validate_public_bundle(public_dir)
        consumed[role] = {
            "cell": folder,
            "public_manifest_hash": file_hash(public_dir / "manifest.json"),
            "public_manifest": public_manifest,
            "input": public_input,
            "summary": summary,
        }

    input_a = consumed["body_a"]["input"]
    input_b = consumed["body_b"]["input"]
    summary_a = consumed["body_a"]["summary"]
    summary_b = consumed["body_b"]["summary"]
    expected = benchmark.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("H4 benchmark manifest requires expected predictions")

    checks = {
        "body_ids": (
            summary_a.get("body_id") == "body_a"
            and summary_b.get("body_id") == "body_b"
        ),
        "same_public_semantics": _same_public_semantics(input_a, input_b),
        "same_public_initial_state": _same_public_initial_state(input_a, input_b),
        "body_and_profile_excited": _body_and_profile_excited(input_a, input_b),
        "body_a_completion_valid": _completion_valid(summary_a),
        "body_b_completion_valid": _completion_valid(summary_b),
        "motorization_excited": _motorization_excited(summary_a, summary_b),
        "body_a_frozen_prediction": _matches_expected(
            summary_a,
            expected["body_a"],
        ),
        "body_b_frozen_prediction": _matches_expected(
            summary_b,
            expected["body_b"],
        ),
    }
    passed = all(checks.values())

    return {
        "format": OUTPUT_FORMAT,
        "benchmark": benchmark["benchmark"],
        "lineage_id": benchmark["lineage_id"],
        "split": benchmark["split"],
        "source": {
            "repository": source["repository"],
            "commit": source_commit,
            "artifact_format": source["artifact_format"],
            "benchmark_manifest_hash": file_hash(benchmark_manifest_path),
        },
        "cells": consumed,
        "checks": checks,
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Consume the H4 jaw paired embodiment run")
    parser.add_argument("--pair-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    result = consume_h4_pair(
        pair_root=args.pair_root,
        benchmark_manifest_path=args.manifest,
        source_commit=args.source_commit,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
