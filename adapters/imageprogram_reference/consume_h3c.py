"""Consume the frozen ImageProgram H3c jaw safe/rejected public artifact pair."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PUBLIC_FORMAT = "imageprogram-h3c-public-1"
OUTPUT_FORMAT = "imageprogram-arena-h3c-consume-1"
MANIFEST_FORMAT = "imageprogram-arena-h3c-golden-pair-manifest-1"

FORBIDDEN_PUBLIC_TOKENS = (
    "known_continuation",
    "witness_binding",
    "source_program",
    "private/",
    "private\\\\",
    ".npz",
)

ZERO_COST_FIELDS = (
    "skill_calls",
    "strokes",
    "motor_commands",
    "observations",
    "rollout_count",
    "tip_distance_m",
    "sim_time_s",
    "wall_time_s",
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


def validate_public_bundle(public_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify an ImageProgram public bundle without consulting sibling private artifacts."""

    manifest_path = public_dir / "manifest.json"
    manifest = read_json(manifest_path)
    if manifest.get("format") != PUBLIC_FORMAT:
        raise ValueError(f"unsupported public artifact format: {manifest.get('format')!r}")

    public_files = manifest.get("public_files")
    if not isinstance(public_files, dict) or not public_files:
        raise ValueError("public manifest must declare a non-empty public_files mapping")

    declared: set[str] = set()
    for name, expected_hash in public_files.items():
        if not isinstance(name, str) or not isinstance(expected_hash, str):
            raise ValueError("public_files must map string paths to string hashes")
        relative = _safe_relative_path(name)
        declared.add(relative.as_posix())
        path = public_dir / relative
        if not path.is_file():
            raise ValueError(f"declared public artifact is missing: {name}")
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
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != declared:
        missing = sorted(declared - actual)
        undeclared = sorted(actual - declared)
        raise ValueError(
            f"public manifest/file-set mismatch: missing={missing}, undeclared={undeclared}"
        )

    if "summary.json" not in declared:
        raise ValueError("public bundle must declare summary.json")

    return manifest, read_json(public_dir / "summary.json")


def _zero_cost(cost: Any) -> bool:
    if not isinstance(cost, dict):
        return False
    try:
        return all(float(cost[field]) == 0.0 for field in ZERO_COST_FIELDS)
    except (KeyError, TypeError, ValueError):
        return False


def _summary_checks(
    safe: dict[str, Any],
    rejected: dict[str, Any],
    benchmark_manifest: dict[str, Any],
) -> dict[str, bool]:
    expected = benchmark_manifest["expected"]
    selection = benchmark_manifest["selection"]
    safe_expected = expected["safe"]
    rejected_expected = expected["rejected"]

    checks = {
        "selected_target_fixture": (
            safe.get("target_fixture")
            == rejected.get("target_fixture")
            == selection["target_fixture"]
        ),
        "selected_variant": (
            safe.get("variant") == rejected.get("variant") == selection["variant"]
        ),
        "same_initial_state": safe.get("initial_state_hash") == rejected.get("initial_state_hash"),
        "safe_case": safe.get("case") == "safe",
        "safe_completed": safe.get("status") == safe_expected["status"],
        "safe_preflight": safe.get("preflight_status") == "safe",
        "safe_actions": safe.get("accepted_actions") == safe_expected["accepted_actions"],
        "safe_endpoint": safe.get("endpoint_error_m") == 0.0,
        "safe_protection": safe.get("protection_added_ink") == 0.0,
        "safe_replay": safe.get("replay_verified") is True,
        "safe_deterministic_replay": safe.get("replay_kind") == "deterministic_execution",
        "safe_private_access_zero": safe.get("policy_private_data_access") == 0,
        "safe_costs_separate": (
            isinstance(safe.get("preparation_cost"), dict)
            and isinstance(safe.get("continuation_cost"), dict)
        ),
        "rejected_case": rejected.get("case") == "rejected",
        "rejected_status": rejected.get("status") == rejected_expected["status"],
        "rejected_preflight": rejected.get("preflight_status") == "rejected",
        "rejected_actions_zero": rejected.get("accepted_actions") == 0,
        "rejected_state_identity": (
            rejected.get("initial_state_hash") == rejected.get("final_state_hash")
        ),
        "rejected_continuation_zero": _zero_cost(rejected.get("continuation_cost")),
        "rejected_replay": rejected.get("replay_verified") is True,
        "rejected_identity_replay": rejected.get("replay_kind") == "identity_no_execution",
        "rejected_private_access_zero": rejected.get("policy_private_data_access") == 0,
        "rejected_costs_separate": (
            isinstance(rejected.get("preparation_cost"), dict)
            and isinstance(rejected.get("continuation_cost"), dict)
        ),
    }
    return checks


def consume_golden_pair(
    *,
    matrix_root: Path,
    benchmark_manifest_path: Path,
    source_commit: str,
) -> dict[str, Any]:
    """Consume the frozen jaw pair while preserving ImageProgram summaries losslessly."""

    benchmark_manifest = read_json(benchmark_manifest_path)
    if benchmark_manifest.get("format") != MANIFEST_FORMAT:
        raise ValueError("unsupported Arena golden-pair manifest format")

    source = benchmark_manifest.get("source")
    if not isinstance(source, dict):
        raise ValueError("benchmark manifest requires source metadata")
    if source_commit != source.get("commit"):
        raise ValueError(
            f"source commit mismatch: expected {source.get('commit')}, got {source_commit}"
        )
    if source.get("artifact_format") != PUBLIC_FORMAT:
        raise ValueError("benchmark manifest pins an unsupported ImageProgram artifact format")

    cells = benchmark_manifest.get("cells")
    if not isinstance(cells, dict) or set(cells) != {"safe", "rejected"}:
        raise ValueError("benchmark manifest must select exactly safe and rejected cells")

    consumed: dict[str, dict[str, Any]] = {}
    for role in ("safe", "rejected"):
        cell = cells[role]
        if not isinstance(cell, str):
            raise ValueError(f"cell id for {role} must be a string")
        public_dir = matrix_root / cell / "public"
        public_manifest, summary = validate_public_bundle(public_dir)
        consumed[role] = {
            "cell": cell,
            "public_manifest_hash": file_hash(public_dir / "manifest.json"),
            "public_manifest": public_manifest,
            "summary": summary,
        }

    checks = _summary_checks(
        consumed["safe"]["summary"],
        consumed["rejected"]["summary"],
        benchmark_manifest,
    )
    passed = all(checks.values())

    return {
        "format": OUTPUT_FORMAT,
        "benchmark": benchmark_manifest["benchmark"],
        "lineage_id": benchmark_manifest["lineage_id"],
        "split": benchmark_manifest["split"],
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
    parser = argparse.ArgumentParser(description="Consume the frozen H3c jaw golden pair")
    parser.add_argument("--matrix-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    result = consume_golden_pair(
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
