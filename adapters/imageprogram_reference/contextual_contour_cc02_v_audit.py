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
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace

from adapters.imageprogram_reference.contextual_contour_cc02_pilot import _git_sha, _manifest
from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
    create_controls,
    create_development_pair,
    validate_pair,
)

VERSION = "arena-cc02-v-arc-audit-v2"
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
        round(x0 + j * (x1 - x0) / max(steps, 1)),
        round(y0 + j * (y1 - y0) / max(steps, 1)),
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
        evidence_digest,
        observe_with_evidence,
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
        "public_input": _public_identity(public),
        "trace": asdict(trace),
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


def _file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


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
    # An admitted component can contain both target and an excluded branch.
    # Shared junction pixels are allowed; branch-exclusive pixels are not.
    excluded_only = set(arc.excluded_xy) - target
    target_components = [c for c in selected_components if c.admitted_node_id in target_ids]
    target_support = {xy for c in target_components for xy in c.pixels_xy}
    contamination = len(target_support & excluded_only)
    edge_accessible = False
    b_decision = next(d for d in receipt["decisions"] if d["arm"] == "B")
    selected_ids = b_decision["selected_nodes"]
    nodes = {n.node_id: n for n in trace.graph.nodes}
    # Use the selector's actual local pair, never the rightmost focus object.
    neighbor_id = selected_ids[1] if len(selected_ids) == 2 else None
    local_pair_known = (neighbor_id in nodes and
                        all(n in nodes and nodes[n].region == "focus" for n in selected_ids))
    forbidden_edge_count = 0
    if local_pair_known:
        for e in trace.graph.edges:
            if e.kind != "possible_continuation" or neighbor_id not in (e.src, e.dst):
                continue
            other = e.dst if e.src == neighbor_id else e.src
            if other in target_ids and nodes[other].region == "context":
                edge_accessible = True
            if not target and other in nodes and nodes[other].region == "context":
                forbidden_edge_count += 1

    reviews = []
    for decision in receipt["decisions"]:
        action = decision["action"]
        correct = action == private.expected_action
        if not target:
            stage = "correct" if correct else "false-continue-or-hold"
        elif (coverage is None or coverage < MIN_CANDIDATE_COVERAGE):
            stage = "P-evidence-not-admitted"
        elif contamination:
            stage = "target-ownership-unresolved"
        elif not local_pair_known:
            stage = "local-selection-unresolved"
        elif not edge_accessible:
            stage = "G-correct-relation-absent"
        elif not correct:
            stage = "R-selection-or-unobserved-path"
        else:
            stage = "action-correct-path-unverified"
        reviews.append({
            "arm": decision["arm"], "action": action,
            "expected": private.expected_action, "correct": correct,
            # Stage attribution is defined for the full-context B arm only.
            "earliest_blocker": stage if decision["arm"] == "B" else "NOT_ATTRIBUTED",
            "selected_path_verdict": "UNKNOWN",
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
        "target_edge_accessible": edge_accessible if target and local_pair_known else None,
        "b_local_pair_known": bool(local_pair_known),
        "target_component_excluded_pixels": contamination,
        "shared_target_excluded_pixels": len(target & set(arc.excluded_xy)),
        "negative_supported_edge_count": forbidden_edge_count,
        "rejected_component_count": sum(not c.admitted_node_id for c in trace.components),
        "reviews": reviews,
    }


def _public_identity(public):
    return {
        "format": public["format"], "raster_sha256": public["raster_digest"],
        "shape": list(public["pixels_l8"].shape), "dtype": str(public["pixels_l8"].dtype),
        "focus_box": list(public["focus_box"]), "anchor_px": list(public["anchor_px"]),
        "budget_pixels": public["budget_pixels"],
    }


def _development_inputs():
    pairs = [create_development_pair(i) for i in range(6)]
    if _manifest([validate_pair(pair) for pair in pairs]) != DEVELOPMENT_MANIFEST_SHA256:
        raise RuntimeError("development-manifest-drift")
    return [(i, public, private) for i, pair in enumerate(pairs)
            for public, private in pair] + [
                (None, public, private) for public, private in create_controls()]


def _provenance():
    import imageprogram
    import numpy as np
    from imageprogram.models.contextual_contour_cc01 import VERSION as MODEL_VERSION
    from imageprogram.models.contextual_contour_cc02_trace import TRACE_VERSION

    if MODEL_VERSION != "contextual-contour-cc01-v2":
        raise RuntimeError("refuse-non-frozen-model")
    model_root = Path(imageprogram.__file__).resolve().parents[2]
    arena_root = Path(__file__).resolve().parents[2]
    model_sha, arena_sha = _git_sha(model_root), _git_sha(arena_root)
    if "unknown" in (model_sha, arena_sha):
        raise RuntimeError("paired-git-checkout-sha-required")
    sources = {
        "model_observer": model_root / "src/imageprogram/models/contextual_contour_cc01.py",
        "model_public_trace": model_root / "src/imageprogram/models/contextual_contour_cc02_trace.py",
        "model_uv_lock": model_root / "uv.lock",
        "model_pyproject": model_root / "pyproject.toml",
        "arena_generator": Path(__file__).with_name("contextual_contour_cc02_tasks.py"),
        "arena_pilot": Path(__file__).with_name("contextual_contour_cc02_pilot.py"),
        "arena_auditor": Path(__file__),
    }
    return {
        "model_sha": model_sha, "arena_sha": arena_sha,
        "model_version": MODEL_VERSION, "trace_version": TRACE_VERSION,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "source_file_sha256": {key: _file_sha(path) for key, path in sources.items()},
        "checkout_dirty": {
            name: bool(subprocess.check_output(
                ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
                text=True)) for name, root in (("model", model_root), ("arena", arena_root))
        },
    }


def predict_development():
    """Public predictions only. Serialize this result BEFORE invoking the grader."""
    start_wall, start_cpu = time.perf_counter_ns(), time.process_time_ns()
    provenance = _provenance()
    receipts = []
    for _, public, _ in _development_inputs():
        _, receipt = _public_observe(public)
        receipts.append(receipt)
    return {
        "experiment_id": "CC-02-V-001", "phase": "PREDICT", "arena_version": VERSION,
        "development_manifest_sha256": DEVELOPMENT_MANIFEST_SHA256,
        **provenance, "config": dict(FROZEN_CONFIG),
        "config_sha256": _sha_json(FROZEN_CONFIG),
        "pregrade_receipts_sha256": _sha_json(receipts), "pregrade_receipts": receipts,
        "wall_elapsed_ns": time.perf_counter_ns() - start_wall,
        "cpu_elapsed_ns": time.process_time_ns() - start_cpu,
        "confirmation": "NOT SCORED", "real_art": "NOT RUN",
    }


def _decode_trace(value):
    # Plain data reconstruction: grading NEVER reruns observe_graph or select.
    graph = value["graph"]
    return SimpleNamespace(
        **{key: val for key, val in value.items() if key not in ("graph", "components")},
        graph=SimpleNamespace(
            **{key: val for key, val in graph.items() if key not in ("nodes", "edges")},
            nodes=tuple(SimpleNamespace(**n) for n in graph["nodes"]),
            edges=tuple(SimpleNamespace(**e) for e in graph["edges"])),
        components=tuple(SimpleNamespace(**{**c, "pixels_xy": tuple(map(tuple, c["pixels_xy"]))})
                         for c in value["components"]),
    )


def _validate_receipt(receipt, public):
    from imageprogram.models.contextual_contour_cc02_trace import TRACE_VERSION, evidence_digest

    if receipt["public_input"] != _public_identity(public):
        raise ValueError("receipt-public-input-mismatch")
    trace = _decode_trace(receipt["trace"])
    graph_payload = {
        "nodes": receipt["trace"]["graph"]["nodes"],
        "edges": receipt["trace"]["graph"]["edges"],
        "version": trace.graph.version,
        "threshold": trace.threshold, "max_gap": trace.max_gap,
    }
    if (trace.public_raster_sha256 != public["raster_digest"] or
            receipt["raster_sha256"] != public["raster_digest"] or
            list(trace.raster_shape) != list(public["pixels_l8"].shape) or
            list(trace.focus_box) != list(public["focus_box"]) or
            trace.threshold != FROZEN_CONFIG["threshold"] or
            trace.max_gap != FROZEN_CONFIG["max_gap"] or
            trace.max_nodes != FROZEN_CONFIG["max_nodes"] or
            trace.max_pixels != FROZEN_CONFIG["max_pixels"] or
            trace.trace_version != TRACE_VERSION or
            _sha_json(graph_payload) != receipt["graph_sha256"] or
            evidence_digest(trace) != receipt["trace_sha256"] or
            trace.graph.candidate_set_sha256 != receipt["graph_sha256"] or
            len(trace.graph.nodes) != receipt["nodes"] or
            len(trace.graph.edges) != receipt["edges"]):
        raise ValueError("receipt-trace-mismatch")
    decisions = receipt["decisions"]
    node_ids = {n.node_id for n in trace.graph.nodes}
    if ([d["arm"] for d in decisions] != ["A1", "B", "B-shuffle"] or
            any(d["candidate_set_sha256"] != receipt["graph_sha256"] or
                d["version"] != trace.graph.version or
                not set(d["selected_nodes"]) <= node_ids or
                d["action"] not in ("continue", "stop", "hold") for d in decisions)):
        raise ValueError("receipt-decisions-mismatch")
    return trace


def grade_development(prediction, *, expected_prediction_sha256):
    """Grade a saved prediction under an externally retained digest; no inference."""
    if _sha_json(prediction) != expected_prediction_sha256:
        raise ValueError("prediction-digest-mismatch")
    if (prediction["phase"] != "PREDICT" or prediction["arena_version"] != VERSION or
            prediction["development_manifest_sha256"] != DEVELOPMENT_MANIFEST_SHA256 or
            prediction["config"] != FROZEN_CONFIG or
            prediction["config_sha256"] != _sha_json(FROZEN_CONFIG) or
            prediction["pregrade_receipts_sha256"] != _sha_json(prediction["pregrade_receipts"])):
        raise ValueError("prediction-contract-mismatch")
    current = _provenance()
    if any(prediction[key] != current[key] for key in
           ("model_version", "trace_version", "source_file_sha256")):
        raise ValueError("prediction-code-provenance-mismatch")
    inputs = _development_inputs()
    receipts = prediction["pregrade_receipts"]
    if len(receipts) != len(inputs):
        raise ValueError("prediction-case-count-mismatch")
    pending, controls, collision_labels = [], [], {}
    for (index, public, private), receipt in zip(inputs, receipts, strict=True):
        trace = _validate_receipt(receipt, public)
        identity = _sha_json(_public_identity(public))
        collision_labels.setdefault(identity, set()).add(private.expected_action)
        if index is None:
            d = next(d for d in receipt["decisions"] if d["arm"] == "B")
            controls.append({"member_id": private.member_id, "actual": d["action"],
                             "expected": private.expected_action,
                             "correct": d["action"] == private.expected_action})
        else:
            pending.append((index, public, private, trace, receipt))
    if any(len(labels) > 1 for labels in collision_labels.values()):
        raise RuntimeError("unidentifiable-contradictory-public-inputs")
    graded = [_review_dev(private, development_private_arc(index, private), trace, receipt, public)
              for index, public, private, trace, receipt in pending]
    by_arm = {}
    for arm_idx, arm in enumerate(("A1", "B", "B-shuffle")):
        decisions = [row["reviews"][arm_idx] for row in graded]
        by_arm[arm] = {
            "correct_members": sum(d["correct"] for d in decisions), "members": len(decisions),
            "both_correct_pairs": sum(all(graded[2*i+j]["reviews"][arm_idx]["correct"]
                                          for j in range(2)) for i in range(6)),
            "pairs": 6, "holds": sum(d["action"] == "hold" for d in decisions),
            "false_continues": sum(d["action"] == "continue" and d["expected"] == "stop"
                                   for d in decisions),
        }
    stages = ("P-evidence-not-admitted", "target-ownership-unresolved",
              "local-selection-unresolved", "G-correct-relation-absent",
              "R-selection-or-unobserved-path", "action-correct-path-unverified")
    positives = [r for r in graded if r["target_pixels"]]
    return {
        **{k: v for k, v in prediction.items() if k != "phase"},
        "phase": "GRADE", "status": "development-only-stage-audit",
        "prediction_sha256": expected_prediction_sha256,
        "private_reviews": graded, "controls": controls,
        "summary": {"by_arm": by_arm,
                    "b_positive_earliest_blockers": {
                        key: sum(r["reviews"][1]["earliest_blocker"] == key for r in positives)
                        for key in stages}},
        "annotation_scope": "synthetic-program-derived, single author; NO real-art adjudication",
        "unidentifiable_public_input_count": 0,
        "canvas": "NOT RUN", "motor": "NOT RUN", "replay": "NOT RUN",
    }


def run_development_audit():
    """Convenience integration check only; CLI split phases are the evidence path."""
    prediction = predict_development()
    result = grade_development(prediction, expected_prediction_sha256=_sha_json(prediction))
    result["execution_mode"] = "IN_PROCESS_INTEGRATION_CHECK"
    return result


def _write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", action="store_true", required=True)
    parser.add_argument("--phase", choices=("predict", "grade"), required=True)
    parser.add_argument("--prediction", type=Path)
    parser.add_argument("--expected-prediction-sha256")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("refuse-overwrite-evidence")
    if args.phase == "predict":
        if args.prediction or args.expected_prediction_sha256:
            parser.error("predict takes no grading inputs")
        result = predict_development()
    else:
        if not args.prediction or not args.expected_prediction_sha256:
            parser.error("grade requires --prediction and --expected-prediction-sha256")
        result = grade_development(json.loads(args.prediction.read_text(encoding="utf-8")),
                                  expected_prediction_sha256=args.expected_prediction_sha256)
    _write_new(args.out, result)
    print({"phase": result["phase"], "sha256": _sha_json(result),
           "receipts_sha256": result["pregrade_receipts_sha256"],
           "summary": result.get("summary"), "out": str(args.out)})


if __name__ == "__main__":
    main()
