"""Arena-side H5a 12x4 pilot bundle orchestration.

This module composes the already-frozen same-checkpoint branch-isolation harness
across exactly twelve task lineages. It does not generate Construction candidates
or own ImageProgram runtime/model logic. The caller supplies ImageProgram-produced
public candidate sets plus lineage-specific checkpoint/runtime callbacks.

The raw bundle preserves measured branch outcomes and costs. An independent
consumer recomputes integrity checks from those raw candidate-level artifacts
instead of trusting the producer summary.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from adapters.imageprogram_reference.h5_branch_isolation import (
    BranchIsolationError,
    REPORT_FORMAT,
    candidate_manifest_hash,
    run_exhaustive_branches,
)

PILOT_FORMAT = "imageprogram-arena-h5-pilot-bundle-1"
PILOT_AUDIT_FORMAT = "imageprogram-arena-h5-pilot-audit-1"
PILOT_BENCHMARK = "complete_structure_pilot_v0"
EXPECTED_LINEAGES = 12
EXPECTED_CANDIDATES_PER_LINEAGE = 4

_COST_FIELDS = (
    "skill_calls",
    "strokes",
    "motor_commands",
    "observations",
    "rollout_count",
    "tip_distance_m",
    "sim_time_s",
    "wall_time_s",
)


class PilotBundleError(ValueError):
    """The H5 pilot bundle violated a frozen producer/consumer invariant."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PilotBundleError(f"{name} must be a mapping")
    return value


def _require_string(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PilotBundleError(f"{name} must be a non-empty string")
    return value


def _semantic_projection(value: Any) -> Any:
    """Remove run-local identity/timing while retaining measured semantics."""

    if isinstance(value, Mapping):
        return {
            key: _semantic_projection(child)
            for key, child in value.items()
            if key not in {"record_id", "wall_time_s", "semantic_bundle_hash"}
        }
    if isinstance(value, list):
        return [_semantic_projection(child) for child in value]
    if isinstance(value, tuple):
        return [_semantic_projection(child) for child in value]
    return value


def _lineage_descriptor(lineage: Mapping[str, Any]) -> dict[str, Any]:
    spec = _require_mapping(lineage.get("spec"), name="lineage.spec")
    candidates = lineage.get("candidates")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise PilotBundleError("lineage.candidates must be a sequence")
    if len(candidates) != EXPECTED_CANDIDATES_PER_LINEAGE:
        raise PilotBundleError(
            f"each pilot lineage requires {EXPECTED_CANDIDATES_PER_LINEAGE} candidates"
        )
    required_spec = (
        "task_lineage",
        "public_task_hash",
        "initial_public_state_hash",
        "management_initial_state_hash",
        "candidate_set_hash",
        "body_spec_hash",
        "motor_profile_hash",
        "adapter_version",
        "runtime_version",
        "evaluator_version",
        "contract_ref",
    )
    missing = [field for field in required_spec if field not in spec]
    if missing:
        raise PilotBundleError(f"lineage.spec missing required fields: {missing}")
    task_lineage = _require_string(spec["task_lineage"], name="spec.task_lineage")
    source_lineage = _require_string(
        lineage.get("source_lineage"), name=f"{task_lineage}.source_lineage"
    )
    parent_lineage = lineage.get("parent_lineage")
    if parent_lineage is not None:
        parent_lineage = _require_string(
            parent_lineage, name=f"{task_lineage}.parent_lineage"
        )
    return {
        "task_lineage": task_lineage,
        "source_lineage": source_lineage,
        "parent_lineage": parent_lineage,
        "public_task_hash": spec["public_task_hash"],
        "initial_public_state_hash": spec["initial_public_state_hash"],
        "management_initial_state_hash": spec["management_initial_state_hash"],
        "candidate_set_hash": spec["candidate_set_hash"],
        "candidate_manifest_hash": candidate_manifest_hash(candidates),
        "body_spec_hash": spec["body_spec_hash"],
        "motor_profile_hash": spec["motor_profile_hash"],
        "adapter_version": spec["adapter_version"],
        "runtime_version": spec["runtime_version"],
        "evaluator_version": spec["evaluator_version"],
    }


def _validate_lineage_inputs(
    lineages: Sequence[Mapping[str, Any]],
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    if len(lineages) != EXPECTED_LINEAGES:
        raise PilotBundleError(
            f"H5 pilot requires exactly {EXPECTED_LINEAGES} task lineages"
        )
    prepared: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    seen_tasks: set[str] = set()
    seen_sources: set[str] = set()
    for index, raw in enumerate(lineages):
        lineage = _require_mapping(raw, name=f"lineage[{index}]")
        if "checkpoint" not in lineage:
            raise PilotBundleError(f"lineage[{index}] missing checkpoint")
        descriptor = _lineage_descriptor(lineage)
        task_lineage = descriptor["task_lineage"]
        source_lineage = descriptor["source_lineage"]
        if task_lineage in seen_tasks:
            raise PilotBundleError(f"duplicate task_lineage: {task_lineage}")
        if source_lineage in seen_sources:
            raise PilotBundleError(f"duplicate source_lineage: {source_lineage}")
        seen_tasks.add(task_lineage)
        seen_sources.add(source_lineage)
        prepared.append((lineage, descriptor))
    return sorted(prepared, key=lambda item: item[1]["task_lineage"])


def _lineage_manifest_hash(descriptors: Sequence[Mapping[str, Any]]) -> str:
    return _sha256_json(
        sorted((dict(item) for item in descriptors), key=lambda item: item["task_lineage"])
    )


def run_pilot_bundle(
    *,
    source: Mapping[str, Any],
    lineages: Sequence[Mapping[str, Any]],
    restore_checkpoint: Callable[[Mapping[str, Any], Any], Any],
    restored_state_hash: Callable[[Mapping[str, Any], Any], str],
    execute_candidate: Callable[
        [Mapping[str, Any], Any, Mapping[str, Any], Mapping[str, Any]],
        Mapping[str, Any],
    ],
) -> dict[str, Any]:
    """Execute the frozen 12x4 pilot through the existing branch harness.

    Candidate generation is deliberately absent. Each lineage must already contain
    the ImageProgram-produced fixed public candidate set and an opaque management
    checkpoint. The checkpoint never enters the returned bundle.
    """

    source = dict(_require_mapping(source, name="source"))
    _require_string(source.get("repository"), name="source.repository")
    _require_string(source.get("commit"), name="source.commit")
    _require_string(
        source.get("candidate_corpus_version"),
        name="source.candidate_corpus_version",
    )
    _require_string(
        source.get("candidate_corpus_hash"),
        name="source.candidate_corpus_hash",
    )
    prepared = _validate_lineage_inputs(lineages)
    descriptors = [descriptor for _, descriptor in prepared]
    manifest_hash = _lineage_manifest_hash(descriptors)

    outputs: list[dict[str, Any]] = []
    for lineage, descriptor in prepared:
        spec = _require_mapping(lineage["spec"], name="lineage.spec")
        candidates = lineage["candidates"]
        candidate_ids = sorted(
            _require_string(candidate.get("candidate_id"), name="candidate_id")
            for candidate in candidates
        )

        try:
            report = run_exhaustive_branches(
                spec=spec,
                checkpoint=lineage["checkpoint"],
                candidates=candidates,
                restore_checkpoint=lambda checkpoint, _lineage=lineage: restore_checkpoint(
                    _lineage, checkpoint
                ),
                restored_state_hash=lambda state, _lineage=lineage: restored_state_hash(
                    _lineage, state
                ),
                execute_candidate=lambda state, candidate, policy_input, _lineage=lineage: (
                    execute_candidate(_lineage, state, candidate, policy_input)
                ),
                order=candidate_ids,
            )
        except BranchIsolationError as exc:
            raise PilotBundleError(
                f"branch-isolation failure for {descriptor['task_lineage']}: {exc}"
            ) from exc

        outputs.append(
            {
                **descriptor,
                "execution_order_policy": "canonical_candidate_id",
                "candidates": [
                    copy.deepcopy(candidate)
                    for candidate in sorted(
                        candidates, key=lambda candidate: candidate["candidate_id"]
                    )
                ],
                "report": report,
            }
        )

    bundle: dict[str, Any] = {
        "format": PILOT_FORMAT,
        "benchmark": PILOT_BENCHMARK,
        "source": copy.deepcopy(source),
        "expected_lineages": EXPECTED_LINEAGES,
        "expected_candidates_per_lineage": EXPECTED_CANDIDATES_PER_LINEAGE,
        "lineage_manifest_hash": manifest_hash,
        "lineages": outputs,
    }
    bundle["semantic_bundle_hash"] = _sha256_json(_semantic_projection(bundle))

    audit = verify_pilot_bundle(bundle)
    if not audit["passed"]:
        failed = [name for name, passed in audit["checks"].items() if not passed]
        raise PilotBundleError(f"producer self-audit failed: {failed}")
    return bundle


def _accumulate_cost(total: dict[str, float], cost: Mapping[str, Any]) -> None:
    for field in _COST_FIELDS:
        value = cost.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise PilotBundleError(f"branch_research_cost.{field} must be numeric")
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0:
            raise PilotBundleError(
                f"branch_research_cost.{field} must be finite and nonnegative"
            )
        total[field] += numeric


def verify_pilot_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Independently recompute #9 integrity from raw lineage/branch artifacts."""

    bundle = _require_mapping(bundle, name="pilot bundle")
    if bundle.get("format") != PILOT_FORMAT:
        raise PilotBundleError(f"unsupported pilot format: {bundle.get('format')!r}")
    source = _require_mapping(bundle.get("source"), name="bundle.source")
    _require_string(source.get("repository"), name="source.repository")
    _require_string(source.get("commit"), name="source.commit")
    _require_string(
        source.get("candidate_corpus_version"),
        name="source.candidate_corpus_version",
    )
    _require_string(
        source.get("candidate_corpus_hash"),
        name="source.candidate_corpus_hash",
    )
    lineages = bundle.get("lineages")
    if not isinstance(lineages, list):
        raise PilotBundleError("bundle.lineages must be a list")

    unique_lineages: set[str] = set()
    unique_source_lineages: set[str] = set()
    descriptors: list[dict[str, Any]] = []
    total_branches = 0
    missing_branches = 0
    replay_failures = 0
    raw_cost = {field: 0.0 for field in _COST_FIELDS}
    lineage_checks: dict[str, dict[str, bool]] = {}

    for index, raw in enumerate(lineages):
        item = _require_mapping(raw, name=f"bundle.lineages[{index}]")
        task_lineage = _require_string(
            item.get("task_lineage"), name=f"lineage[{index}].task_lineage"
        )
        duplicate = task_lineage in unique_lineages
        unique_lineages.add(task_lineage)
        source_lineage = _require_string(
            item.get("source_lineage"), name=f"lineage[{index}].source_lineage"
        )
        duplicate_source = source_lineage in unique_source_lineages
        unique_source_lineages.add(source_lineage)

        candidate_snapshots = item.get("candidates")
        if not isinstance(candidate_snapshots, list):
            raise PilotBundleError(f"{task_lineage}.candidates must be a list")
        if len(candidate_snapshots) != EXPECTED_CANDIDATES_PER_LINEAGE:
            raise PilotBundleError(
                f"{task_lineage} requires {EXPECTED_CANDIDATES_PER_LINEAGE} candidate snapshots"
            )
        try:
            recomputed_candidate_manifest_hash = candidate_manifest_hash(candidate_snapshots)
        except BranchIsolationError as exc:
            raise PilotBundleError(
                f"{task_lineage} candidate snapshot boundary failure: {exc}"
            ) from exc
        snapshot_by_id: dict[str, Mapping[str, Any]] = {}
        for candidate_index, raw_candidate in enumerate(candidate_snapshots):
            candidate = _require_mapping(
                raw_candidate, name=f"{task_lineage}.candidates[{candidate_index}]"
            )
            candidate_id = _require_string(
                candidate.get("candidate_id"),
                name=f"{task_lineage}.candidates[{candidate_index}].candidate_id",
            )
            if candidate_id in snapshot_by_id:
                raise PilotBundleError(
                    f"{task_lineage} duplicate candidate snapshot: {candidate_id}"
                )
            snapshot_by_id[candidate_id] = candidate

        report = _require_mapping(item.get("report"), name=f"{task_lineage}.report")
        if report.get("format") != REPORT_FORMAT:
            raise PilotBundleError(f"{task_lineage} uses unexpected branch report format")
        branches = report.get("branches")
        if not isinstance(branches, list):
            raise PilotBundleError(f"{task_lineage}.report.branches must be a list")
        total_branches += len(branches)

        report_contract_ref = _require_mapping(
            report.get("contract_ref"), name=f"{task_lineage}.report.contract_ref"
        )
        source_contract_pinned = (
            report_contract_ref.get("repository") == source.get("repository")
            and report_contract_ref.get("commit") == source.get("commit")
        )
        candidate_ids: set[str] = set()
        initial_hashes: set[str] = set()
        replay_ok = True
        candidate_payload_links_valid = True
        branch_semantic_digests_valid = True
        record_provenance_valid = True
        prediction_inputs_public_only = True
        for branch_index, raw_branch in enumerate(branches):
            branch = _require_mapping(
                raw_branch, name=f"{task_lineage}.branches[{branch_index}]"
            )
            candidate_id = _require_string(
                branch.get("candidate_id"), name=f"{task_lineage}.candidate_id"
            )
            candidate_ids.add(candidate_id)
            initial_hashes.add(
                _require_string(
                    branch.get("initial_state_hash"),
                    name=f"{task_lineage}.{candidate_id}.initial_state_hash",
                )
            )
            record = _require_mapping(
                branch.get("outcome_record"),
                name=f"{task_lineage}.{candidate_id}.outcome_record",
            )
            snapshot = snapshot_by_id.get(candidate_id)
            if snapshot is None:
                candidate_payload_links_valid = False
            else:
                candidate_payload_links_valid = candidate_payload_links_valid and (
                    record.get("candidate_id") == candidate_id
                    and record.get("candidate_public_payload_hash")
                    == snapshot.get("candidate_public_payload_hash")
                )
            expected_branch_digest = _sha256_json(
                _semantic_projection(
                    {
                        "candidate_id": candidate_id,
                        "initial_state_hash": branch.get("initial_state_hash"),
                        "final_state_hash": branch.get("final_state_hash"),
                        "outcome_record": record,
                        "policy_execution_cost": branch.get("policy_execution_cost"),
                    }
                )
            )
            branch_semantic_digests_valid = branch_semantic_digests_valid and (
                branch.get("semantic_digest") == expected_branch_digest
            )
            record_provenance_valid = record_provenance_valid and all(
                record.get(field) == item.get(field)
                for field in (
                    "task_lineage",
                    "public_task_hash",
                    "initial_public_state_hash",
                    "candidate_set_hash",
                    "body_spec_hash",
                    "motor_profile_hash",
                    "adapter_version",
                    "runtime_version",
                    "evaluator_version",
                )
            )
            prediction_input = _require_mapping(
                record.get("prediction_input"),
                name=f"{task_lineage}.{candidate_id}.prediction_input",
            )
            prediction_inputs_public_only = prediction_inputs_public_only and (
                prediction_input.get("public_only") is True
                and prediction_input.get("sha256") == item.get("initial_public_state_hash")
            )
            status = record.get("record_status")
            branch_replay_ok = True
            if status == "missing":
                missing_branches += 1
                if not record.get("missing_reason_code"):
                    raise PilotBundleError(
                        f"{task_lineage}/{candidate_id} missing record lacks reason"
                    )
                replay_status = record.get("replay_status")
                if replay_status not in {"failed", "not_available"}:
                    branch_replay_ok = False
            elif status == "observed":
                replay_status = record.get("replay_status")
                if replay_status not in {"verified", "identity_no_execution"}:
                    branch_replay_ok = False
            else:
                raise PilotBundleError(
                    f"{task_lineage}/{candidate_id} has unsupported record_status"
                )
            replay_ok = replay_ok and branch_replay_ok
            if not branch_replay_ok:
                replay_failures += 1
            _accumulate_cost(
                raw_cost,
                _require_mapping(
                    record.get("branch_research_cost"),
                    name=f"{task_lineage}.{candidate_id}.branch_research_cost",
                ),
            )

        same_initial = (
            len(initial_hashes) == 1
            and initial_hashes == {item.get("management_initial_state_hash")}
            and report.get("management_initial_state_hash")
            == item.get("management_initial_state_hash")
        )
        checks = {
            "not_duplicate_lineage": not duplicate,
            "not_duplicate_source_lineage": not duplicate_source,
            "report_passed": report.get("passed") is True,
            "exact_candidate_count": len(branches) == EXPECTED_CANDIDATES_PER_LINEAGE,
            "unique_candidate_ids": (
                len(candidate_ids) == EXPECTED_CANDIDATES_PER_LINEAGE
                and candidate_ids == set(snapshot_by_id)
            ),
            "same_management_initial_state": same_initial,
            "candidate_set_hash_bound": (
                report.get("candidate_set_hash") == item.get("candidate_set_hash")
            ),
            "candidate_manifest_hash_recomputed": (
                recomputed_candidate_manifest_hash
                == item.get("candidate_manifest_hash")
                == report.get("candidate_manifest_hash")
            ),
            "source_contract_pinned": source_contract_pinned,
            "execution_order_canonical": (
                report.get("execution_order") == sorted(snapshot_by_id)
            ),
            "candidate_payload_links_valid": candidate_payload_links_valid,
            "branch_semantic_digests_valid": branch_semantic_digests_valid,
            "record_provenance_valid": record_provenance_valid,
            "prediction_inputs_public_only": prediction_inputs_public_only,
            "replay_semantics_valid": replay_ok,
        }
        lineage_checks[task_lineage] = checks
        descriptors.append(
            {
                key: item.get(key)
                for key in (
                    "task_lineage",
                    "source_lineage",
                    "parent_lineage",
                    "public_task_hash",
                    "initial_public_state_hash",
                    "management_initial_state_hash",
                    "candidate_set_hash",
                    "candidate_manifest_hash",
                    "body_spec_hash",
                    "motor_profile_hash",
                    "adapter_version",
                    "runtime_version",
                    "evaluator_version",
                )
            }
        )

    expected_semantic_hash = _sha256_json(
        _semantic_projection(
            {
                key: copy.deepcopy(value)
                for key, value in bundle.items()
                if key != "semantic_bundle_hash"
            }
        )
    )
    recomputed_manifest_hash = _lineage_manifest_hash(descriptors)
    global_checks = {
        "benchmark_pinned": bundle.get("benchmark") == PILOT_BENCHMARK,
        "exact_lineage_count": len(lineages) == EXPECTED_LINEAGES,
        "unique_lineage_count": len(unique_lineages) == EXPECTED_LINEAGES,
        "unique_source_lineage_count": (
            len(unique_source_lineages) == EXPECTED_LINEAGES
        ),
        "exact_branch_count": total_branches
        == EXPECTED_LINEAGES * EXPECTED_CANDIDATES_PER_LINEAGE,
        "lineage_manifest_hash_matches": (
            bundle.get("lineage_manifest_hash") == recomputed_manifest_hash
        ),
        "semantic_bundle_hash_matches": (
            bundle.get("semantic_bundle_hash") == expected_semantic_hash
        ),
        "all_lineage_checks_pass": all(
            all(checks.values()) for checks in lineage_checks.values()
        ),
    }
    return {
        "format": PILOT_AUDIT_FORMAT,
        "benchmark": bundle.get("benchmark"),
        "source": copy.deepcopy(dict(source)),
        "independent_lineages": len(unique_lineages),
        "independent_source_lineages": len(unique_source_lineages),
        "candidate_executions": total_branches,
        "missing_branches": missing_branches,
        "replay_failures": replay_failures,
        "total_branch_research_cost": raw_cost,
        "lineage_checks": lineage_checks,
        "checks": global_checks,
        "semantic_bundle_hash": expected_semantic_hash,
        "passed": all(global_checks.values()),
    }


def write_pilot_bundle(bundle: Mapping[str, Any], output: Path) -> Path:
    """Write the raw evaluator-private pilot bundle without dropping measured costs."""

    audit = verify_pilot_bundle(bundle)
    if not audit["passed"]:
        raise PilotBundleError("refusing to write a pilot bundle that fails independent audit")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(
            bundle,
            stream,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        stream.write("\n")
    return output
