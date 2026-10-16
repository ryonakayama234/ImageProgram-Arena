"""Independent source-stroke scorer; no model/perception/relation implementation.

Only exact support on one known procedural source stroke gets a binary label.
No inference from predicted edges, target-region proxies, tangent thresholds or
selected paths. Unknown source identity remains unscored. Not a blind annotator.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from itertools import combinations
from pathlib import Path

from adapters.imageprogram_reference.contour_relation_g1_observed import (
    VERSION,
    checked,
    digest,
)

LABEL_VERSION = "source-stroke-membership-v1"


def source_pixels(a, b):
    # Independently implemented from the documented source rasterization contract.
    n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    return {(round(a[0] + i * (b[0] - a[0]) / max(n, 1)),
             round(a[1] + i * (b[1] - a[1]) / max(n, 1))) for i in range(n + 1)}


def validate_observation(observation):
    if (observation.get("protocol") != VERSION or observation.get("stage") != "observe"
            or observation.get("original_confirmation") != "NOT_RUN"
            or [r["task_id"] for r in observation["rows"]] != [f"obs-{i:02d}" for i in range(27)]):
        raise ValueError("invalid-observation-manifest")
    for row in observation["rows"]:
        if digest(row["fragments"]) != row["fragment_sha256"]:
            raise ValueError("observation-fragment-drift")
        if len(row["fragments"]) != len(row["p02_arms"]):
            raise ValueError("arm-fragment-count-mismatch")
        for index, (node, arm) in enumerate(zip(row["fragments"], row["p02_arms"])):
            support = set(map(tuple, arm["support_xy"]))
            if (node["node_id"] != f"n{index:03d}" or node["pixels"] != len(support)
                    or not support or len(support) != len(arm["support_xy"])
                    or any(node[k] != arm[k] for k in (
                        "endpoint_a", "endpoint_b", "tangent", "mean_l8", "region"))):
                raise ValueError("non-identity-arm-adapter")


def label(observation, observation_sha):
    checked(observation, observation_sha)
    validate_observation(observation)
    # Source definitions are the pre-existing input program, not model answers.
    from adapters.imageprogram_reference.branch_contour_p02_trial import CASES

    rows = []
    for row in observation["rows"]:
        owners = {}
        if row["family"] == "technical":
            name, strokes = next((name, strokes) for name, strokes in CASES
                                 if row["case_id"].startswith(name + ":"))
            masks = [source_pixels(a, b) for a, b in strokes]
            raster = bytearray([255] * (72 * 72))
            for mask in masks:
                for x, y in mask:
                    raster[y * 72 + x] = 0
            if hashlib.sha256(raster).hexdigest() != row["raster_sha256"]:
                raise ValueError("independent-source-raster-mismatch:" + name)
            for node, arm in zip(row["fragments"], row["p02_arms"]):
                support = set(map(tuple, arm["support_xy"]))
                if not support <= set().union(*masks):
                    raise ValueError("unobserved-arm-support")
                matches = [i for i, mask in enumerate(masks) if support <= mask]
                owners[node["node_id"]] = matches[0] if len(matches) == 1 else None
        # Older DEV/control files provide region/action proxies, not full arc identity.
        # Never turn those proxies into allegedly independent binary relation labels.
        pairs = []
        for a, b in combinations(row["fragments"], 2):
            x, y = owners.get(a["node_id"]), owners.get(b["node_id"])
            truth = "unknown" if x is None or y is None else (
                "positive" if x == y else "negative")
            pairs.append({"src": a["node_id"], "dst": b["node_id"], "truth": truth,
                          "reason": "same-source-stroke" if truth == "positive" else (
                              "different-source-strokes" if truth == "negative" else
                              "source-arc-identity-unavailable-or-mixed")})
        rows.append({"task_id": row["task_id"], "fragment_sha256": row["fragment_sha256"],
                     "source_owners": owners, "pairs": pairs})
    return {"protocol": VERSION, "stage": "label", "label_version": LABEL_VERSION,
            "observation_sha256": observation_sha, "rows": rows,
            "annotation": "source-program-exact-support-not-blind-artwork",
            "grader_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "original_confirmation": "NOT_RUN"}


def pair_kinds(edges, node_ids, *, newer):
    result = {}
    allowed = {"possible_continuation", "adjacent_distinct"}
    if newer:
        allowed.add("ambiguous_relation")
    for edge in edges:
        key = (edge["src"], edge["dst"])
        if (key[0] not in node_ids or key[1] not in node_ids or key[0] >= key[1]
                or key in result or edge["kind"] not in allowed):
            raise ValueError("invalid-predicted-pair")
        result[key] = edge["kind"]
    return result


def score(truth, kind):
    if truth == "unknown":
        return "unknown_possible" if kind == "possible_continuation" else "unknown_other"
    if kind in ("ambiguous_relation", "budget-abstention"):
        return "abstain_" + truth
    positive = kind == "possible_continuation"
    return ("TP" if positive else "FN") if truth == "positive" else (
        "FP" if positive else "TN")


def grade(observation, observation_sha, labels, label_sha, prediction, prediction_sha):
    checked(observation, observation_sha)
    checked(labels, label_sha)
    checked(prediction, prediction_sha)
    validate_observation(observation)
    # Reproduce deterministic source labels, never recompute model outputs.
    if label(observation, observation_sha) != labels:
        raise ValueError("frozen-private-label-drift")
    if (prediction.get("protocol") != VERSION or prediction.get("stage") != "predict"
            or prediction.get("source") != observation["source"]
            or prediction.get("observation_sha256") != observation_sha
            or prediction.get("original_confirmation") != "NOT_RUN"
            or prediction.get("selected_path") != "NOT_RUN"
            or prediction.get("budgets") != {"max_gap": 8, "max_pairs": 128,
                                               "max_relations": 128}
            or len(prediction["rows"]) != len(observation["rows"])):
        raise ValueError("prediction-manifest-drift")
    totals = {"g0": Counter(), "g1": Counter()}
    reviews = []
    for observed, labelled, predicted in zip(observation["rows"], labels["rows"],
                                            prediction["rows"]):
        if (predicted["task_id"] != observed["task_id"]
                or predicted["fragment_sha256"] != observed["fragment_sha256"]
                or predicted["g1_status"] not in (
                    "ok", "pair-budget-exceeded", "relation-budget-exceeded")):
            raise ValueError("prediction-fragment-or-status-drift")
        ids = {n["node_id"] for n in observed["fragments"]}
        kinds = {g: pair_kinds(predicted[g], ids, newer=g == "g1") for g in ("g0", "g1")}
        if predicted["g1_status"] != "ok" and predicted["g1"]:
            raise ValueError("partial-budget-bank")
        scores = {"g0": Counter(), "g1": Counter()}
        pairs = []
        for pair in labelled["pairs"]:
            key = pair["src"], pair["dst"]
            detail = dict(pair)
            for g in ("g0", "g1"):
                kind = "budget-abstention" if g == "g1" and predicted["g1_status"] != (
                    "ok") else kinds[g].get(key, "absent")
                outcome = score(pair["truth"], kind)
                scores[g][outcome] += 1
                totals[g][outcome] += 1
                detail[g] = kind
                detail[g + "_score"] = outcome
            pairs.append(detail)
        reviews.append({"task_id": observed["task_id"], "family": observed["family"],
                        "case_id": observed["case_id"], "p02_status": observed["p02_status"],
                        "nodes": len(ids), "pairs": pairs,
                        "counts": {g: dict(v) for g, v in scores.items()}})
    return {"protocol": VERSION, "stage": "grade", "prediction_sha256": prediction_sha,
            "observation_sha256": observation_sha, "labels_sha256": label_sha,
            "counts": {g: dict(v) for g, v in totals.items()}, "reviews": reviews,
            "scenes": len(reviews), "empty_observations": sum(not r["nodes"] for r in reviews),
            "p02_status_counts": dict(Counter(r["p02_status"] for r in reviews)),
            "annotation": labels["annotation"], "original_confirmation": "NOT_RUN",
            "independent_blind_annotation": "NOT_RUN", "selected_path": "NOT_RUN"}
