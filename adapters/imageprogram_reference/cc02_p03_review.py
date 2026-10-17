"""P03 Arena-only independent full-path scorer.

Consumes saved public P03 receipts; never imports ImageProgram or generates candidates.
Frozen R2 grader is reused through a versioned *validation adapter*, not modified.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from adapters.imageprogram_reference import cc02_r2_candidate_review as r2

VERSION = "arena-cc02-p03-independent-review-v0"
MODEL_VERSION = "imageprogram-cc02-p03-faint-full-path-bank-v0"
WEAK_KEYS = {
    "candidate_id", "path_sha256", "ordered_xy", "start_xy", "end_xy",
    "endpoint_kinds", "support_vertices", "mean_observed_l8",
    "evidence_kind", "ownership",
}
MAX_WEAK_CANDIDATES = 4
MAX_VERTICES = 32768


def digest(value):
    return r2.digest(value)


def grade(public, private, prediction, public_sha, private_sha, prediction_sha):
    for obj, sha in ((public, public_sha), (private, private_sha),
                    (prediction, prediction_sha)):
        if digest(obj) != sha:
            raise ValueError("p03-external-sha-mismatch")
    r2.keys(public, {"protocol", "split", "cases"}, "p03-public")
    r2.keys(private, {"protocol", "public_sha256", "cases"}, "p03-private")
    r2.keys(prediction, {"protocol", "public_sha256", "cases"}, "p03-prediction")
    if (any(obj["protocol"] != VERSION for obj in (public, private, prediction))
            or public["split"] not in ("development", "confirmation")
            or private["public_sha256"] != public_sha
            or prediction["public_sha256"] != public_sha):
        raise ValueError("p03-protocol-or-parent-drift")
    pub = r2.index(public["cases"], "public")
    pri = r2.index(private["cases"], "private")
    pred = r2.index(prediction["cases"], "prediction")
    if not pub or pub.keys() != pri.keys() or pub.keys() != pred.keys():
        raise ValueError("p03-case-universe-drift")
    # R2's strict full-path identity, geometry, provenance and contract validator
    # has a frozen DEV-only API. Its ephemeral copy is *explicitly adapted*
    # for validation; the original input and its external SHA are unchanged.
    r2_public = {**public, "protocol": r2.VERSION, "split": "development"}
    r2_private = {"protocol": r2.VERSION, "public_sha256": digest(r2_public),
                  "cases": []}
    r2_prediction = {"protocol": r2.VERSION,
                     "public_sha256": digest(r2_public), "cases": []}
    supplemental = {}
    for case_id, task in pub.items():
        target, decision = pri[case_id], pred[case_id]
        r2.keys(target, {"case_id", "family_id", "kind", "accepted_paths_xy",
                         "excluded_paths_xy"}, "p03-private-task")
        r2.keys(decision, {"case_id", "public_task_sha256", "model_git_commit",
                           "observation"}, "p03-prediction-task")
        receipt = decision["observation"]
        if not isinstance(receipt, dict):
            raise ValueError("p03-missing-receipt")
        if receipt.get("protocol") != MODEL_VERSION:
            raise ValueError("p03-model-version-drift")
        if receipt.get("stage") != "public-weak-path-evidence":
            raise ValueError("p03-wrong-stage")
        if (receipt.get("private_target_used") is not False
                or receipt.get("endpoint_verified") is not False
                or receipt.get("goal_status") != "unknown"
                or receipt.get("weak_selected_candidate_id") is not None):
            raise ValueError("p03-private-leak-or-false-selection")
        if receipt.get("raster_sha256") != task["raster_sha256"]:
            raise ValueError("p03-raster-binding-drift")
        if digest({k: v for k, v in receipt.items()
                   if k != "canonical_sha256"}) != receipt.get("canonical_sha256"):
            raise ValueError("p03-receipt-hash-drift")
        if (not isinstance(receipt.get("weak_observer_source_sha256"), str)
                or len(receipt["weak_observer_source_sha256"]) != 64
                or receipt.get("weak_band_l8") != [145, 200]):
            raise ValueError("p03-source-or-band-contract")
        base = receipt.get("base_r2")
        if (not isinstance(base, dict)
                or base.get("canonical_sha256") != receipt.get("base_r2_sha256")
                or digest({k: v for k, v in base.items()
                           if k != "canonical_sha256"}) != receipt["base_r2_sha256"]):
            raise ValueError("p03-base-r2-sha-drift")
        weak = receipt.get("weak_paths")
        if not isinstance(weak, list) or len(weak) > MAX_WEAK_CANDIDATES:
            raise ValueError("p03-overbudget-weak-paths")
        state = receipt.get("weak_status")
        if (not isinstance(state, str)
                or ("budget-exceeded" in state and weak)):
            raise ValueError("p03-non-atomic-weak-budget")
        if (len(weak) + len(base.get("candidates", [])) > 128
                or sum(len(c.get("ordered_xy", [])) for c in weak)
                + base.get("diagnostic_work", {}).get("exported_path_vertices", 0)
                > MAX_VERTICES):
            raise ValueError("p03-total-work-budget")
        work = receipt.get("diagnostic_work", {})
        if (work.get("weak_candidate_count") != len(weak)
                or work.get("weak_path_vertices") != sum(
                    len(c.get("ordered_xy", [])) for c in weak)):
            raise ValueError("p03-weak-work-drift")
        paths = []
        seen = set()
        for candidate in weak:
            r2.keys(candidate, WEAK_KEYS, "p03-weak-candidate")
            path = r2.xy_path(candidate["ordered_xy"], "p03-weak")
            path_hash = digest(min(path, tuple(reversed(path))))
            if (candidate["candidate_id"] != "weak-path-" + path_hash[:20]
                    or candidate["path_sha256"] != path_hash
                    or tuple(candidate["start_xy"]) != path[0]
                    or tuple(candidate["end_xy"]) != path[-1]
                    or candidate["support_vertices"] != len(path)
                    or candidate["candidate_id"] in seen):
                raise ValueError("p03-weak-geometry-identity")
            if (candidate["ownership"] != "unknown"
                    or candidate["evidence_kind"] != "weak-only-ordered-path"):
                raise ValueError("p03-unearned-target-ownership")
            mean = candidate["mean_observed_l8"]
            if mean is not None and (type(mean) not in (int, float)
                                     or not 145 <= mean < 200):
                raise ValueError("p03-invalid-evidence-brightness")
            seen.add(candidate["candidate_id"])
            paths.append(path)
        supplemental[case_id] = paths
        # Strict base validation gets the same concrete observation, plus
        # only the VERSION/split envelope needed by frozen R2 grader.
        r2_private["cases"].append({k: v for k, v in target.items()
                                   if k != "excluded_paths_xy"})
        r2_prediction["cases"].append({**decision, "observation": base})
    frozen = r2.grade(r2_public, r2_private, r2_prediction,
                      digest(r2_public), digest(r2_private), digest(r2_prediction))
    base_rows = {item["case_id"]: item for item in frozen["rows"]}
    counts = Counter()
    rows = []
    for case_id, target in pri.items():
        old = base_rows[case_id]
        paths = supplemental[case_id]
        accepted = [r2.xy_path(path, "p03-private-target")
                    for path in target["accepted_paths_xy"]]
        excluded = [r2.xy_path(path, "p03-private-excluded")
                    for path in target["excluded_paths_xy"]]
        weak_match = any(r2.matches(p, t) for p in paths for t in accepted)
        excluded_matches = sum(any(r2.matches(p, e) for e in excluded)
                               for p in paths)
        old_available = old["candidate_available"]
        available = bool(old_available or weak_match) if old_available is not None else None
        counts["cases"] += 1
        counts["weak_candidates"] += len(paths)
        counts["excluded_exact_matches"] += excluded_matches
        if target["kind"] == "unique_path":
            counts["positive"] += 1
            counts["baseline_available"] += int(old_available)
            counts["p03_available"] += int(available)
            counts["newly_recovered"] += int(not old_available and weak_match)
        else:
            counts["controls"] += 1
            counts["control_weak_candidates"] += len(paths)
        rows.append({
            "case_id": case_id,
            "family_id": target["family_id"],
            "kind": target["kind"],
            "baseline_candidate_available": old_available,
            "p03_candidate_available": available,
            "newly_recovered": bool(target["kind"] == "unique_path"
                                    and not old_available and weak_match),
            "weak_candidate_count": len(paths),
            "excluded_exact_matches": excluded_matches,
            "weak_status": pred[case_id]["observation"]["weak_status"],
            "base_r2_sha256": pred[case_id]["observation"]["base_r2_sha256"],
        })
    counts["positive_lineages"] = len({p["family_id"] for p in pri.values()
                                       if p["kind"] == "unique_path"})
    return {"protocol": VERSION, "stage": "independent-weak-path-grade",
            "split": public["split"], "public_sha256": public_sha,
            "private_sha256": private_sha, "prediction_sha256": prediction_sha,
            "counts": dict(counts), "rows": rows,
            "model_was_reinvoked": False, "r2_validation_adapter_used": True,
            "completion": "NOT_EVALUABLE", "training": "NOT_RUN"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("public", "private", "prediction"):
        parser.add_argument("--" + key, type=Path, required=True)
        parser.add_argument("--" + key + "-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    sources = []
    for name in ("public", "private", "prediction"):
        data = json.loads(getattr(a, name).read_text(encoding="utf-8"))
        if digest(data) != getattr(a, name + "_sha256"):
            raise ValueError("p03-external-input-sha-mismatch")
        sources.append(data)
    result = grade(*sources, a.public_sha256, a.private_sha256, a.prediction_sha256)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, sort_keys=True,
                  allow_nan=False)
        f.write("\n")
    print(json.dumps(result["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
