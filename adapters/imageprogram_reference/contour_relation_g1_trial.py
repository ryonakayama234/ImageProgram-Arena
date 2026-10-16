"""Saved G0/G1 predictions on SAME frozen public Fragments; private grade only.

This is a deliberately injected-geometry diagnostic, NOT P02 real graph transfer,
independent/blind target-arc review, selected path inference or drawing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from imageprogram.models.contextual_contour_cc01 import _relation
from imageprogram.models.contour_relation_g1 import fragment_digest, propose_relations

from adapters.imageprogram_reference.contour_relation_g1_tasks import public_tasks

VERSION = "arena-cc02-g1-diagnostic-v0"


def _canonical_sha(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def predict():
    records = []
    for task in public_tasks():
        nodes = task.fragments
        out = propose_relations(nodes)
        old = [_relation(a, b, max_gap=8) for i, a in enumerate(nodes) for b in nodes[i + 1:]]
        baseline = [asdict(x) for x in old if x is not None]
        if out.fragment_sha256 != fragment_digest(nodes):
            raise RuntimeError("frozen-fragment-hash-drift")
        records.append({"task_id": task.task_id, "split": task.evidence_split,
                        "public_fragment_sha256": out.fragment_sha256,
                        "g0_edges": baseline, "g1_relations": [asdict(x) for x in out.relations],
                        "g1_status": out.status, "pairs": out.considered_pairs,
                        "endpoint_pairs": out.evaluated_endpoint_pairs})
    return {"protocol": VERSION, "records": records,
            "original_confirmation": "NOT_RUN", "real_art": "NOT_RUN",
            "independent_annotation": "NOT_RUN"}


def grade(saved, retained_sha):
    if _canonical_sha(saved) != retained_sha:
        raise ValueError("unanchored-prediction-sha")
    if saved.get("protocol") != VERSION or saved.get("original_confirmation") != "NOT_RUN":
        raise ValueError("prediction-contract-mismatch")
    from adapters.imageprogram_reference.contour_relation_g1_private import EXPECTED_G_ONLY

    tasks = public_tasks()
    rows = saved.get("records", [])
    if len(rows) != len(tasks):
        raise ValueError("task-count-mismatch")
    reviews = []
    for task, row in zip(tasks, rows):
        if row["task_id"] != task.task_id or row["public_fragment_sha256"] != fragment_digest(
                task.fragments):
            raise ValueError("public-fragment-drift")
        labels = EXPECTED_G_ONLY[task.task_id]
        scored = []
        for pair, truth in labels.items():
            a, b = pair.split(":")
            edge = next((x for x in row["g1_relations"] if x["src"] == a and x["dst"] == b), None)
            baseline = next((x for x in row["g0_edges"] if x["src"] == a and x["dst"] == b), None)
            new_kind = edge["kind"] if edge else "absent"
            old_kind = baseline["kind"] if baseline else "absent"
            scored.append({"pair": pair, "source_derived_label": truth,
                           "g0": old_kind, "g1": new_kind,
                           "g0_match": None if truth == "unknown" else
                           ((old_kind == "possible_continuation") == (truth == "positive")),
                           "g1_match": None if truth == "unknown" else
                           ((new_kind == "possible_continuation") == (truth == "positive"))})
        reviews.append({"task_id": task.task_id, "pairs": scored,
                        "status": row["g1_status"], "fragment_sha256": row["public_fragment_sha256"]})
    labels = [x for row in reviews for x in row["pairs"] if x["source_derived_label"] != "unknown"]
    return {"protocol": VERSION, "prediction_sha256": retained_sha,
            "annotation": "same-author-geometry-not-blind",
            "g0_correct": sum(x["g0_match"] for x in labels),
            "g1_correct": sum(x["g1_match"] for x in labels),
            "scored_pairs": len(labels), "reviews": reviews,
            "original_confirmation": "NOT_RUN", "selected_path": "NOT_RUN"}


def _write_new(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("predict", "grade"), required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    if args.phase == "predict":
        if args.receipt is not None or args.expected_sha256 is not None:
            parser.error("predict-accepts-no-private-grading-inputs")
        record = predict()
        print("ANCHOR_BEFORE_GRADE_SHA256", _canonical_sha(record))
    else:
        if not args.receipt or not args.expected_sha256:
            parser.error("grade-requires-saved-receipt-and-external-anchor")
        record = grade(json.loads(args.receipt.read_text(encoding="utf-8")),
                       args.expected_sha256)
    _write_new(args.out, record)


if __name__ == "__main__":
    main()
