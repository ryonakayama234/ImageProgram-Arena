"""CC-02-V1: development-only actual-arc audit of the frozen CC-01/v2 graph.

This is an Arena PRIVATE reviewer. No target arc, label or component ID is
passed to the Model. Source-authored synthetic annotations are not a blind,
independent human annotation of real art. Confirmation is deliberately absent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

AUDIT_VERSION = "cc02-v1-source-arc-audit-v1"
EVIDENCE_PROVENANCE = "source-derived-synthetic-unblinded"
HUMAN_ADJUDICATION = "NOT_RUN"
ARC_TOLERANCE_PX = 1.0
MIN_TARGET_COVERAGE = 0.5  # Diagnostic convention; not a learned threshold.


@dataclass(frozen=True)
class PrivateArc:
    pair_id: str
    member_id: str
    expected_action: str
    # Exact pixel-center polyline points, manually transcribed from the DEV
    # source specification. Branch arms are not the intended main path.
    path: tuple[tuple[int, int], ...]


def development_continue_annotation(index: int) -> PrivateArc:
    """Returns only DEV intended-main-path arcs; never touch confirmation."""
    if type(index) is not int or not 0 <= index < 6:
        raise ValueError("development-index-only")
    y = 27 + index
    paths = (
        ((59, y + 1), (68, y + 5)),        # slanted
        ((59, y), (69, y)),                # T main path (branch separate)
        ((59, y), (63, y), (69, y + 4)),   # curved/polyline main path
        ((59, y), (69, y)),                # faint 218 L8
        ((59, y), (69, y)),                # separate parallel distractor
        ((59, y), (69, y)),                # Y main path (arms separate)
    )
    return PrivateArc(f"dev-{index:02d}", f"dev-{index:02d}-continue",
                      "continue", paths[index])


def _canonical_sha(data: object) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _arc_points(path: tuple[tuple[int, int], ...]) -> set[tuple[int, int]]:
    """Use the synthetic source rasterizer's endpoint-inclusive rounding rule."""
    points: set[tuple[int, int]] = set()
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        steps = max(abs(x1 - x0), abs(y1 - y0))
        for j in range(steps + 1):
            a = j / max(1, steps)
            points.add((int(round(x0 + a * (x1 - x0))),
                        int(round(y0 + a * (y1 - y0)))))
    return points


def _components_from_public(raster: np.ndarray, threshold: int,
                            max_nodes: int) -> list[set[tuple[int, int]]]:
    """Independent 8-connected-component implementation, row-major indexed.

    Index is used only to verify support for the frozen v2 node identifier.
    A future model with non-v2 IDs must use a versioned support adapter.
    """
    mask = raster < threshold
    visited = np.zeros_like(mask, dtype=bool)
    h, w = mask.shape
    out: list[set[tuple[int, int]]] = []
    for y, x in zip(*np.where(mask)):
        y, x = int(y), int(x)
        if visited[y, x]:
            continue
        todo = [(y, x)]
        visited[y, x] = True
        points = set()
        while todo:
            cy, cx = todo.pop()
            points.add((cx, cy))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        todo.append((ny, nx))
        out.append(points)
        if len(out) > max_nodes:
            raise ValueError("component-budget-exceeded")
    return out


def _verified_node_supports(public: dict, graph: object, threshold: int,
                            max_nodes: int) -> dict[str, set[tuple[int, int]]]:
    raster = public["pixels_l8"]
    comps = _components_from_public(raster, threshold, max_nodes)
    result: dict[str, set[tuple[int, int]]] = {}
    for node in graph.nodes:
        ident = node.node_id
        if not ident.startswith("fragment-") or not ident[9:].isdigit():
            raise ValueError("unsupported-v2-node-identifier")
        idx = int(ident[9:])
        if idx >= len(comps):
            raise ValueError("node-component-index-invalid")
        support = comps[idx]
        if len(support) != node.pixels:
            raise ValueError("node-component-size-mismatch")
        mean = sum(int(raster[y, x]) for x, y in support) / len(support)
        if not math.isclose(mean, node.mean_l8, rel_tol=0, abs_tol=1e-7):
            raise ValueError("node-component-intensity-mismatch")
        result[ident] = support
    return result


def _coverage(arc: set[tuple[int, int]], support: set[tuple[int, int]],
              tol: float) -> float:
    if not arc or not support:
        return 0.0
    radius2 = tol * tol
    return sum(any((ax - sx) ** 2 + (ay - sy) ** 2 <= radius2
                   for sx, sy in support) for ax, ay in arc) / len(arc)


def audit_continue(public: dict, graph: object, decision: object,
                   annotation: PrivateArc, *, threshold: int = 200,
                   max_nodes: int = 16,
                   tolerance_px: float = ARC_TOLERANCE_PX,
                   min_coverage: float = MIN_TARGET_COVERAGE) -> dict:
    """Audit the already-produced v2 decision with private DEV target geometry.

    Stage is single-primary where diagnosable; cases with no selected local
    neighbor or unverifiable component are explicitly UNRESOLVED.
    """
    if annotation.expected_action != "continue" or not annotation.pair_id.startswith("dev-"):
        raise ValueError("continue-development-only")
    if decision.arm != "B" or decision.candidate_set_sha256 != graph.candidate_set_sha256:
        raise ValueError("decision-graph-mismatch")
    if not 0 <= tolerance_px <= 2 or not 0 < min_coverage <= 1:
        raise ValueError("invalid-audit-tolerance")
    arc = _arc_points(annotation.path)
    raster = public["pixels_l8"]
    if any(not 0 <= x < raster.shape[1] or not 0 <= y < raster.shape[0]
           or int(raster[y, x]) >= 255 for x, y in arc):
        raise ValueError("annotation-not-visible-in-public-raster")
    supports = _verified_node_supports(public, graph, threshold, max_nodes)
    per_node = {n.node_id: _coverage(arc, supports[n.node_id], tolerance_px)
                for n in graph.nodes if n.region == "context"}
    eligible = sorted(node_id for node_id, value in per_node.items() if value >= min_coverage)
    union = set().union(*(supports[node_id] for node_id in per_node)) if per_node else set()
    total_coverage = _coverage(arc, union, tolerance_px)
    local_neighbor = decision.selected_nodes[1] if len(decision.selected_nodes) >= 2 else None
    if not eligible and total_coverage >= min_coverage:
        stage = "UNRESOLVED_FRAGMENTED_TARGET"
    elif not eligible:
        stage = "P_CANDIDATE_ABSENT"
    elif local_neighbor is None:
        stage = "UNRESOLVED_LOCAL_PATH"
    elif not any(edge.kind == "possible_continuation" and
                 {edge.src, edge.dst} == {local_neighbor, target}
                 for target in eligible for edge in graph.edges):
        stage = "G_CONTINUATION_EDGE_ABSENT"
    elif decision.action != "continue":
        stage = "R_SELECTION_FAILURE"
    else:
        stage = "ACTION_CORRECT_PATH_EDGE_UNOBSERVED"
    return {
        "audit_version": AUDIT_VERSION,
        "pair_id": annotation.pair_id,
        "member_id": annotation.member_id,
        "evidence_provenance": EVIDENCE_PROVENANCE,
        "human_adjudication": HUMAN_ADJUDICATION,
        "public_sha256": public["raster_digest"],
        "candidate_set_sha256": graph.candidate_set_sha256,
        "annotation_sha256": _canonical_sha(asdict(annotation)),
        "target_arc_pixels": len(arc),
        "arc_coverage_all_context_nodes": round(total_coverage, 6),
        "target_node_coverage": {k: round(v, 6) for k, v in sorted(per_node.items())},
        "eligible_target_nodes": eligible,
        "selected_local_neighbor": local_neighbor,
        "decision_action": decision.action,
        "diagnostic_stage": stage,
        "coverage_tolerance_px": tolerance_px,
        "min_single_node_coverage": min_coverage,
        "path_edge_receipt": "UNAVAILABLE_IN_FROZEN_V2",
    }


def run_development_arc_audit() -> dict:
    """Development ONLY. Import Model for decisions, then private evaluator."""
    from imageprogram.models.contextual_contour_cc01 import (
        VERSION, observe_graph, select,
    )
    from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
        create_development_pair, validate_pair,
    )
    if VERSION != "contextual-contour-cc01-v2":
        raise ValueError("frozen-v2-required")
    # Model receives ONLY public data; all decisions precede private review.
    # The annotations NEVER enter observe_graph/select.
    pre_review = []
    for i in range(6):
        pair = create_development_pair(i)
        validate_pair(pair)
        public = pair[0][0]  # The DEV task convention is continue, then stop.
        graph = observe_graph(public["pixels_l8"], public["focus_box"],
                              threshold=200, max_gap=8, max_nodes=16,
                              max_pixels=8192)
        decision = select(graph, public["anchor_px"], arm="B", max_edges=64)
        pre_review.append((i, public, graph, decision))
    receipts = [{"pair_id": f"dev-{i:02d}", "public_sha256": public["raster_digest"],
                 "candidate_set_sha256": graph.candidate_set_sha256,
                 "action": decision.action, "reason": decision.reason,
                 "selected_nodes": list(decision.selected_nodes),
                 "node_count": len(graph.nodes), "edge_count": len(graph.edges)}
                for i, public, graph, decision in pre_review]
    receipt_sha = _canonical_sha(receipts)
    reviews = [audit_continue(public, graph, decision,
                              development_continue_annotation(i))
               for i, public, graph, decision in pre_review]
    return {
        "experiment_id": "CC-02-V1-source-arc-audit",
        "status": "development-source-derived-diagnostic",
        "reviewer_version": AUDIT_VERSION,
        "model_version": VERSION,
        "source_review": "UNBLINDED; requires independent adjudication",
        "confirmation": "NOT_RUN",
        "real_art": "NOT_RUN",
        "decision_receipts_before_review": receipts,
        "receipt_sha256": receipt_sha,
        "reviews": reviews,
        "stage_counts": {stage: sum(r["diagnostic_stage"] == stage for r in reviews)
                         for stage in sorted({r["diagnostic_stage"] for r in reviews})},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", action="store_true", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("refuse-to-overwrite-evidence")
    report = run_development_arc_audit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print({"status": report["status"], "stage_counts": report["stage_counts"]})


if __name__ == "__main__":
    main()
