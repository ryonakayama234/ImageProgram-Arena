"""Arena P02 source-mask technical screen. Never accesses confirmation pairs.

PREDICT uses public raster only. GRADE re-generates procedural source masks in
another process and requires an externally anchored receipt SHA256.
The source author's masks are NOT independent blinded semantic annotations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
    create_controls,
    create_development_pair,
)

VERSION = "arena-branch-p02-screen-v0"
FOCUS = (6, 12, 55, 59)
# Fixed before authoritative checkout trial: 12 synthetic technical challenges.
# Public geometry only: name and observed source strokes. Private indices live in grade-only module.
CASES = (
    ("t-right", (((16, 30), (43, 30)), ((30, 30), (30, 44)))),
    ("t-left", (((16, 34), (43, 34)), ((30, 20), (30, 34)))),
    ("y-up", (((16, 35), (30, 35)), ((30, 35), (44, 21)),
              ((30, 35), (44, 49)))),
    ("y-down", (((16, 32), (30, 32)), ((30, 32), (45, 19)),
                ((30, 32), (45, 45)))),
    ("x-one", (((16, 16), (45, 45)), ((16, 45), (45, 16)))),
    ("x-two", (((16, 42), (46, 22)), ((18, 22), (46, 43)))),
    ("parallel", (((16, 28), (47, 28)), ((16, 35), (47, 35)))),
    ("near-miss", (((16, 32), (30, 32)), ((33, 34), (46, 34)))),
    ("corner", (((16, 32), (30, 32)), ((30, 32), (43, 42)))),
    ("thick-t", (((17, 32), (46, 32)), ((30, 32), (30, 49)),
                 ((17, 33), (46, 33)), ((31, 32), (31, 49)))),
    ("t-distractor", (((16, 30), (44, 30)), ((31, 30), (31, 44)),
                       ((55, 48), (67, 48)))),
    ("junction-grid", (((17, 22), (50, 22)), ((17, 30), (50, 30)),
                       ((17, 38), (50, 38)), ((25, 17), (25, 46)),
                       ((41, 17), (41, 46)))),
)


def _stroke(a, b):
    steps = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    return {(int(round(a[0] + (b[0] - a[0]) * i / max(steps, 1))),
             int(round(a[1] + (b[1] - a[1]) * i / max(steps, 1))))
            for i in range(steps + 1)}


def _technical_public(index):
    name, strokes = CASES[index]
    image = np.full((72, 72), 255, dtype=np.uint8)
    for a, b in strokes:
        for x, y in _stroke(a, b):
            image[y, x] = 0
    return name, {"pixels_l8": image, "focus_box": FOCUS,
                  "anchor_px": (16.5, 32.5)}


def _public_cases():
    for i in range(6):
        for public, _ in create_development_pair(i):
            yield "dev", public["raster_digest"], public
    for public, _ in create_controls():
        yield "control", public["raster_digest"], public
    for i in range(len(CASES)):
        name, public = _technical_public(i)
        digest = hashlib.sha256(public["pixels_l8"].tobytes()).hexdigest()
        yield "technical", name + ":" + digest, public


def predict():
    from imageprogram.models.branch_contour_p02 import observe_branch
    from imageprogram.models.contextual_contour_cc01 import observe_graph, select
    from imageprogram.models import contextual_contour_cc01 as baseline_module
    from imageprogram.models import branch_contour_p02 as branch_module

    source_hashes = {
        "p02_model": hashlib.sha256(Path(branch_module.__file__).read_bytes()).hexdigest(),
        "frozen_p0": hashlib.sha256(Path(baseline_module.__file__).read_bytes()).hexdigest(),
        "arena_trial": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    rows = []
    for family, case_id, public in _public_cases():
        image, focus = public["pixels_l8"], public["focus_box"]
        out = observe_branch(image, focus)
        baseline = observe_graph(image, focus)
        if out.strong_graph != baseline:
            raise RuntimeError("frozen-baseline-mismatch")
        decision = select(baseline, public["anchor_px"], arm="B")
        if out.strong_graph.candidate_set_sha256 != decision.candidate_set_sha256:
            raise RuntimeError("frozen-decision-mismatch")
        rows.append({"family": family, "case_id": case_id,
                     "raster_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                     "strong_sha256": baseline.candidate_set_sha256,
                     "baseline_action": decision.action,
                     "baseline_decision": asdict(decision),
                     "status": out.status, "junction_pixels": out.junction_pixels_seen,
                     "work": out.pixel_pass_equivalents,
                     "evidence_sha256": out.evidence_sha256,
                     "arms": [asdict(a) for a in out.arm_candidates]})
    return {"version": VERSION, "split": "development-and-technical-only",
            "confirmation": "NOT_RUN", "source_sha256": source_hashes,
            "model_budget": {"threshold": 200, "junction_pixels": 8,
                             "arm_candidates": 16, "pixel_pass_equivalents": 16384},
            "rows": rows}


def _source_masks(family, case_id, public):
    image = public["pixels_l8"]
    if family == "technical":
        index = next(i for i, c in enumerate(CASES)
                     if case_id.startswith(c[0] + ":"))
        from adapters.imageprogram_reference.branch_contour_p02_private import (
            SOURCE_STROKE_INDICES,
        )
        _, strokes = CASES[index]
        chosen, excluded = SOURCE_STROKE_INDICES[index]
        target = _stroke(*strokes[chosen]) if chosen is not None else set()
        other = _stroke(*strokes[excluded]) if excluded is not None else set()
        # Shared observed junction ink is not forbidden-exclusive ink.
        return target, other - target
    if family == "dev":
        # Historical source-derived region proxy is not a blind target arc.
        for i in range(6):
            for known, private in create_development_pair(i):
                if known["raster_digest"] != case_id:
                    continue
                if private.target_region is None:
                    return set(), {(x, y) for y, x in zip(*np.where(image < 230))}
                x0, y0, x1, y1 = private.target_region
                target = {(x, y) for y, x in zip(*np.where(image < 230))
                          if x0 <= x < x1 and y0 <= y < y1}
                return target, set()
        raise ValueError("unknown-development-case")
    return set(), set()


def grade(receipt, anchored_sha):
    raw = json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False)
    actual = hashlib.sha256(raw.encode()).hexdigest()
    if actual != anchored_sha:
        raise ValueError("unanchored-or-altered-prediction")
    if receipt.get("version") != VERSION:
        raise ValueError("version-mismatch")
    source = receipt.get("source_sha256", {})
    if source.get("arena_trial") != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError("arena-source-drift")
    rows = list(_public_cases())
    if (len(rows) != len(receipt["rows"])
            or receipt.get("confirmation") != "NOT_RUN"
            or receipt.get("split") != "development-and-technical-only"):
        raise ValueError("manifest-or-confirmation-mismatch")
    reviews = []
    for (family, case_id, public), saved in zip(rows, receipt["rows"]):
        if (saved["family"] != family or saved["case_id"] != case_id
                or saved["raster_sha256"] != hashlib.sha256(
                    public["pixels_l8"].tobytes()).hexdigest()):
            raise ValueError("public-case-hash-mismatch")
        target, excluded = _source_masks(family, case_id, public)
        arms = saved["arms"]
        support = [set(map(tuple, arm["support_xy"])) for arm in arms]
        all_core = set().union(*support) if support else set()
        covered = len(target & all_core) / len(target) if target else None
        best_single = max((len(target & s) / len(target) for s in support),
                          default=0.0) if target else None
        reviews.append({"family": family, "case_id": case_id,
                        "target_pixels": len(target),
                        "excluded_pixels": len(excluded),
                        "core_target_recall": covered,
                        "best_arm_recall": best_single,
                        "excluded_core_pixels": len(all_core & excluded),
                        "arm_count": len(arms), "status": saved["status"],
                        "work": saved["work"]})
    return {"version": VERSION, "receipt_sha256": actual,
            "confirmation": "NOT_RUN",
            "annotation": "source-derived-not-blind",
            "reviews": reviews}


def _write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, sort_keys=True, indent=2, ensure_ascii=False)
        handle.write("
")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--predict", action="store_true")
    parser.add_argument("--grade", action="store_true")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.predict == args.grade:
        parser.error("choose --predict or --grade")
    if args.predict:
        data = predict()
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
        print("ANCHOR_BEFORE_GRADE_SHA256",
              hashlib.sha256(raw.encode()).hexdigest())
    else:
        if not args.receipt or not args.expected_sha256:
            parser.error("GRADE needs receipt and externally anchored sha256")
        data = grade(json.loads(args.receipt.read_text(encoding="utf-8")),
                     args.expected_sha256)
    _write_new(args.out, data)
    print("saved", args.out)


if __name__ == "__main__":
    main()
