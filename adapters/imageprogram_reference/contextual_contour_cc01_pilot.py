"""CC-01 offline paired decision pilot; *not* Motor or Canvas validation.

Run from the Arena checkout with ImageProgram installed:
    python -m adapters.imageprogram_reference.contextual_contour_cc01_pilot \
        --split development --out /tmp/cc01-dev.json
    python -m adapters.imageprogram_reference.contextual_contour_cc01_pilot \
        --split rotation_probe --out /tmp/cc01-confirm.json
Never publish full private manifests/annotations by default; the output path is local.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from adapters.imageprogram_reference.contextual_contour_cc01 import (
    VERSION as ARENA_VERSION,
    aggregate,
    create_pair,
    evaluate,
    validate_pair,
)
from imageprogram.models.contextual_contour_cc01 import VERSION as MODEL_VERSION
from imageprogram.models.contextual_contour_cc01 import observe_graph, select


def _git_sha(path):
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True,
            stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def run(split):
    if split not in ("development", "rotation_probe"):
        raise ValueError("unknown-split")
    rows = []
    pair_manifest = []
    decisions = []
    for i in range(6):
        cases = create_pair(i, split=split)
        pair_manifest.append(validate_pair(cases))
        for public, private in cases:
            graph = observe_graph(
                public["pixels_l8"], public["focus_box"],
                threshold=200, max_gap=8, max_nodes=16, max_pixels=8192,
            )
            arm_decisions = [select(graph, public["anchor_px"], arm=arm, max_edges=64)
                             for arm in ("A1", "B", "B-shuffle")]
            if len({d.candidate_set_sha256 for d in arm_decisions}) != 1:
                raise ValueError("candidate-set-mismatch")
            for decision in arm_decisions:
                # Independent review only happens AFTER receipt construction.
                receipt = asdict(decision)
                receipt["public_raster_digest"] = public["raster_digest"]
                receipt["node_count"] = len(graph.nodes)
                receipt["edge_count"] = len(graph.edges)
                decisions.append(receipt)
                rows.append(evaluate(decision, private))
    stats = aggregate(rows)
    return {
        "experiment_id": f"CC-01-{split}",
        "status": "decision-only-experiment",
        "model_version": MODEL_VERSION,
        "arena_version": ARENA_VERSION,
        "fixed_config": {"threshold_l8": 200, "max_gap_px": 8,
                         "max_nodes": 16, "max_pixels": 8192,
                         "max_edges": 64},
        "model_sha": _git_sha(Path(__import__("imageprogram").__file__).resolve().parents[2]),
        "arena_sha": _git_sha(Path(__file__).resolve().parents[2]),
        "pair_manifest": pair_manifest,
        "counts": stats,
        "decisions_before_private_review": decisions,
        "private_reviews_after_decision": rows,
        "drawing_status": "not-run",
        "motor_replay_status": "not-run",
        "natural_art_transfer": "unknown",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", required=True, choices=("development", "rotation_probe"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = run(args.split)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.out.exists():
            raise ValueError("refuse-overwrite-experiment-record")
        args.out.write_text(text, encoding="utf-8")
        print(f"CC-01 {args.split}: {report['counts']} -> {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
