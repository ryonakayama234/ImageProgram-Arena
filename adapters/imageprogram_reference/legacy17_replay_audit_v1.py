"""Replay the frozen coordinate-path baseline without inventing v0 evidence.

This is a separate legacy contract, not a conversion to the edge-ID grader.
No model, task generator, original scorer, or confirmation imports are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "arena-legacy-coordinate-replay-audit-v1"
ANCHORS = {
    "public": "5497ad7e31e9d1528a01b881f92da0655de81d1d24da40f783cfc05b6f95b374",
    "private": "476cb257de6f19f9248771ca5953e4510902d9913a75bacf91110d0f0a1517ba",
    "prediction": "f01a79ba93e9634c9d096c9cd2886b9c7498d2e1a5f44cdd7e2a5d7ba5240813",
}
TOLERANCE_PX = 0.75
MAX_STEP_PX = 1.415


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(label + "-contract")


def points(value):
    if not isinstance(value, list) or any(
        not isinstance(p, list) or len(p) != 2 or any(
            type(x) not in {int, float} or not math.isfinite(x) for x in p) for p in value
    ):
        raise ValueError("invalid-coordinate-path")
    return value


def adapt(public, private, prediction, anchors):
    """Bind original records by public-input digest, never by list position."""
    if set(anchors) != set(ANCHORS) or any(
        digest(value) != anchors[name] for name, value in (
            ("public", public), ("private", private), ("prediction", prediction))
    ):
        raise ValueError("unanchored-source")
    if not isinstance(public, list) or not public or not isinstance(private, list):
        raise ValueError("missing-source-cases")
    keys(prediction, {"protocol", "public_sha256", "rows", "original_confirmation",
                      "training_updates"}, "prediction")
    if (prediction["protocol"] != "visible-path-baseline-predictions-v0"
            or prediction["public_sha256"] != anchors["public"]
            or prediction["original_confirmation"] != "NOT_RUN"
            or prediction["training_updates"] != 0):
        raise ValueError("prediction-provenance")

    def index(records, label, key):
        if not isinstance(records, list):
            raise ValueError(label + "-not-list")
        result = {}
        for row in records:
            if not isinstance(row, dict):
                raise ValueError(label + "-not-object")
            identity = key(row)
            if not isinstance(identity, str) or not identity or identity in result:
                raise ValueError(label + "-duplicate-or-missing-id")
            result[identity] = row
        return result

    pubs = index(public, "public", digest)
    truths = index(private, "private", lambda r: r.get("public_sha256"))
    preds = index(prediction["rows"], "prediction", lambda r: r.get("public_sha256"))
    if pubs.keys() != truths.keys() or pubs.keys() != preds.keys():
        raise ValueError("missing-or-extra-case")
    if len({r.get("case_id") for r in private}) != len(private):
        raise ValueError("duplicate-case-id")
    normalized = []
    for sha, wire in pubs.items():
        keys(wire, {"anchor_px", "focus_box", "max_candidates", "pixels_l8"}, "public")
        truth, saved = truths[sha], preds[sha]
        keys(truth, {"case_id", "family", "group", "protocol", "public_sha256", "split",
                     "target_xy", "excluded_xy", "expected_goal"}, "private")
        keys(saved, {"public_sha256", "prediction", "seconds"}, "saved-row")
        pred = saved["prediction"]
        keys(pred, {"adapter", "anchored", "cc01", "cc01_full_path", "goal_status", "graph",
                    "ordered_path", "partial", "termination_reason"}, "decision")
        if (truth["protocol"] != "arena-visible-path-dev-v0"
                or truth["split"] != "development" or truth["group"] not in {"unique", "control"}
                or truth["expected_goal"] not in {"satisfied", "unknown"}
                or pred["adapter"] != "contour-path-baseline-adapter-v0"
                or pred["goal_status"] not in {"satisfied", "unknown"}
                or pred["cc01_full_path"] != "NOT_SUPPORTED"
                or not isinstance(truth["case_id"], str) or not truth["case_id"]
                or not isinstance(truth["family"], str) or not truth["family"]
                or not isinstance(pred["termination_reason"], str)
                or type(saved["seconds"]) not in {int, float}
                or not math.isfinite(saved["seconds"]) or saved["seconds"] < 0):
            raise ValueError("legacy-row-provenance")
        target = points(truth["target_xy"])
        if truth["group"] == "unique" and not target:
            raise ValueError("unique-missing-target")
        normalized.append({"case_id": truth["case_id"], "family": truth["family"],
                           "group": truth["group"], "source_public_sha256": sha,
                           "anchor_px": wire["anchor_px"], "target_xy": target,
                           "excluded_xy": points(truth["excluded_xy"]),
                           "expected_goal": truth["expected_goal"],
                           "path": points(pred["ordered_path"]),
                           "goal_status": pred["goal_status"],
                           "termination_reason": pred["termination_reason"],
                           "seconds": saved["seconds"]})
    return {"protocol": VERSION, "source_canonical_sha256": dict(anchors),
            "cases": normalized,
            "missing_evidence": ["full_candidate_paths", "observation_bound_endpoint_evidence",
                                 "selected_path_to_graph_mapping", "predictor_source_commit"]}


def geometry(path, target, excluded):
    """Independent scalar implementation of the predeclared thin-pixel grammar."""
    points(path)
    points(target)
    points(excluded)
    has = bool(path and target)
    distances = [[math.dist(t, p) for t in target] for p in path] if has else []
    coverage = sum(min(row[j] for row in distances) <= TOLERANCE_PX
                   for j in range(len(target))) / len(target) if has else 0.0
    precision = sum(min(row) <= TOLERANCE_PX for row in distances) / len(path) if has else 0.0
    endpoints = bool(has and math.dist(path[0], target[0]) <= TOLERANCE_PX
                     and math.dist(path[-1], target[-1]) <= TOLERANCE_PX)
    continuous = len(path) >= 2 and all(
        math.dist(a, b) <= MAX_STEP_PX for a, b in zip(path, path[1:]))
    nearest = [min(range(len(target)), key=lambda j: row[j]) for row in distances]
    ordered = bool(has and all(a <= b for a, b in zip(nearest, nearest[1:])))
    wrong_line = any(math.dist(p, e) <= TOLERANCE_PX for p in path for e in excluded)
    return {"coverage": coverage, "precision": precision, "endpoint_match": endpoints,
            "continuous": continuous, "ordered": ordered, "excluded_line_selected": wrong_line,
            "path_correct": bool(coverage == 1 and precision == 1 and endpoints
                                 and continuous and ordered and not wrong_line)}


def grade(normalized, expected_sha):
    if normalized.get("protocol") != VERSION or digest(normalized) != expected_sha:
        raise ValueError("unanchored-adapted-input")
    rows, counts, families = [], Counter(), defaultdict(list)
    for case in normalized["cases"]:
        metrics = geometry(case["path"], case["target_xy"], case["excluded_xy"])
        unique = case["group"] == "unique"
        claim = case["goal_status"] == "satisfied"
        goal_match = case["goal_status"] == case["expected_goal"]
        legacy_success = bool(unique and metrics["path_correct"] and claim)
        false_complete = bool(claim and (not goal_match or not metrics["path_correct"]))
        row = {k: case[k] for k in ("case_id", "family", "group", "source_public_sha256",
                                    "goal_status", "termination_reason", "seconds")}
        row.update(metrics, legacy_claim_success=legacy_success, goal_match=goal_match,
                   false_complete=false_complete, no_selected_path=not case["path"],
                   full_v0_success=None, candidate_available=None, false_join=None)
        rows.append(row)
        counts["cases"] += 1
        counts["unique" if unique else "controls"] += 1
        counts["false_complete"] += int(false_complete)
        counts["completion_claims"] += int(claim)
        if unique:
            families[case["family"]].append(legacy_success)
            counts["unique_path_correct"] += int(metrics["path_correct"])
            counts["unique_legacy_claim_success"] += int(legacy_success)
            counts["unique_no_selected_path"] += int(not case["path"])
            counts["unique_excluded_line_selected"] += int(metrics["excluded_line_selected"])
        else:
            counts["control_goal_match"] += int(goal_match)
    return {"protocol": VERSION, "stage": "grade", "split": "development",
            "source_canonical_sha256": normalized["source_canonical_sha256"],
            "adapted_sha256": digest(normalized), "results": rows, "counts": dict(counts),
            "unique_family_results": {k: {"cases": len(v), "all_pass": all(v)}
                                      for k, v in families.items()},
            "missing_evidence": normalized["missing_evidence"],
            "full_v0_gate": "NOT_EVALUABLE", "p_g_r_causal_attribution": "NOT_IDENTIFIABLE",
            "control_reason_acceptance": "NOT_SPECIFIED_IN_SOURCE_ORACLE",
            "model_was_reinvoked": False, "original_confirmation": "NOT_RUN",
            "qualification": "synthetic-development-legacy-claim-not-verified-completion"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ANCHORS:
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    raw = {name: getattr(args, name).read_bytes() for name in ANCHORS}
    sources = {name: json.loads(value.decode("utf-8")) for name, value in raw.items()}
    normalized = adapt(sources["public"], sources["private"], sources["prediction"], ANCHORS)
    report = grade(normalized, digest(normalized))
    report["source_byte_sha256"] = {
        name: hashlib.sha256(value).hexdigest() for name, value in raw.items()}
    report["evaluator_file_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(report["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
