"""Arena-side H5a same-checkpoint branch-isolation harness.

The harness owns experiment orchestration only. ImageProgram remains the source
of truth for ConstructionOutcomeRecordV0 and for the actual runtime/checkpoint
implementation. Callers inject restore/execute functions; Arena verifies that
every candidate starts from the same management-side state and that canonical
outcome records remain version/hash bound.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

REPORT_FORMAT = "imageprogram-arena-h5-branch-isolation-1"
AUDIT_FORMAT = "imageprogram-arena-h5-branch-isolation-audit-1"

FORBIDDEN_POLICY_KEYS = frozenset(
    {
        "hidden_witness",
        "known_continuation",
        "source_program",
        "witness_binding",
        "oracle_outcome",
        "oracle_candidate_outcome",
        "best_candidate",
        "best_candidate_id",
        "best_candidate_label",
        "private_checkpoint",
        "checkpoint_path",
    }
)
FORBIDDEN_POLICY_TEXT = ("private/", "private\\", ".npz")
REQUIRED_SPEC_FIELDS = (
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
    "policy_input",
)
REQUIRED_CONTRACT_REF_FIELDS = (
    "repository",
    "commit",
    "schema_version",
    "record_contract_version",
    "record_contract_hash",
    "outcome_contract_version",
    "outcome_contract_hash",
)
REQUIRED_CANDIDATE_FIELDS = (
    "candidate_id",
    "candidate_public_payload_hash",
    "public_payload",
)


class BranchIsolationError(ValueError):
    """The branch experiment violated an H5a isolation/provenance invariant."""


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
        raise BranchIsolationError(f"{name} must be a mapping")
    return value


def _require_fields(value: Mapping[str, Any], fields: Sequence[str], *, name: str) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        raise BranchIsolationError(f"{name} missing required fields: {missing}")


def _walk_public(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text.lower() in FORBIDDEN_POLICY_KEYS:
                joined = ".".join((*path, key_text))
                raise BranchIsolationError(f"policy input contains private/oracle key: {joined}")
            _walk_public(child, (*path, key_text))
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _walk_public(child, (*path, str(index)))
        return
    if isinstance(value, str):
        lowered = value.lower()
        for token in FORBIDDEN_POLICY_TEXT:
            if token in lowered:
                joined = ".".join(path) or "<root>"
                raise BranchIsolationError(
                    f"policy input contains management-private path/token at {joined}: {token}"
                )


def _validate_spec(spec: Mapping[str, Any]) -> None:
    _require_fields(spec, REQUIRED_SPEC_FIELDS, name="branch spec")
    contract_ref = _require_mapping(spec["contract_ref"], name="contract_ref")
    _require_fields(contract_ref, REQUIRED_CONTRACT_REF_FIELDS, name="contract_ref")
    _walk_public(spec["policy_input"])


def _validate_candidates(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    if not candidates:
        raise BranchIsolationError("candidate set must not be empty")
    by_id: dict[str, Mapping[str, Any]] = {}
    for index, candidate in enumerate(candidates):
        candidate = _require_mapping(candidate, name=f"candidate[{index}]")
        _require_fields(candidate, REQUIRED_CANDIDATE_FIELDS, name=f"candidate[{index}]")
        candidate_id = candidate["candidate_id"]
        if not isinstance(candidate_id, str) or not candidate_id:
            raise BranchIsolationError("candidate_id must be a non-empty string")
        if candidate_id in by_id:
            raise BranchIsolationError(f"duplicate candidate_id: {candidate_id}")
        _walk_public(candidate["public_payload"], (f"candidate[{candidate_id}]", "public_payload"))
        by_id[candidate_id] = candidate
    return by_id


def candidate_manifest_hash(candidates: Sequence[Mapping[str, Any]]) -> str:
    """Arena-local identity for the declared candidate list, not the canonical set hash."""

    by_id = _validate_candidates(candidates)
    descriptor = [
        {
            "candidate_id": candidate_id,
            "candidate_public_payload_hash": by_id[candidate_id][
                "candidate_public_payload_hash"
            ],
        }
        for candidate_id in sorted(by_id)
    ]
    return _sha256_json(descriptor)


def _validate_outcome_record(
    record: Mapping[str, Any],
    *,
    spec: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> None:
    record = _require_mapping(record, name="outcome_record")
    required = (
        "schema_version",
        "kind",
        "record_contract_version",
        "record_contract_hash",
        "outcome_contract_version",
        "outcome_contract_hash",
        "record_id",
        "task_lineage",
        "parent_lineage",
        "public_task_hash",
        "initial_public_state_hash",
        "candidate_set_hash",
        "candidate_id",
        "candidate_public_payload_hash",
        "body_spec_hash",
        "motor_profile_hash",
        "adapter_version",
        "runtime_version",
        "evaluator_version",
        "prediction_input",
        "record_status",
        "outcome",
        "replay_status",
        "branch_research_cost",
        "missing_reason_code",
    )
    _require_fields(record, required, name="outcome_record")
    if record["kind"] != "construction_outcome_record":
        raise BranchIsolationError("branch result is not a Construction outcome record")

    contract_ref = spec["contract_ref"]
    equality_checks = {
        "schema_version": contract_ref["schema_version"],
        "record_contract_version": contract_ref["record_contract_version"],
        "record_contract_hash": contract_ref["record_contract_hash"],
        "outcome_contract_version": contract_ref["outcome_contract_version"],
        "outcome_contract_hash": contract_ref["outcome_contract_hash"],
        "task_lineage": spec["task_lineage"],
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
    }
    for field, expected in equality_checks.items():
        if record[field] != expected:
            raise BranchIsolationError(
                f"outcome_record {field} mismatch: expected {expected!r}, got {record[field]!r}"
            )

    prediction_input = _require_mapping(record["prediction_input"], name="prediction_input")
    if prediction_input.get("public_only") is not True:
        raise BranchIsolationError("prediction_input must remain public_only=true")
    _walk_public(prediction_input, ("prediction_input",))

    record_status = record["record_status"]
    if record_status == "observed":
        if not isinstance(record["outcome"], Mapping):
            raise BranchIsolationError("observed branch requires outcome")
        if record["missing_reason_code"] is not None:
            raise BranchIsolationError("observed branch cannot carry missing_reason_code")
    elif record_status == "missing":
        if record["outcome"] is not None:
            raise BranchIsolationError("missing branch cannot carry outcome")
        if not isinstance(record["missing_reason_code"], str) or not record["missing_reason_code"]:
            raise BranchIsolationError("missing branch requires missing_reason_code")
    else:
        raise BranchIsolationError(f"unsupported record_status: {record_status!r}")

    if not isinstance(record["branch_research_cost"], Mapping):
        raise BranchIsolationError("branch_research_cost must be preserved separately")


def _without_wall_time(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _without_wall_time(child)
            for key, child in value.items()
            if key != "wall_time_s"
        }
    if isinstance(value, list):
        return [_without_wall_time(child) for child in value]
    if isinstance(value, tuple):
        return tuple(_without_wall_time(child) for child in value)
    return value


def _semantic_digest(branch: Mapping[str, Any]) -> str:
    return _sha256_json(
        _without_wall_time(
            {
                "candidate_id": branch["candidate_id"],
                "initial_state_hash": branch["initial_state_hash"],
                "final_state_hash": branch["final_state_hash"],
                "outcome_record": {
                    key: value
                    for key, value in branch["outcome_record"].items()
                    if key != "record_id"
                },
                "policy_execution_cost": branch["policy_execution_cost"],
            }
        )
    )


def run_exhaustive_branches(
    *,
    spec: Mapping[str, Any],
    checkpoint: Any,
    candidates: Sequence[Mapping[str, Any]],
    restore_checkpoint: Callable[[Any], Any],
    restored_state_hash: Callable[[Any], str],
    execute_candidate: Callable[
        [Any, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]
    ],
    order: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Execute every fixed candidate from a fresh restore of the same checkpoint.

    execute_candidate must return initial_state_hash, final_state_hash,
    canonical outcome_record, and policy_execution_cost. Unexpected adapter
    exceptions are not converted into missing labels: an explicit canonical missing
    record must be returned when collection itself is missing.
    """

    spec = _require_mapping(spec, name="branch spec")
    _validate_spec(spec)
    by_id = _validate_candidates(candidates)
    candidate_ids = list(by_id)
    execution_order = list(order) if order is not None else list(candidate_ids)
    if len(execution_order) != len(candidate_ids) or set(execution_order) != set(candidate_ids):
        raise BranchIsolationError("execution order must contain each candidate exactly once")

    branches: list[dict[str, Any]] = []
    for candidate_id in execution_order:
        candidate = by_id[candidate_id]
        restored = restore_checkpoint(checkpoint)
        restored_hash = restored_state_hash(restored)
        if restored_hash != spec["management_initial_state_hash"]:
            raise BranchIsolationError(
                "restored management state differs from frozen checkpoint: "
                f"candidate={candidate_id} expected={spec['management_initial_state_hash']} "
                f"got={restored_hash}"
            )

        result = _require_mapping(
            execute_candidate(
                restored,
                copy.deepcopy(candidate),
                copy.deepcopy(spec["policy_input"]),
            ),
            name=f"branch result {candidate_id}",
        )
        _require_fields(
            result,
            (
                "initial_state_hash",
                "final_state_hash",
                "outcome_record",
                "policy_execution_cost",
            ),
            name=f"branch result {candidate_id}",
        )
        if result["initial_state_hash"] != restored_hash:
            raise BranchIsolationError(
                f"branch {candidate_id} did not execute from its restored checkpoint"
            )
        if not isinstance(result["final_state_hash"], str) or not result["final_state_hash"]:
            raise BranchIsolationError(f"branch {candidate_id} missing final_state_hash")
        if not isinstance(result["policy_execution_cost"], Mapping):
            raise BranchIsolationError(f"branch {candidate_id} missing policy_execution_cost")
        _validate_outcome_record(result["outcome_record"], spec=spec, candidate=candidate)

        branch = {
            "candidate_id": candidate_id,
            "initial_state_hash": result["initial_state_hash"],
            "final_state_hash": result["final_state_hash"],
            "policy_execution_cost": copy.deepcopy(result["policy_execution_cost"]),
            "outcome_record": copy.deepcopy(result["outcome_record"]),
        }
        branch["semantic_digest"] = _semantic_digest(branch)
        branches.append(branch)

    by_candidate = {branch["candidate_id"]: branch for branch in branches}
    checks = {
        "candidate_set_complete": set(by_candidate) == set(candidate_ids),
        "same_management_initial_state": all(
            branch["initial_state_hash"] == spec["management_initial_state_hash"]
            for branch in branches
        ),
        "contract_version_hash_pinned": True,
        "policy_private_data_access_prevented": True,
        "research_and_policy_cost_channels_separate": all(
            isinstance(branch["policy_execution_cost"], Mapping)
            and isinstance(branch["outcome_record"]["branch_research_cost"], Mapping)
            for branch in branches
        ),
    }
    return {
        "format": REPORT_FORMAT,
        "task_lineage": spec["task_lineage"],
        "contract_ref": copy.deepcopy(spec["contract_ref"]),
        "candidate_set_hash": spec["candidate_set_hash"],
        "candidate_manifest_hash": candidate_manifest_hash(candidates),
        "management_initial_state_hash": spec["management_initial_state_hash"],
        "execution_order": execution_order,
        "branches": [by_candidate[candidate_id] for candidate_id in sorted(by_candidate)],
        "checks": checks,
        "passed": all(checks.values()),
    }


def _all_pairwise_orders_reversed(forward: Sequence[str], reverse: Sequence[str]) -> bool:
    if len(forward) != len(reverse) or set(forward) != set(reverse):
        return False
    fpos = {candidate_id: index for index, candidate_id in enumerate(forward)}
    rpos = {candidate_id: index for index, candidate_id in enumerate(reverse)}
    ids = list(forward)
    return all(
        (fpos[ids[i]] < fpos[ids[j]]) != (rpos[ids[i]] < rpos[ids[j]])
        for i in range(len(ids))
        for j in range(i + 1, len(ids))
    )


def audit_order_invariance(
    *,
    spec: Mapping[str, Any],
    checkpoint: Any,
    candidates: Sequence[Mapping[str, Any]],
    restore_checkpoint: Callable[[Any], Any],
    restored_state_hash: Callable[[Any], str],
    execute_candidate: Callable[
        [Any, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]
    ],
) -> dict[str, Any]:
    """Run forward and reverse orders and require per-candidate semantic identity."""

    by_id = _validate_candidates(candidates)
    forward_order = list(by_id)
    reverse_order = list(reversed(forward_order))
    forward = run_exhaustive_branches(
        spec=spec,
        checkpoint=checkpoint,
        candidates=candidates,
        restore_checkpoint=restore_checkpoint,
        restored_state_hash=restored_state_hash,
        execute_candidate=execute_candidate,
        order=forward_order,
    )
    reverse = run_exhaustive_branches(
        spec=spec,
        checkpoint=checkpoint,
        candidates=candidates,
        restore_checkpoint=restore_checkpoint,
        restored_state_hash=restored_state_hash,
        execute_candidate=execute_candidate,
        order=reverse_order,
    )
    forward_by_id = {item["candidate_id"]: item for item in forward["branches"]}
    reverse_by_id = {item["candidate_id"]: item for item in reverse["branches"]}
    candidate_checks = {
        candidate_id: (
            forward_by_id[candidate_id]["semantic_digest"]
            == reverse_by_id[candidate_id]["semantic_digest"]
        )
        for candidate_id in sorted(by_id)
    }
    checks = {
        "forward_passed": forward["passed"],
        "reverse_passed": reverse["passed"],
        "all_pairwise_relative_orders_reversed": _all_pairwise_orders_reversed(
            forward_order, reverse_order
        ),
        "candidate_repeat_deterministic": all(candidate_checks.values()),
    }
    return {
        "format": AUDIT_FORMAT,
        "task_lineage": spec["task_lineage"],
        "forward_order": forward_order,
        "reverse_order": reverse_order,
        "verification_executions": 2 * len(by_id),
        "candidate_checks": candidate_checks,
        "checks": checks,
        "forward": forward,
        "reverse": reverse,
        "passed": all(checks.values()),
    }


def deterministic_audit_projection(audit: Mapping[str, Any]) -> dict[str, Any]:
    """Drop measured wall-time fields while retaining every semantic isolation result."""

    return _without_wall_time(copy.deepcopy(dict(audit)))


def write_deterministic_audit(audit: Mapping[str, Any], output: Path) -> Path:
    """Write a stable JSON audit; raw measured records remain caller-owned for #9."""

    output = Path(output)
    projection = deterministic_audit_projection(audit)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(
            projection,
            stream,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        stream.write("\n")
    return output
