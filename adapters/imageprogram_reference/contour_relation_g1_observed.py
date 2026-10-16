"""Freeze actual P02 observations, then compare G0/G1 without private labels.

Stages are separate processes: observe -> label -> predict -> external anchor
-> grade. The source atlas is synthetic DEV evidence, never blind artwork truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

VERSION = "arena-g1-observed-p02-v1"
ARENA_ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked(value, expected):
    if len(expected) != 64 or digest(value) != expected:
        raise ValueError("unanchored-or-altered-artifact")
    return value


def source_identity():
    import imageprogram
    from imageprogram.models import branch_contour_p02, contextual_contour_cc01, contour_relation_g1

    model = Path(imageprogram.__file__).resolve().parents[2]
    heads = {}
    for label, root in (("model", model), ("arena", ARENA_ROOT)):
        if subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"],
                                   text=True).strip():
            raise ValueError("dirty-source-checkout")
        heads[label] = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    return {"heads": heads, "p02": file_digest(branch_contour_p02.__file__),
            "g0": file_digest(contextual_contour_cc01.__file__),
            "g1": file_digest(contour_relation_g1.__file__),
            "adapter": file_digest(__file__)}


def observe():
    from imageprogram.models.branch_contour_p02 import observe_branch
    from imageprogram.models.contextual_contour_cc01 import Fragment, observe_graph

    from adapters.imageprogram_reference.branch_contour_p02_trial import _public_cases

    rows = []
    for index, (family, case, public) in enumerate(_public_cases()):
        raster, focus = public["pixels_l8"], public["focus_box"]
        start = time.perf_counter()
        observed = observe_branch(raster, focus)
        elapsed = time.perf_counter() - start
        if observed.strong_graph != observe_graph(raster, focus):
            raise ValueError("frozen-p0-drift")
        # One-to-one field adaptation only. No endpoints, tangents or pixels are invented.
        nodes = tuple(Fragment(f"n{j:03d}", arm.endpoint_a, arm.endpoint_b, arm.tangent,
                               len(arm.support_xy), arm.mean_l8, arm.region)
                      for j, arm in enumerate(observed.arm_candidates))
        fragments = [asdict(n) for n in nodes]
        rows.append({"task_id": f"obs-{index:02d}", "family": family, "case_id": case,
                     "raster_sha256": hashlib.sha256(raster.tobytes()).hexdigest(),
                     "focus": focus, "p02_status": observed.status,
                     "p02_evidence_sha256": observed.evidence_sha256,
                     "p0_graph_sha256": observed.strong_graph.candidate_set_sha256,
                     "p02_arms": [asdict(a) for a in observed.arm_candidates],
                     "fragments": fragments, "fragment_sha256": digest(fragments),
                     "pixel_pass_equivalents": observed.pixel_pass_equivalents,
                     "observation_seconds": elapsed})
    return {"protocol": VERSION, "stage": "observe", "source": source_identity(),
            "rows": rows, "original_confirmation": "NOT_RUN",
            "input_scope": "actual-p02-arms-from-existing-synthetic-raster-bank"}


def fragment_tuple(row):
    from imageprogram.models.contextual_contour_cc01 import Fragment

    nodes = tuple(Fragment(n["node_id"], tuple(n["endpoint_a"]), tuple(n["endpoint_b"]),
                           tuple(n["tangent"]), n["pixels"], n["mean_l8"], n["region"])
                  for n in row["fragments"])
    if digest([asdict(n) for n in nodes]) != row["fragment_sha256"]:
        raise ValueError("fragment-hash-drift")
    return nodes


def predict(observation, observation_sha):
    checked(observation, observation_sha)
    if (observation.get("protocol") != VERSION or observation.get("stage") != "observe"
            or observation["source"] != source_identity()):
        raise ValueError("observation-source-drift")
    from imageprogram.models.contextual_contour_cc01 import _relation
    from imageprogram.models.contour_relation_g1 import fragment_digest, propose_relations

    rows = []
    for row in observation["rows"]:
        nodes = fragment_tuple(row)
        start = time.perf_counter()
        old = [_relation(a, b, max_gap=8) for i, a in enumerate(nodes) for b in nodes[i + 1:]]
        old_seconds = time.perf_counter() - start
        start = time.perf_counter()
        new = propose_relations(nodes)
        new_seconds = time.perf_counter() - start
        if fragment_digest(nodes) != row["fragment_sha256"] or new.fragment_sha256 != (
                row["fragment_sha256"]):
            raise ValueError("shared-fragment-identity-drift")
        rows.append({"task_id": row["task_id"], "fragment_sha256": new.fragment_sha256,
                     "g0": [asdict(e) for e in old if e is not None],
                     "g1": [asdict(e) for e in new.relations], "g1_status": new.status,
                     "pairs": new.considered_pairs,
                     "endpoint_pairs": new.evaluated_endpoint_pairs,
                     "g0_seconds": old_seconds, "g1_seconds": new_seconds})
    return {"protocol": VERSION, "stage": "predict", "source": source_identity(),
            "observation_sha256": observation_sha, "rows": rows,
            "budgets": {"max_gap": 8, "max_pairs": 128, "max_relations": 128},
            "original_confirmation": "NOT_RUN", "selected_path": "NOT_RUN"}


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phase", choices=("observe", "label", "predict", "grade"), required=True)
    ap.add_argument("--observation", type=Path)
    ap.add_argument("--observation-sha256")
    ap.add_argument("--receipt", type=Path)
    ap.add_argument("--expected-sha256")
    ap.add_argument("--labels", type=Path)
    ap.add_argument("--labels-sha256")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    if args.phase in ("observe", "predict") and any((args.labels, args.labels_sha256,
                                                    args.receipt, args.expected_sha256)):
        ap.error("public-stages-reject-private-label-and-grading-arguments")
    if args.phase == "observe":
        if args.observation or args.observation_sha256:
            ap.error("observe-takes-no-saved-input")
        result = observe()
    else:
        if not args.observation or not args.observation_sha256:
            ap.error("requires-observation-and-external-sha256")
        observation = checked(json.loads(args.observation.read_text()), args.observation_sha256)
        if args.phase == "predict":
            result = predict(observation, args.observation_sha256)
        else:
            # This module has no G0/G1/P02 calls and does not import previous target labels.
            from adapters.imageprogram_reference.contour_relation_g1_observed_grade import (
                grade,
                label,
            )
            if args.phase == "label":
                if any((args.labels, args.labels_sha256, args.receipt, args.expected_sha256)):
                    ap.error("label-takes-no-prediction")
                result = label(observation, args.observation_sha256)
            else:
                if not all((args.labels, args.labels_sha256, args.receipt, args.expected_sha256)):
                    ap.error("grade-requires-labels-receipt-and-both-external-sha256-values")
                labels = checked(json.loads(args.labels.read_text()), args.labels_sha256)
                receipt = checked(json.loads(args.receipt.read_text()), args.expected_sha256)
                result = grade(observation, args.observation_sha256, labels,
                               args.labels_sha256, receipt, args.expected_sha256)
    write_new(args.out, result)
    print("ARTIFACT_CANONICAL_SHA256", digest(result))


if __name__ == "__main__":
    main()
