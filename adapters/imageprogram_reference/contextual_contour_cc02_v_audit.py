"""CC-02-V Arena-private synthetic arc evidence audit.

Only development six pairs and three controls are admitted. The sealed
confirmation family is NEVER instantiated or scored here. Ground-truth
geometry is defined independently of Model-produced candidates/decisions.

This is a diagnostic of finite observed synthetic ink, NOT evidence of
natural illustration contour ownership or real drawing ability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from adapters.imageprogram_reference.contextual_contour_cc02_pilot import _git_sha, _manifest
from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
    create_controls,
    create_development_pair,
    validate_pair,
)

VERSION = "arena-cc02-v-arc-audit-v1"
DEVELOPMENT_MANIFEST_SHA256 = "4d796ebc0467153a119a233724e6f9cfc1b8509b65c77bd101c31da3a3d61dcd"
# Zero-tolerance exact synthetic raster support: no interpolated approximate
# bounding boxes or post-hoc precision tuning.
MIN_CANDIDATE_COVERAGE = 1.0
FROZEN_CONFIG = {
    "threshold": 200, "max_gap": 8, "max_nodes": 16,
    "max_pixels": 8192, "max_edges": 64,
}


@dataclass(frozen=True)
class PrivateArc:
    """Arena-private centerline pixel index support, defined without model outputs."""
    member_id: str
    target_xy: tuple[tuple[int, int], ...]
    excluded_xy: tuple[tuple[int, int], ...]
    status: str = "synthetic-program-derived-single-annotation"
    version: str = VERSION


def _line(a, b):
    """Match the documented finite endpoint-inclusive raster line convention."""
    x0, y0 = a
    x1, y1 = b
    steps = max(abs(x1 - x0), abs(y1 - y0))
    return tuple((
        int(round(x0 + j * (x1 - x0) / max(steps, 1))),
        int(round(y0 + j * (y1 - y0) / max(steps, 1))),
    ) for j in range(steps + 1))


def _pixels(*segments):
    seen = set()
    for a, b in segments:
        seen.update(_line(a, b))
    return tuple(sorted(seen, key=lambda xy: (xy[1], xy[0])))


def development_private_arc(index, private):
    """Auditor-authored synthetic arc sidecar; does not read a selected graph.

    The branch structures are distractions/alternative topology, not proof of
    a unique underlying drawing history. The declared MAIN synthetic distal
    arc is the target evidence for the binary action protocol.
    """
    if not 0 <= index < 6 or private.split != "development":
        raise ValueError("development-only-private-annotation")
    y = 27 + index
    if private.expected_action == "continue":
        targets = (
            (((59, y + 1), (68, y + 5)),),
            (((59, y), (69, y)),),
            (((59, y), (63, y)), ((63, y), (69, y + 4))),
            (((59, y), (69, y)),),
            (((59, y), (69, y)),),
            (((59, y), (69, y)),),
        )
        excluded = (
            (),
            (((64, y), (64, y + 10)),),
            (),
            (),
            (((59, y + 12), (68, y + 12)),),
            (((64, y), (69, y - 5)), ((64, y), (69, y + 5))),
        )
        target_xy = _pixels(*targets[index])
        excluded_xy = _pixels(*excluded[index])
    elif private.expected_action == "stop":
        negative = (
            (((60, y + 8), (60, y + 19)),),
            (((60, y + 8), (60, y + 19)),),
            (((60, y + 8), (60, y + 19)),),
            (((60, y + 8), (60, y + 19)),),
            (((59, y + 7), (69, y + 7)), ((59, y + 12), (68, y + 12))),
            (((60, y + 7), (69, y + 15)), ((63, y + 15), (68, y + 15))),
        )
        target_xy = ()
        excluded_xy = _pixels(*negative[index])
    else:
        raise ValueError("binary-development-expected")
    return PrivateArc(private.member_id, target_xy, excluded_xy)


def _public_observe(public):
    from imageprogram.models.contextual_contour_cc01 import select
    from imageprogram.models.contextual_contour_cc02_trace import (
        observe_with_evidence,
        evidence_digest,
    )

    trace = observe_with_evidence(
        public["pixels_l8"], public["focus_box"],
        threshold=FROZEN_CONFIG["threshold"], max_gap=FROZEN_CONFIG["max_gap"],
        max_nodes=FROZEN_CONFIG["max_nodes"], max_pixels=FROZEN_CONFIG["max_pixels"],
    )
    snapshots = []
    for arm in ("A1", "B", "B-shuffle"):
        decision = select(
            trace.graph, public["anchor_px"],
            arm=arm, max_edges=FROZEN_CONFIG["max_edges"],
        )
        if decision.candidate_set_sha256 != trace.graph.candidate_set_sha256:
            raise RuntimeError("candidate-set-sha-mismatch")
        snapshots.append(asdict(decision))
    return trace, {
        "raster_sha256": public["raster_digest"],
        "graph_sha256": trace.graph.candidate_set_sha256,
        "trace_sha256": evidence_digest(trace),
        "nodes": len(trace.graph.nodes),
        "edges": len(trace.graph.edges),
        "decisions": snapshots,
    }


def _sha_json(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _review_dev(private, arc, trace, receipt, public):
    """Private grading AFTER receipts are fully recorded and hashed."""
    if arc.member_id != private.member_id:
        raise ValueError("private-annotation-identity-mismatch")
    raster = public["pixels_l8"]
    for x, y in (*arc.target_xy, *arc.excluded_xy):
        if not (0 <= x < raster.shape[1] and 0 <= y < raster.shape[0]):
            raise ValueError("annotation-out-of-bounds")
        if raster[y, x] == 255:
            raise ValueError("private-annotation-does-not-match-visible-ink")

    selected_components = [c for c in trace.components if c.admitted_node_id]
    admitted_pixels = {xy for c in selected_components for xy in c.pixels_xy}
    target = set(arc.target_xy)
    coverage = (len(target & admitted_pixels) / len(target)) if target else None
    threshold_fraction = (
        sum(int(raster[y, x]) < trace.threshold for x, y in target) / len(target)
        if target else None
    )
    # At 0px geometric tolerance, each admitted pixel must literally belong to
    # a retained graph Fragment. This avoids the old Node-BBox center proxy.
    target_ids = {
        c.admitted_node_id for c in selected_components if target.intersection(c.pixels_xy)
    }
    local_nodes = [n for n in trace.graph.nodes if n.region == "focus"]
    # The right-hand focus component is the publicly observed bridge-neighbor,
    # not chosen via any private target identity.
    neighbor = max(
        local_nodes, key=lambda n: max(n.endpoint_a[0], n.endpoint_b[0]),
        default=None,
    )
    edge_accessible = False
    forbidden_edge_count = 0
    if neighbor is not None:
        for e in trace.graph.edges:
            if (e.kind == "possible_continuation" and
                    {e.src, e.dst} & target_ids and
                    neighbor.node_id in (e.src, e.dst)):
                edge_accessible = True
            if (e.kind == "possible_continuation" and
                    neighbor.node_id in (e.src, e.dst) and not target and
                    any(n.node_id in (e.src, e.dst) and n.region == "context"
                        for n in trace.graph.nodes)):
                forbidden_edge_count += 1

    reviews = []
    for decision in receipt["decisions"]:
        action = decision["action"]
        correct = action == private.expected_action
        if not target:
            stage = "correct" if correct else "false-continue-or-hold"
        elif (coverage is None or coverage < MIN_CANDIDATE_COVERAGE):
            stage = "P-evidence-not-admitted"
        elif not edge_accessible:
            stage = "G-correct-relation-absent"
        elif not correct:
            stage = "R-selection-or-unobserved-path"
        else:
            stage = "correct"
        reviews.append({
            "arm": decision["arm"], "action": action,
            "expected": private.expected_action, "correct": correct,
            "earliest_blocker": stage,
        })
    return {
        "member_id": private.member_id,
        "scene_kind": private.scene_kind,
        "annotation_sha256": _sha_json(asdict(arc)),
        "annotation_status": arc.status,
        "target_pixels": len(target), "excluded_pixels": len(arc.excluded_xy),
        "threshold_survival": threshold_fraction,
        "admitted_target_coverage": coverage,
        "admitted_target_node_ids": sorted(target_ids),
        "target_edge_accessible": edge_accessible if target else None,
        "negative_supported_edge_count": forbidden_edge_count,
        "rejected_component_count": sum(not c.admitted_node_id for c in trace.components),
        "reviews": reviews,
    }


def run_development_audit():
    """One bounded stage audit, no confirmation calls and no model modification."""
    start_wall_ns = time.perf_counter_ns()
    start_cpu_ns = time.process_time_ns()
    import imageprogram
    import numpy as np
    from imageprogram.models.contextual_contour_cc01 import VERSION as MODEL_VERSION

    if MODEL_VERSION != "contextual-contour-cc01-v2":
        raise RuntimeError("refuse-non-frozen-model")
    from adapters.imageprogram_reference import contextual_contour_cc02_pilot as pilot

    pairs = [create_development_pair(i) for i in range(6)]
    manifests = [validate_pair(pair) for pair in pairs]
    manifest_hash = _manifest(manifests)
    if manifest_hash != DEVELOPMENT_MANIFEST_SHA256:
        raise RuntimeError("development-manifest-drift")

    # Phase one: NO private annotations / outcome grading. Store snapshots first.
    pending = []
    for i, pair in enumerate(pairs):
        for public, private in pair:
            trace, receipt = _public_observe(public)
            pending.append((i, public, private, trace, receipt))
    controls = []
    for public, private in create_controls():
        trace, receipt = _public_observe(public)
        controls.append((public, private, trace, receipt))
    pregrade_receipts = [rec for _, _, _, _, rec in pending] + [
        rec for _, _, _, rec in controls
    ]
    receipts_sha = _sha_json(pregrade_receipts)

    # Phase two: Arena-private sidecars are now allowed.
    graded = [
        _review_dev(private, development_private_arc(i, private), trace, receipt, public)
        for i, public, private, trace, receipt in pending
    ]
    control_grades = []
    for public, private, trace, receipt in controls:
        for d in receipt["decisions"]:
            if d["arm"] == "B":
                control_grades.append({
                    "member_id": private.member_id,
                    "actual": d["action"], "expected": private.expected_action,
                    "correct": d["action"] == private.expected_action,
                })
    by_arm = {}
    for arm in ("A1", "B", "B-shuffle"):
        decisions = [row["reviews"][k] for row in graded for k in range(3)
                     if row["reviews"][k]["arm"] == arm]
        by_arm[arm] = {
            "correct_members": sum(d["correct"] for d in decisions),
            "members": len(decisions),
            "holds": sum(d["action"] == "hold" for d in decisions),
        }
    b_continue = [r for r in graded if r["member_id"].endswith("-continue")]
    return {
        "experiment_id": "CC-02-V-001",
        "status": "development-only-stage-audit",
        "model_version": MODEL_VERSION,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "wall_elapsed_ns": time.perf_counter_ns() - start_wall_ns,
        "cpu_elapsed_ns": time.process_time_ns() - start_cpu_ns,
        "trace_version": "cc02-v-public-trace-v1",
        "arena_version": VERSION,
        "model_sha": _git_sha(Path(imageprogram.__file__).resolve().parents[2]),
        "arena_sha": _git_sha(Path(pilot.__file__).resolve().parents[2]),
        "development_manifest_sha256": manifest_hash,
        "config": FROZEN_CONFIG,
        "zero_tolerance_synthetic_support": True,
        "pregrade_receipts_sha256": receipts_sha,
        "pregrade_receipts": pregrade_receipts,
        "private_reviews": graded,
        "controls": control_grades,
        "summary": {
            "by_arm": by_arm,
            "b_positive_earliest_blockers": {
                key: sum(row["reviews"][1]["earliest_blocker"] == key
                         for row in b_continue)
                for key in ("P-evidence-not-admitted", "G-correct-relation-absent",
                            "R-selection-or-unobserved-path", "correct")
            },
        },
        "annotation_scope": "synthetic-program-derived, single author; NO real-art adjudication",
        "confirmation": "NOT SCORED",
        "real_art": "NOT RUN",
        "canvas": "NOT RUN",
        "motor": "NOT RUN",
        "replay": "NOT RUN",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", action="store_true", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("refuse-overwrite-evidence")
    result = run_development_audit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) +
                        "\n", encoding="utf-8")
    print({
        "experiment": result["experiment_id"],
        "manifest": result["development_manifest_sha256"],
        "receipt_sha": result["pregrade_receipts_sha256"],
        "summary": result["summary"],
        "out": str(args.out),
    })


if __name__ == "__main__":
    main()
