"""P01 development-only weak evidence screen, separate predict and grade.

All source-derived target labels are Arena-owned. No confirmation factory is
called. Candidate retention is not semantic ownership or successful drawing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from adapters.imageprogram_reference.cc02_v2_ledger import (
    canonical,
    checkout_sha,
    sha256,
    write_once,
)

PROTOCOL = "cc02-p01-weak-evidence-dev-v1"
LEVELS = (199, 200, 201, 218, 229, 230, 245)
EXTRAS = ("salt4", "blob", "parallel", "component-flood", "candidate-flood", "blank", "short4")
CONFIG = {"strong_threshold": 200, "weak_threshold": 230,
          "max_weak_components": 8, "max_weak_candidates": 4,
          "max_pixel_work": 16384, "repetitions": 3}


def new_image(name):
    image = np.full((72, 72), 255, dtype=np.uint8)
    image[30, 10:29] = 0
    image[30, 33:53] = 0
    value = int(name[3:]) if name.startswith("l8-") else 218
    if name != "blank":
        image[30, 59:(63 if name == "short4" else 70)] = value
    if name == "salt4":
        image[5, [5, 9, 13, 17]] = 218
    elif name == "blob":
        image[48:51, 60:63] = 218
    elif name == "parallel":
        image[43, 59:70] = 218
    elif name == "component-flood":
        image[5, list(range(5, 37, 4))] = 218
    elif name == "candidate-flood":
        for y in (5, 10, 15, 20):
            image[y, 59:70] = 218
    return image


def public_cases():
    from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
        create_controls,
        create_development_pair,
    )

    for i in range(6):
        for j, (public, _) in enumerate(create_development_pair(i)):
            yield f"dev-{i:02d}-m{j}", public
    for i, (public, _) in enumerate(create_controls()):
        yield f"control-{i}", public
    for name in tuple(f"l8-{v}" for v in LEVELS) + EXTRAS:
        image = new_image(name)
        yield "screen-" + name, {
            "pixels_l8": image, "focus_box": (6, 12, 55, 59),
            "anchor_px": (10.5, 30.5),
            "raster_digest": hashlib.sha256(image.tobytes()).hexdigest(),
        }


def predict():
    import imageprogram
    from imageprogram.models import weak_contour_p01 as p1
    from imageprogram.models.contextual_contour_cc01 import observe_graph, select

    if [p1.STRONG_THRESHOLD, p1.WEAK_THRESHOLD, p1.MAX_WEAK_COMPONENTS,
        p1.MAX_WEAK_CANDIDATES, p1.MAX_PIXEL_WORK] != [200, 230, 8, 4, 16384]:
        raise ValueError("predeclared-config-mismatch")
    rows = []
    for key, public in public_cases():
        image, focus = public["pixels_l8"], public["focus_box"]
        if hashlib.sha256(image.tobytes()).hexdigest() != public["raster_digest"]:
            raise ValueError("public-raster-digest-mismatch")
        p0_times, p1_times, hashes = [], [], []
        for _ in range(CONFIG["repetitions"]):
            start = time.perf_counter_ns()
            p0 = observe_graph(image, focus)
            p0_times.append(time.perf_counter_ns() - start)
            start = time.perf_counter_ns()
            observation = p1.observe_weak(image, focus)
            p1_times.append(time.perf_counter_ns() - start)
            hashes.append(observation.evidence_sha256)
        if len(set(hashes)) != 1 or p0 != observation.strong_graph:
            raise ValueError("nondeterministic-or-strong-graph-changed")
        d0 = select(p0, public["anchor_px"])
        d1 = select(observation.strong_graph, public["anchor_px"])
        if d0 != d1:
            raise ValueError("frozen-GR-behavior-changed")
        rows.append({"case_key": key, "raster_sha256": public["raster_digest"],
                     "p0_graph": asdict(p0), "p1": asdict(observation),
                     "frozen_r0_decision": asdict(d0), "strong_graph_equal": True,
                     "frozen_r0_equal": True,
                     "p0_ns": p0_times, "p1_ns": p1_times,
                     "p0_median_ns": statistics.median(p0_times),
                     "p1_median_ns": statistics.median(p1_times)})
    payload = {"protocol": PROTOCOL, "config": CONFIG,
               "model_sha": checkout_sha(Path(imageprogram.__file__).resolve().parents[2]),
               "arena_sha": checkout_sha(Path(__file__).resolve().parents[2]),
               "input_count": len(rows), "rows": rows,
               "confirmation": "NOT_RUN", "real_art": "NOT_RUN",
               "label_provenance": "source-derived-technical-screen-not-blind",
               "weak_promotion_to_GR": "NOT_IMPLEMENTED"}
    payload["receipt_sha256"] = sha256(payload)
    return payload


def annotation(key, public):
    """Grading-only source geometry. New straight masks use array indexing."""
    from adapters.imageprogram_reference.cc02_arc_review import (
        _arc_points,
        development_continue_annotation,
    )
    from adapters.imageprogram_reference.cc02_v2_ledger import excluded_paths
    from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
        create_development_pair,
    )

    if key.startswith("dev-"):
        i, j = int(key[4:6]), int(key[-1])
        private = create_development_pair(i)[j][1]
        target = _arc_points(development_continue_annotation(i).path) if j == 0 else set()
        return target, excluded_paths(key, private) - target
    if key.startswith("control-"):
        return set(), set()
    name = key[7:]
    target = set() if name == "blank" else {
        (x, 30) for x in range(59, 63 if name == "short4" else 70)}
    # All added non-target weak pixels are marked as competing evidence.
    image = public["pixels_l8"]
    extra = {(int(x), int(y)) for y, x in zip(*np.where((image >= 200) & (image < 255)))}
    return target, extra - target


def grade(payload, expected_sha):
    from types import SimpleNamespace

    from adapters.imageprogram_reference.cc02_arc_review import (
        _coverage,
        _verified_node_supports,
    )

    if (payload.get("receipt_sha256") != expected_sha or
            sha256({k: v for k, v in payload.items() if k != "receipt_sha256"}) != expected_sha):
        raise ValueError("receipt-digest-mismatch")
    if payload.get("protocol") != PROTOCOL or payload.get("config") != CONFIG:
        raise ValueError("trial-contract-mismatch")
    if checkout_sha(Path(__file__).resolve().parents[2]) != payload["arena_sha"]:
        raise ValueError("arena-source-changed-before-grade")
    public = dict(public_cases())
    rows = payload["rows"]
    if len(rows) != 29 or {r["case_key"] for r in rows} != set(public):
        raise ValueError("missing-or-duplicate-inputs")
    reviews = []
    for row in rows:
        key = row["case_key"]
        obs = public[key]
        if row["raster_sha256"] != obs["raster_digest"]:
            raise ValueError("public-raster-mismatch")
        graph = row["p0_graph"]
        if graph != row["p1"]["strong_graph"]:
            raise ValueError("frozen-graph-mismatch")
        ref = {**graph, "threshold": 200, "max_gap": 8}
        ref.pop("candidate_set_sha256")
        if sha256(ref) != graph["candidate_set_sha256"]:
            raise ValueError("graph-content-digest-mismatch")
        ns = SimpleNamespace(nodes=tuple(SimpleNamespace(**n) for n in graph["nodes"]))
        supports = _verified_node_supports(obs, ns, 200, 16)
        strong = set().union(*(supports[n["node_id"]] for n in graph["nodes"]
                               if n["region"] == "context"))
        weak = set()
        for c in row["p1"]["weak_candidates"]:
            pixels = {tuple(p) for p in c["support_xy"]}
            if (c["ownership"] != "unknown" or c["evidence_kind"] != "weak-observed-ink" or
                    any(not 200 <= obs["pixels_l8"][y, x] < 230 for x, y in pixels)):
                raise ValueError("invalid-weak-evidence")
            if c["region"] == "context":
                weak.update(pixels)
        target, excluded = annotation(key, obs)
        if any(obs["pixels_l8"][y, x] >= 255 for x, y in target | excluded):
            raise ValueError("annotation-not-visible")
        p0_cov = _coverage(target, strong, 1.0) if target else None
        p1_cov = _coverage(target, strong | weak, 1.0) if target else None
        reviews.append({"case_key": key, "target_pixels": len(target),
                        "p0_coverage": p0_cov, "p1_coverage": p1_cov,
                        "weak_status": row["p1"]["weak_status"],
                        "weak_candidates": len(row["p1"]["weak_candidates"]),
                        "competing_pixels_retained": len(weak & excluded),
                        "weak_support_pixels": len(weak),
                        "p0_median_ns": row["p0_median_ns"],
                        "p1_median_ns": row["p1_median_ns"]})
    dev = [r for r in reviews if r["case_key"].startswith("dev-") and r["case_key"].endswith("m0")]
    return {"protocol": PROTOCOL, "receipt_sha256": expected_sha,
            "model_sha": payload["model_sha"], "arena_sha": payload["arena_sha"],
            "input_count": 29, "all_reviews": reviews,
            "dev_candidate_adequacy_p0": sum(r["p0_coverage"] >= 0.5 for r in dev),
            "dev_candidate_adequacy_p1": sum(r["p1_coverage"] >= 0.5 for r in dev),
            "strong_graphs_and_r0_preserved": all(r["strong_graph_equal"] and r["frozen_r0_equal"] for r in rows),
            "budget_abstentions": sum(r["weak_status"] != "ok" for r in reviews),
            "p0_median_case_ns": statistics.median(r["p0_median_ns"] for r in reviews),
            "p1_median_case_ns": statistics.median(r["p1_median_ns"] for r in reviews),
            "independent_semantic_annotation": "NOT_RUN",
            "weak_promotion_to_GR": "NOT_IMPLEMENTED", "confirmation": "NOT_SCORED",
            "real_art": "NOT_RUN", "drawing_or_skill_learning": "NOT_RUN"}


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--predict", action="store_true")
    mode.add_argument("--grade", action="store_true")
    parser.add_argument("--receipts", type=Path)
    parser.add_argument("--receipt-sha")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.predict:
        result = predict()
    else:
        if not args.receipts or not args.receipt_sha:
            parser.error("grade requires receipts and external digest")
        result = grade(json.loads(args.receipts.read_text()), args.receipt_sha)
    write_once(args.out, result)
    print(canonical({k: result[k] for k in ("protocol", "receipt_sha256", "input_count")}))


if __name__ == "__main__":
    main()
