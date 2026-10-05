"""Consume the frozen H4 8-lineage / 16-run paired embodiment matrix.

Arena verifies every body public bundle independently. It never consumes the producer's
matrix_summary.json or sibling private directories as PASS authority.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from adapters.imageprogram_reference.consume_h4 import (
    FORBIDDEN_PUBLIC_TOKENS,
    _body_and_profile_excited,
    _motorization_excited,
    _safe_relative_path,
    _same_public_initial_state,
    _same_public_semantics,
    file_hash,
    read_json,
)

PUBLIC_FORMAT = "imageprogram-h4-matrix-body-public-1"
OUTPUT_FORMAT = "imageprogram-arena-h4-matrix-consume-1"
MANIFEST_FORMAT = "imageprogram-arena-h4-matrix-manifest-1"


def validate_matrix_public_bundle(
    public_dir: Path,
    *,
    case: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = read_json(public_dir / "manifest.json")
    if manifest.get("format") != PUBLIC_FORMAT:
        raise ValueError(
            f"unsupported H4 matrix public artifact format: {manifest.get('format')!r}"
        )

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

    required = {"input.json", "summary.json", "preflight.json", "replay_report.json"}
    if not required.issubset(declared):
        raise ValueError(
            f"H4 matrix public bundle missing required files: {sorted(required - declared)}"
        )
    if case == "safe" and "program.json" not in declared:
        raise ValueError("safe H4 matrix bundle must declare program.json")
    if case == "rejected" and "program.json" in declared:
        raise ValueError("rejected H4 matrix bundle must not contain program.json")

    return (
        manifest,
        read_json(public_dir / "input.json"),
        read_json(public_dir / "summary.json"),
    )


def _safe_completion_valid(summary: dict[str, Any]) -> bool:
    endpoint = summary.get("endpoint_error_m")
    return (
        summary.get("status") == "completed"
        and summary.get("preflight_status") == "safe"
        and summary.get("replay_verified") is True
        and summary.get("replay_kind") == "deterministic_execution"
        and summary.get("protection_added_ink") == 0.0
        and isinstance(endpoint, (int, float))
        and float(endpoint) <= 1e-12
        and summary.get("policy_private_data_access") == 0
    )


def _rejected_completion_valid(summary: dict[str, Any]) -> bool:
    continuation = summary.get("continuation_cost")
    if not isinstance(continuation, dict):
        return False
    try:
        sim_time = float(continuation["sim_time_s"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        summary.get("status") == "rejected"
        and summary.get("preflight_status") == "rejected"
        and summary.get("replay_verified") is True
        and summary.get("replay_kind") == "identity_no_execution"
        and summary.get("accepted_actions") == 0
        and summary.get("continuation_control_ticks") == 0
        and summary.get("newly_darkened_pixels") == 0
        and summary.get("protection_added_ink") == 0.0
        and summary.get("initial_state_hash") == summary.get("final_state_hash")
        and summary.get("motor_program_sha256") is None
        and summary.get("execution_budget_absolute") is None
        and continuation.get("motor_commands") == 0
        and math.isclose(sim_time, 0.0, rel_tol=0.0, abs_tol=1e-12)
        and summary.get("policy_private_data_access") == 0
    )


def _matches_expected(
    summary: dict[str, Any],
    expected: dict[str, Any],
    *,
    case: str,
) -> bool:
    if case == "rejected":
        return _rejected_completion_valid(summary)

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


def _consume_lineage(
    *,
    pair_root: Path,
    lineage: dict[str, Any],
) -> dict[str, Any]:
    lineage_id = lineage.get("lineage_id")
    folder = lineage.get("folder")
    target = lineage.get("target_fixture")
    variant = lineage.get("variant")
    case = lineage.get("case")
    expected = lineage.get("expected")
    if not all(isinstance(value, str) for value in (lineage_id, folder, target, variant, case)):
        raise ValueError("H4 matrix lineage requires string identity fields")
    if case not in {"safe", "rejected"}:
        raise ValueError(f"unsupported H4 matrix case: {case!r}")
    if not isinstance(expected, dict):
        raise ValueError("H4 matrix lineage requires expected predictions")

    consumed: dict[str, dict[str, Any]] = {}
    for role, body_folder in (("body_a", "body-a"), ("body_b", "body-b")):
        public_dir = pair_root / folder / body_folder / "public"
        public_manifest, public_input, summary = validate_matrix_public_bundle(
            public_dir,
            case=case,
        )
        consumed[role] = {
            "cell": f"{folder}/{body_folder}",
            "public_manifest_hash": file_hash(public_dir / "manifest.json"),
            "public_manifest": public_manifest,
            "input": public_input,
            "summary": summary,
        }

    input_a = consumed["body_a"]["input"]
    input_b = consumed["body_b"]["input"]
    summary_a = consumed["body_a"]["summary"]
    summary_b = consumed["body_b"]["summary"]

    identity_checks = {
        "body_ids": (
            summary_a.get("body_id") == "body_a"
            and summary_b.get("body_id") == "body_b"
        ),
        "target_fixture": (
            summary_a.get("target_fixture") == target
            and summary_b.get("target_fixture") == target
        ),
        "variant": (
            summary_a.get("variant") == variant
            and summary_b.get("variant") == variant
        ),
        "case": (
            summary_a.get("case") == case
            and summary_b.get("case") == case
        ),
    }

    if case == "safe":
        outcome_checks = {
            "body_a_completion_valid": _safe_completion_valid(summary_a),
            "body_b_completion_valid": _safe_completion_valid(summary_b),
            "motorization_excited": _motorization_excited(summary_a, summary_b),
        }
    else:
        outcome_checks = {
            "body_a_completion_valid": _rejected_completion_valid(summary_a),
            "body_b_completion_valid": _rejected_completion_valid(summary_b),
            "motorization_excited": True,
        }

    checks = {
        **identity_checks,
        "same_public_semantics": _same_public_semantics(input_a, input_b),
        "same_public_initial_state": _same_public_initial_state(input_a, input_b),
        "body_and_profile_excited": _body_and_profile_excited(input_a, input_b),
        **outcome_checks,
        "body_a_frozen_prediction": _matches_expected(
            summary_a,
            expected.get("body_a", {}),
            case=case,
        ),
        "body_b_frozen_prediction": _matches_expected(
            summary_b,
            expected.get("body_b", {}),
            case=case,
        ),
    }

    return {
        "lineage_id": lineage_id,
        "folder": folder,
        "target_fixture": target,
        "variant": variant,
        "case": case,
        "cells": consumed,
        "checks": checks,
        "passed": all(checks.values()),
    }


def consume_h4_matrix(
    *,
    matrix_root: Path,
    benchmark_manifest_path: Path,
    source_commit: str,
) -> dict[str, Any]:
    benchmark = read_json(benchmark_manifest_path)
    if benchmark.get("format") != MANIFEST_FORMAT:
        raise ValueError("unsupported Arena H4 matrix manifest format")

    source = benchmark.get("source")
    if not isinstance(source, dict):
        raise ValueError("H4 matrix benchmark manifest requires source metadata")
    if source_commit != source.get("commit"):
        raise ValueError(
            f"source commit mismatch: expected {source.get('commit')}, got {source_commit}"
        )
    if source.get("artifact_format") != PUBLIC_FORMAT:
        raise ValueError("H4 matrix manifest pins an unsupported artifact format")

    lineages = benchmark.get("lineages")
    if not isinstance(lineages, list) or len(lineages) != 8:
        raise ValueError("H4 matrix manifest must declare exactly 8 lineages")

    lineage_ids = [lineage.get("lineage_id") for lineage in lineages if isinstance(lineage, dict)]
    folders = [lineage.get("folder") for lineage in lineages if isinstance(lineage, dict)]
    if len(lineage_ids) != 8 or len(set(lineage_ids)) != 8:
        raise ValueError("H4 matrix lineage IDs must be unique")
    if len(folders) != 8 or len(set(folders)) != 8:
        raise ValueError("H4 matrix lineage folders must be unique")

    cases = [lineage.get("case") for lineage in lineages]
    if cases.count("safe") != 6 or cases.count("rejected") != 2:
        raise ValueError("H4 matrix must contain exactly 6 safe and 2 rejected lineages")

    consumed = [
        _consume_lineage(pair_root=matrix_root, lineage=lineage)
        for lineage in lineages
    ]
    safe = [lineage for lineage in consumed if lineage["case"] == "safe"]

    checks = {
        "independent_lineages": len(consumed) == 8,
        "total_runs": len(consumed) * 2 == 16,
        "safe_lineages": len(safe) == 6,
        "negative_lineages": len(consumed) - len(safe) == 2,
        "suite_motorization_excited": any(
            lineage["checks"]["motorization_excited"] for lineage in safe
        ),
        "all_lineages_pass": all(lineage["passed"] for lineage in consumed),
    }

    return {
        "format": OUTPUT_FORMAT,
        "benchmark": benchmark["benchmark"],
        "split": benchmark["split"],
        "source": {
            "repository": source["repository"],
            "commit": source_commit,
            "artifact_format": source["artifact_format"],
            "benchmark_manifest_hash": file_hash(benchmark_manifest_path),
        },
        "lineages": consumed,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consume the H4 8-lineage / 16-run paired embodiment matrix"
    )
    parser.add_argument("--matrix-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    result = consume_h4_matrix(
        matrix_root=args.matrix_root,
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
