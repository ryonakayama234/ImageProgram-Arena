"""CC-02 offline pre-change CC-01/v2 development diagnostic.

Cannot score the prospective confirmation split; only --seal-confirmation
writes safe public pair hashes, without importing or invoking ImageProgram.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
    VERSION,
    create_confirmation_pair,
    create_controls,
    create_development_pair,
    validate_pair,
)


def _git_sha(path):
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"


def _manifest(rows):
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def confirmation_seal():
    """No Model import or evaluation: freeze a distinct prospective family."""
    pairs = [validate_pair(create_confirmation_pair(i)) for i in range(6)]
    return {
        "split": "confirmation", "status": "sealed-NOT-SCORED",
        "family": "angled-arc-grammar-v1", "protocol_version": VERSION,
        "pair_count": 6, "manifest_sha256": _manifest(pairs),
        "pairs_public_only": pairs, "model_scores": None,
    }


def _review(decision, graph, private, public):
    """Independently classify action failure; private values used AFTER decision."""
    matched = []
    if private.target_region:
        x0, y0, x1, y1 = private.target_region
        matched = [
            n.node_id for n in graph.nodes if n.region == "context"
            and x0 <= (n.endpoint_a[0] + n.endpoint_b[0]) / 2 < x1
            and y0 <= (n.endpoint_a[1] + n.endpoint_b[1]) / 2 < y1
        ]
    if decision.action == private.expected_action:
        failure = "correct"
    elif private.expected_action == "continue" and not matched:
        failure = "candidate_missing"
    elif decision.action == "continue" and private.expected_action == "stop":
        failure = "unjustified_continue"
    elif decision.action == "stop" and private.expected_action == "continue":
        failure = "unjustified_stop"
    else:
        failure = "hold_mismatch"
    return {
        "pair_id": private.pair_id, "scene_kind": private.scene_kind,
        "member_id": private.member_id, "expected": private.expected_action,
        "actual": decision.action, "arm": decision.arm, "reason": decision.reason,
        "correct": decision.action == private.expected_action, "failure": failure,
        "target_candidate_count": len(matched),
        "node_count": len(graph.nodes), "edge_count": len(graph.edges),
        "local_node_count": sum(n.region == "focus" for n in graph.nodes),
        "candidate_set_sha256": graph.candidate_set_sha256,
        "public_sha256": public["raster_digest"],
    }


def run_development():
    """Use the unchanged previously implemented v2; do not import hidden labels into it."""
    import imageprogram
    from imageprogram.models.contextual_contour_cc01 import (
        VERSION as MODEL_VERSION,
    )
    from imageprogram.models.contextual_contour_cc01 import (
        observe_graph,
        select,
    )

    if MODEL_VERSION != "contextual-contour-cc01-v2":
        raise ValueError("pre-change-diagnostic-requires-v2")
    fixed = {
        "threshold": 200, "max_gap": 8, "max_nodes": 16,
        "max_pixels": 8192, "max_edges": 64,
    }
    pair_manifest, receipts, reviews = [], [], []
    for i in range(6):
        pair = create_development_pair(i)
        pair_manifest.append(validate_pair(pair))
        for public, private in pair:
            graph = observe_graph(
                public["pixels_l8"], public["focus_box"],
                threshold=fixed["threshold"], max_gap=fixed["max_gap"],
                max_nodes=fixed["max_nodes"], max_pixels=fixed["max_pixels"],
            )
            decisions = [
                select(graph, public["anchor_px"], arm=arm, max_edges=fixed["max_edges"])
                for arm in ("A1", "B", "B-shuffle")
            ]
            if len({d.candidate_set_sha256 for d in decisions}) != 1:
                raise RuntimeError("arm-candidate-mismatch")
            # All decision receipts are serialized BEFORE independent grading.
            snapshots = [asdict(d) for d in decisions]
            receipts.extend({
                **snapshot, "public_sha256": public["raster_digest"],
                "node_count": len(graph.nodes), "edge_count": len(graph.edges),
            } for snapshot in snapshots)
            reviews.extend(_review(d, graph, private, public) for d in decisions)

    for public, private in create_controls():
        graph = observe_graph(public["pixels_l8"], public["focus_box"])
        decision = select(graph, public["anchor_px"], arm="B")
        receipts.append({**asdict(decision), "public_sha256": public["raster_digest"],
                         "node_count": len(graph.nodes), "edge_count": len(graph.edges)})
        reviews.append(_review(decision, graph, private, public))

    summary = {}
    for arm in ("A1", "B", "B-shuffle"):
        xs = [r for r in reviews if r["arm"] == arm and r["pair_id"].startswith("dev-")]
        groups = {}
        for r in xs:
            groups.setdefault(r["pair_id"], []).append(r)
        summary[arm] = {
            "correct_members": sum(r["correct"] for r in xs),
            "members": len(xs),
            "both_correct_pairs": sum(len(p) == 2 and all(q["correct"] for q in p)
                                      for p in groups.values()),
            "pairs": len(groups), "holds": sum(r["actual"] == "hold" for r in xs),
            "false_continues": sum(r["failure"] == "unjustified_continue" for r in xs),
        }
    return {
        "experiment_id": "CC-02c-v2-prechange", "status": "development-diagnostic",
        "model_version": MODEL_VERSION, "arena_version": VERSION,
        "model_sha": _git_sha(Path(imageprogram.__file__).resolve().parents[2]),
        "arena_sha": _git_sha(Path(__file__).resolve().parents[2]),
        "fixed_config": fixed,
        "development_manifest_sha256": _manifest(pair_manifest),
        "development_pairs": pair_manifest, "decisions_before_review": receipts,
        "independent_reviews": reviews, "summary": summary,
        "confirmation": "NOT SCORED", "canvas": "NOT RUN",
        "motor": "NOT RUN", "replay": "NOT RUN",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--seal-confirmation", action="store_true")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.development == args.seal_confirmation:
        parser.error("choose exactly one of --development or --seal-confirmation")
    result = run_development() if args.development else confirmation_seal()
    if args.out.exists():
        raise ValueError("refuse-to-overwrite-evidence")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
                        + "\n", encoding="utf-8")
    print({"status": result["status"], "out": str(args.out),
           "summary": result.get("summary"), "manifest": result.get("manifest_sha256",
                            result.get("development_manifest_sha256"))})


if __name__ == "__main__":
    main()
