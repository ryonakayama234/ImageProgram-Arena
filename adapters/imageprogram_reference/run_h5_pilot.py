"""Concrete cross-repo runner for the H5a 12x4 pilot.

This adapter consumes:
- ImageProgram #47 private pilot-lineage summary/checkpoints;
- ImageProgram #46 public fixed-candidate corpus;
- ImageProgram #50 one-candidate CLI.

Arena owns orchestration and artifact integrity only. It never reimplements
Construction lowering, World execution, or canonical Outcome measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from adapters.imageprogram_reference.h5_pilot_bundle import (
    EXPECTED_CANDIDATES_PER_LINEAGE,
    EXPECTED_LINEAGES,
    PILOT_BENCHMARK,
    PilotBundleError,
    run_pilot_bundle,
    verify_pilot_bundle,
    write_pilot_bundle,
)

ADAPTER_VERSION = "arena-imageprogram-h5-pilot-v0"
CANDIDATE_CORPUS_VERSION = "h5-fixed-candidate-corpus-v0"
LINEAGE_SUMMARY_VERSION = "h5-pilot-excitation-summary-v0"


def _read_json(path: Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(
            value,
            stream,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        stream.write("\n")


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PilotBundleError(f"{name} must be a non-empty string")
    return value


def _safe_checkpoint(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise PilotBundleError("checkpoint path escapes the #47 artifact root")
    if candidate.is_symlink() or not candidate.is_file():
        raise PilotBundleError("checkpoint path must resolve to a regular non-symlink file")
    return candidate


def _public_lineage_input(lineage: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "h5-fixed-candidate-lineage-input-v0",
        "task_lineage": lineage["task_lineage"],
        "source_lineage": lineage["source_lineage"],
        "parent_lineage": lineage.get("parent_lineage"),
        "public_state": lineage["public_state"],
        "profile": lineage["profile"],
    }


def prepare_h5_pilot_inputs(
    *,
    lineage_root: Path,
    candidate_corpus_path: Path,
    source_commit: str,
    descriptor: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Join #47 management checkpoints to #46 public candidates without schema forking."""

    lineage_root = Path(lineage_root)
    corpus = _read_json(candidate_corpus_path)
    if not isinstance(corpus, dict):
        raise PilotBundleError("candidate corpus must be a JSON object")
    if corpus.get("schema_version") != CANDIDATE_CORPUS_VERSION:
        raise PilotBundleError("unsupported ImageProgram candidate corpus version")
    if corpus.get("source_repository") != "ryonakayama234/ImageProgram":
        raise PilotBundleError("candidate corpus repository mismatch")
    if corpus.get("source_commit") != source_commit:
        raise PilotBundleError("candidate corpus source commit mismatch")
    corpus_hash = _require_string(corpus.get("corpus_hash"), "candidate corpus hash")
    if corpus.get("expected_lineages") != EXPECTED_LINEAGES:
        raise PilotBundleError("candidate corpus must declare exactly 12 lineages")
    if (
        corpus.get("expected_candidates_per_lineage")
        != EXPECTED_CANDIDATES_PER_LINEAGE
    ):
        raise PilotBundleError("candidate corpus must declare exactly 4 candidates/lineage")

    private_summary_path = lineage_root / "private" / "summary.json"
    private_summary = _read_json(private_summary_path)
    if not isinstance(private_summary, dict):
        raise PilotBundleError("#47 private summary must be a JSON object")
    if private_summary.get("schema_version") != LINEAGE_SUMMARY_VERSION:
        raise PilotBundleError("unsupported #47 private summary version")
    if private_summary.get("benchmark") != PILOT_BENCHMARK:
        raise PilotBundleError("#47 benchmark identity mismatch")
    if private_summary.get("source_repository") != "ryonakayama234/ImageProgram":
        raise PilotBundleError("#47 source repository mismatch")
    if private_summary.get("source_commit") != source_commit:
        raise PilotBundleError("#47 source commit mismatch")

    descriptor = dict(descriptor)
    contract_ref = descriptor.get("contract_ref")
    if not isinstance(contract_ref, dict):
        raise PilotBundleError("#50 descriptor missing contract_ref")
    if (
        contract_ref.get("repository") != "ryonakayama234/ImageProgram"
        or contract_ref.get("commit") != source_commit
    ):
        raise PilotBundleError("#50 descriptor source commit mismatch")
    runtime_version = _require_string(
        descriptor.get("runtime_version"), "#50 runtime_version"
    )
    evaluator_version = _require_string(
        descriptor.get("evaluator_version"), "#50 evaluator_version"
    )

    raw_private = private_summary.get("lineages")
    raw_public = corpus.get("lineages")
    if not isinstance(raw_private, list) or len(raw_private) != EXPECTED_LINEAGES:
        raise PilotBundleError("#47 summary must contain exactly 12 lineages")
    if not isinstance(raw_public, list) or len(raw_public) != EXPECTED_LINEAGES:
        raise PilotBundleError("#46 corpus must contain exactly 12 lineages")

    private_by_task: dict[str, dict[str, Any]] = {}
    for item in raw_private:
        if not isinstance(item, dict):
            raise PilotBundleError("#47 lineage summary must be a JSON object")
        task = _require_string(item.get("task_lineage"), "#47 task_lineage")
        if task in private_by_task:
            raise PilotBundleError(f"duplicate #47 task lineage: {task}")
        private_by_task[task] = item

    lineages: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for item in raw_public:
        if not isinstance(item, dict):
            raise PilotBundleError("#46 lineage must be a JSON object")
        task = _require_string(item.get("task_lineage"), "#46 task_lineage")
        source_lineage = _require_string(item.get("source_lineage"), "#46 source_lineage")
        if source_lineage in seen_sources:
            raise PilotBundleError(f"duplicate #46 source lineage: {source_lineage}")
        seen_sources.add(source_lineage)
        private = private_by_task.get(task)
        if private is None:
            raise PilotBundleError(f"#46 lineage has no #47 checkpoint: {task}")
        if private.get("source_lineage") != source_lineage:
            raise PilotBundleError(f"source lineage mismatch for {task}")

        public_input = _public_lineage_input(item)
        if _canonical_hash(public_input) != private.get("public_input_hash"):
            raise PilotBundleError(f"public input hash mismatch for {task}")

        checkpoint_rel = _require_string(
            private.get("checkpoint_relative_path"),
            f"{task}.checkpoint_relative_path",
        )
        checkpoint = _safe_checkpoint(lineage_root, checkpoint_rel)
        if _file_hash(checkpoint) != private.get("checkpoint_sha256"):
            raise PilotBundleError(f"checkpoint SHA-256 mismatch for {task}")
        management_state_hash = _require_string(
            private.get("management_initial_state_hash"),
            f"{task}.management_initial_state_hash",
        )

        candidates = item.get("candidates")
        if not isinstance(candidates, list) or len(candidates) != 4:
            raise PilotBundleError(f"{task} must carry exactly 4 fixed candidates")

        spec = {
            "task_lineage": task,
            "public_task_hash": item["public_task_hash"],
            "initial_public_state_hash": item["initial_public_state_hash"],
            "management_initial_state_hash": management_state_hash,
            "candidate_set_hash": item["candidate_set_hash"],
            "body_spec_hash": item["body_spec_hash"],
            "motor_profile_hash": item["motor_profile_hash"],
            "adapter_version": ADAPTER_VERSION,
            "runtime_version": runtime_version,
            "evaluator_version": evaluator_version,
            "contract_ref": contract_ref,
            "policy_input": {
                "public_state": item["public_state"],
                "profile": item["profile"],
            },
        }
        lineages.append(
            {
                "source_lineage": source_lineage,
                "parent_lineage": item.get("parent_lineage"),
                "spec": spec,
                "checkpoint": checkpoint,
                "checkpoint_sha256": private["checkpoint_sha256"],
                "lineage_payload": item,
                "candidates": candidates,
            }
        )

    if set(private_by_task) != {item["spec"]["task_lineage"] for item in lineages}:
        raise PilotBundleError("#47/#46 task lineage sets differ")

    source = {
        "repository": corpus["source_repository"],
        "commit": source_commit,
        "candidate_corpus_version": corpus["schema_version"],
        "candidate_corpus_hash": corpus_hash,
    }
    return source, sorted(lineages, key=lambda item: item["spec"]["task_lineage"])


def _validate_imageprogram_checkout(
    imageprogram_root: Path,
    source_commit: str,
) -> None:
    imageprogram_root = Path(imageprogram_root)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=imageprogram_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if head.returncode != 0:
        raise PilotBundleError(
            "cannot resolve ImageProgram Git HEAD: " + head.stderr.strip()
        )
    if head.stdout.strip() != source_commit:
        raise PilotBundleError(
            "ImageProgram checkout HEAD does not match --source-commit"
        )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=imageprogram_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if status.returncode != 0:
        raise PilotBundleError(
            "cannot inspect ImageProgram working tree: " + status.stderr.strip()
        )
    if status.stdout.strip():
        raise PilotBundleError(
            "ImageProgram working tree must be clean for the frozen H5 pilot"
        )


def _run_imageprogram_json(
    *,
    imageprogram_root: Path,
    arguments: list[str],
) -> dict[str, Any]:
    process = subprocess.run(
        ["uv", "run", "python", *arguments],
        cwd=Path(imageprogram_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        raise PilotBundleError(
            "ImageProgram command failed: "
            + " ".join(arguments)
            + f"\nstdout:\n{process.stdout}\nstderr:\n{process.stderr}"
        )
    try:
        value = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise PilotBundleError("ImageProgram command did not emit one JSON object") from exc
    if not isinstance(value, dict):
        raise PilotBundleError("ImageProgram command JSON must be an object")
    return value


def run_cross_repo_h5_pilot(
    *,
    imageprogram_root: Path,
    lineage_root: Path,
    candidate_corpus_path: Path,
    source_commit: str,
    output: Path,
) -> dict[str, Any]:
    """Run the concrete #47 -> #46 -> #50 -> Arena #9 pilot stack."""

    _validate_imageprogram_checkout(imageprogram_root, source_commit)

    output = Path(output)
    if output.exists():
        raise PilotBundleError("pilot output path already exists")
    output.mkdir(parents=True)
    branch_root = output / "branches"
    branch_root.mkdir()

    descriptor = _run_imageprogram_json(
        imageprogram_root=imageprogram_root,
        arguments=[
            "scripts/h5_candidate_branch.py",
            "--source-commit",
            source_commit,
            "--descriptor-only",
        ],
    )
    source, lineages = prepare_h5_pilot_inputs(
        lineage_root=lineage_root,
        candidate_corpus_path=candidate_corpus_path,
        source_commit=source_commit,
        descriptor=descriptor,
    )

    with tempfile.TemporaryDirectory(prefix="arena-h5-pilot-") as temp:
        temp_root = Path(temp)
        lineage_files: dict[str, Path] = {}
        for index, lineage in enumerate(lineages):
            task = lineage["spec"]["task_lineage"]
            lineage_file = temp_root / f"lineage-{index:02d}.json"
            _write_json(lineage_file, lineage["lineage_payload"])
            lineage_files[task] = lineage_file

        def restore_checkpoint(lineage: Mapping[str, Any], checkpoint: Any) -> dict[str, Any]:
            path = Path(checkpoint)
            if _file_hash(path) != lineage["checkpoint_sha256"]:
                raise PilotBundleError(
                    f"checkpoint changed before branch execution: {lineage['spec']['task_lineage']}"
                )
            return {
                "path": path,
                "state_hash": lineage["spec"]["management_initial_state_hash"],
            }

        def restored_state_hash(
            lineage: Mapping[str, Any],
            restored: Mapping[str, Any],
        ) -> str:
            return _require_string(restored.get("state_hash"), "restored state hash")

        def execute_candidate(
            lineage: Mapping[str, Any],
            restored: Mapping[str, Any],
            candidate: Mapping[str, Any],
            policy_input: Mapping[str, Any],
        ) -> Mapping[str, Any]:
            # policy_input has already passed Arena's public-boundary walker.
            del policy_input
            task = lineage["spec"]["task_lineage"]
            token = hashlib.sha256(task.encode("utf-8")).hexdigest()[:16]
            candidate_id = _require_string(candidate.get("candidate_id"), "candidate_id")
            branch_out = branch_root / token / candidate_id
            result = _run_imageprogram_json(
                imageprogram_root=imageprogram_root,
                arguments=[
                    "scripts/h5_candidate_branch.py",
                    "--source-commit",
                    source_commit,
                    "--lineage",
                    str(lineage_files[task]),
                    "--candidate-id",
                    candidate_id,
                    "--checkpoint",
                    str(restored["path"]),
                    "--adapter-version",
                    ADAPTER_VERSION,
                    "--out",
                    str(branch_out),
                ],
            )
            branch_result = result.get("branch_result")
            if not isinstance(branch_result, dict):
                raise PilotBundleError(
                    f"#50 did not return branch_result for {task}/{candidate_id}"
                )
            return branch_result

        bundle = run_pilot_bundle(
            source=source,
            lineages=lineages,
            restore_checkpoint=restore_checkpoint,
            restored_state_hash=restored_state_hash,
            execute_candidate=execute_candidate,
        )

    write_pilot_bundle(bundle, output / "pilot_bundle.json")
    audit = verify_pilot_bundle(bundle)
    _write_json(output / "pilot_audit.json", audit)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the concrete ImageProgram H5a 12x4 pilot through Arena."
    )
    parser.add_argument("--imageprogram-root", type=Path, required=True)
    parser.add_argument("--lineage-root", type=Path, required=True)
    parser.add_argument("--candidate-corpus", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    audit = run_cross_repo_h5_pilot(
        imageprogram_root=args.imageprogram_root,
        lineage_root=args.lineage_root,
        candidate_corpus_path=args.candidate_corpus,
        source_commit=args.source_commit,
        output=args.out,
    )
    print(json.dumps(audit, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if audit["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
