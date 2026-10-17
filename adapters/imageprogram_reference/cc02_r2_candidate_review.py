"""Arena-only CC-02-R2 scorer: complete public candidate paths vs private geometry.

Never import ImageProgram or call any observer/selector from this module.
Only synthetic development geometry with independently specified visible paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

VERSION = "arena-cc02-r2-full-candidate-review-v0"
MODEL_VERSION = "imageprogram-cc02-r2-partial-candidate-bank-v0"


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def keys(obj, expected, name):
    if not isinstance(obj, dict) or set(obj) != set(expected):
        raise ValueError(name + "-contract")


def xy_path(raw, name):
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError(name + "-too-short")
    output = []
    for xy in raw:
        if (not isinstance(xy, list) or len(xy) != 2
                or any(type(x) not in (float, int) or not math.isfinite(x) for x in xy)):
            raise ValueError(name + "-not-finite-xy")
        output.append((float(xy[0]), float(xy[1])))
    for a, b in zip(output, output[1:]):
        if not 0 < math.dist(a, b) <= math.sqrt(2) + 1e-6:
            raise ValueError(name + "-gap-or-duplicate")
    return tuple(output)


def matches(path, target, tolerance=0.76):
    """Bidirectional pixel-centre coverage and endpoints: no target-only cheating."""
    endpoints = (math.dist(path[0], target[0]) <= tolerance
                 and math.dist(path[-1], target[-1]) <= tolerance)
    backwards = (math.dist(path[0], target[-1]) <= tolerance
                 and math.dist(path[-1], target[0]) <= tolerance)
    if not (endpoints or backwards):
        return False
    return (all(min(math.dist(p, q) for q in path) <= tolerance for p in target)
            and all(min(math.dist(p, q) for q in target) <= tolerance for p in path))


def index(rows, name):
    if not isinstance(rows, list):
        raise ValueError(name + "-not-list")
    if any(not isinstance(row, dict) or not isinstance(row.get("case_id"), str)
           or not row["case_id"] for row in rows):
        raise ValueError(name + "-invalid-ids")
    result = {row["case_id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(name + "-duplicate-cases")
    return result


def grade(public, private, prediction, public_sha, private_sha, prediction_sha):
    if any(digest(obj) != sha for obj, sha in ((public, public_sha),
                                              (private, private_sha),
                                              (prediction, prediction_sha))):
        raise ValueError("input-canonical-sha-drift")
    keys(public, {"protocol", "split", "cases"}, "public")
    keys(private, {"protocol", "public_sha256", "cases"}, "private")
    keys(prediction, {"protocol", "public_sha256", "cases"}, "prediction")
    if (public["protocol"] != VERSION or private["protocol"] != VERSION
            or prediction["protocol"] != VERSION
            or private["public_sha256"] != public_sha
            or prediction["public_sha256"] != public_sha
            or public["split"] != "development"):
        raise ValueError("version-parent-or-split-drift")
    pub, pri, pred = index(public["cases"], "public"), index(private["cases"], "private"), index(
        prediction["cases"], "prediction")
    if not pub or pub.keys() != pri.keys() or pub.keys() != pred.keys():
        raise ValueError("case-universe-drift")
    rows = []
    for case_id, task in pub.items():
        keys(task, {"case_id", "raster_sha256", "public_task_sha256"}, "public-task")
        target, decision = pri[case_id], pred[case_id]
        keys(target, {"case_id", "family_id", "kind", "accepted_paths_xy"}, "private-task")
        keys(decision, {"case_id", "public_task_sha256", "model_git_commit",
                        "observation"}, "prediction-task")
        if (decision["public_task_sha256"] != task["public_task_sha256"]
                or not isinstance(decision["model_git_commit"], str)
                or len(decision["model_git_commit"]) != 40
                or not all(v in "0123456789abcdef" for v in decision["model_git_commit"])):
            raise ValueError("prediction-source-or-input-drift")
        obs = decision["observation"]
        if not isinstance(obs, dict):
            raise ValueError("missing-observation")
        if (obs.get("protocol") != MODEL_VERSION
                or obs.get("raster_sha256") != task["raster_sha256"]):
            raise ValueError("model-observation-binding-mismatch")
        existing_digest = obs.get("canonical_sha256")
        if (not isinstance(existing_digest, str)
                or digest({k: v for k, v in obs.items() if k != "canonical_sha256"})
                != existing_digest):
            raise ValueError("candidate-bank-hash-mismatch")
        candidates = obs.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("missing-full-candidates")
        declared_count = obs.get("diagnostic_work", {}).get("candidate_count")
        if declared_count != len(candidates):
            raise ValueError("candidate-count-drift")
        candidate_paths = {}
        for candidate in candidates:
            keys(candidate, {"candidate_id", "source_candidate_id", "path_sha256",
                             "ordered_xy", "start_xy", "end_xy", "endpoint_kinds",
                             "length_px", "support_vertices"}, "candidate")
            path = xy_path(candidate["ordered_xy"], "observed-candidate")
            pid = digest(min(path, tuple(reversed(path))))
            if (candidate["candidate_id"] != "path-" + pid[:20]
                    or candidate["path_sha256"] != pid
                    or candidate["support_vertices"] != len(path)
                    or tuple(candidate["start_xy"]) != path[0]
                    or tuple(candidate["end_xy"]) != path[-1]
                    or candidate["candidate_id"] in candidate_paths):
                raise ValueError("candidate-identity-or-path-drift")
            candidate_paths[candidate["candidate_id"]] = path
        selected = obs.get("legacy_selected_candidate_id")
        if selected is not None and selected not in candidate_paths:
            raise ValueError("legacy-selection-not-in-bank")
        if (obs.get("status") == "observed") != (selected is not None):
            raise ValueError("status-selection-drift")
        if obs.get("endpoint_verified") is not False or obs.get("goal_status") != "unknown":
            raise ValueError("unearned-completion-claim")
        accepted = target["accepted_paths_xy"]
        if target["kind"] == "unique_path":
            if not isinstance(accepted, list) or not accepted:
                raise ValueError("missing-positive-target")
            true_paths = [xy_path(p, "private-target") for p in accepted]
            matches_by_id = {cid: any(matches(path, truth) for truth in true_paths)
                             for cid, path in candidate_paths.items()}
            available = any(matches_by_id.values())
            selected_correct = bool(selected and matches_by_id[selected])
            wrong_selection = bool(selected and not selected_correct)
        elif target["kind"] in ("ambiguous", "observation_insufficient"):
            if accepted != []:
                raise ValueError("private-control-has-target")
            available = selected_correct = wrong_selection = None
        else:
            raise ValueError("unsupported-private-kind")
        rows.append({
            "case_id": case_id, "family_id": target["family_id"], "kind": target["kind"],
            "raster_sha256": task["raster_sha256"],
            "candidate_bank_sha256": existing_digest,
            "status": obs["status"], "candidate_count": len(candidates),
            "candidate_available": available, "legacy_selected_correct": selected_correct,
            "legacy_wrong_selected_candidate": wrong_selection,
            "endpoint_verified": False,
            "reason": obs["reason"],
        })
    counts = Counter()
    for row in rows:
        counts["cases"] += 1
        if row["kind"] == "unique_path":
            counts["unique"] += 1
            counts["candidate_available"] += int(row["candidate_available"])
            counts["legacy_selected_correct"] += int(row["legacy_selected_correct"])
            counts["legacy_wrong_selected_candidate"] += int(row["legacy_wrong_selected_candidate"])
            counts["legacy_hold"] += int(row["status"] != "observed")
        else:
            counts["controls"] += 1
        if row["status"] == "budget_exceeded":
            counts["budget_exceeded"] += 1
    counts["source_families"] = len({row["family_id"] for row in rows
                                    if row["kind"] == "unique_path"})
    return {"protocol": VERSION, "stage": "grade-candidate-availability",
            "public_sha256": public_sha, "private_sha256": private_sha,
            "prediction_sha256": prediction_sha, "counts": dict(counts),
            "rows": rows, "model_was_reinvoked": False,
            "full_visible_endpoint_completion": "NOT_EVALUABLE",
            "historical_17_baseline": "UNCHANGED_NOT_SCORED_HERE"}


def load(path, expected):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if digest(data) != expected:
        raise ValueError("external-input-sha-mismatch")
    return data


def main():
    p = argparse.ArgumentParser()
    for name in ("public", "private", "prediction"):
        p.add_argument("--" + name, type=Path, required=True)
        p.add_argument("--" + name + "-sha256", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = grade(
        load(args.public, args.public_sha256),
        load(args.private, args.private_sha256),
        load(args.prediction, args.prediction_sha256),
        args.public_sha256, args.private_sha256, args.prediction_sha256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as out:
        json.dump(result, out, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        out.write("\n")
    print(json.dumps(result["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
