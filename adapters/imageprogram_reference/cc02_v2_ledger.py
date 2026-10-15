"""CC-02-V2 strictly-development two-stage prediction and private grading.

PREDICT does not import the private reviewer or inspect returned target fields.
GRADE never imports ImageProgram or executes observe_graph/select. The source
generator is readable and still returns private labels in both stages: this is
process-level segregation, not cryptographic separation or blinded annotation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

PROTOCOL = "cc02-v2-development-ledger-v1"
EXPECTED_DEV_MANIFEST = "4d796ebc0467153a119a233724e6f9cfc1b8509b65c77bd101c31da3a3d61dcd"
FIXED = {"threshold": 200, "max_gap": 8, "max_nodes": 16,
         "max_pixels": 8192, "max_edges": 64}
ARMS = ("A1", "B", "B-shuffle")
EXPECTED_MODEL_VERSION = "contextual-contour-cc01-v2"
REQUIRED_CASES = {f"dev-{i:02d}-m{j}" for i in range(6) for j in range(2)}
REQUIRED_CASES |= {f"control-{i}" for i in range(3)}


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(obj: object) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def checkout_sha(path: Path) -> str:
    """A real git commit is mandatory; unknown/local-mirror is not reproducible."""
    sha = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"],
                                  stderr=subprocess.DEVNULL, text=True).strip()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("unverified-40-hex-checkout-sha")
    dirty = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"],
                                    stderr=subprocess.DEVNULL, text=True)
    if dirty.strip():
        raise ValueError("dirty-source-checkout")
    return sha


def write_once(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def public_cases():
    """Never return target labels in the prediction interface."""
    from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
        create_controls,
        create_development_pair,
    )
    for i in range(6):
        for j, (public, _unused_private) in enumerate(create_development_pair(i)):
            yield f"dev-{i:02d}-m{j}", public
    for i, (public, _unused_private) in enumerate(create_controls()):
        yield f"control-{i}", public


def predict() -> dict:
    import numpy as np
    import imageprogram
    from imageprogram.models.contextual_contour_cc01 import (
        VERSION,
        observe_graph,
        select,
    )
    from adapters.imageprogram_reference.contextual_contour_cc02_tasks import VERSION as AV

    if VERSION != EXPECTED_MODEL_VERSION:
        raise ValueError("frozen-v2-required")
    arena_root = Path(__file__).resolve().parents[2]
    model_root = Path(imageprogram.__file__).resolve().parents[2]
    head_arena, head_model = checkout_sha(arena_root), checkout_sha(model_root)
    predictions: list[dict] = []
    for case_key, public in public_cases():
        image = public["pixels_l8"]
        if hashlib.sha256(image.tobytes()).hexdigest() != public["raster_digest"]:
            raise ValueError("public-raster-digest-mismatch")
        graph = observe_graph(image, public["focus_box"], threshold=FIXED["threshold"],
                              max_gap=FIXED["max_gap"], max_nodes=FIXED["max_nodes"],
                              max_pixels=FIXED["max_pixels"])
        snap = asdict(graph)
        arms = ARMS if case_key.startswith("dev-") else ("B",)
        for arm in arms:
            decision = select(graph, public["anchor_px"], arm=arm,
                              max_edges=FIXED["max_edges"])
            predictions.append({
                "case_key": case_key, "public_sha256": public["raster_digest"],
                "graph": snap, "decision": asdict(decision),
            })
    payload = {
        "protocol": PROTOCOL, "split": "development-and-controls-only",
        "model_version": VERSION, "arena_version": AV,
        "model_checkout_sha": head_model, "arena_checkout_sha": head_arena,
        "python": sys.version.split()[0], "numpy": np.__version__,
        "config": FIXED, "predictions": predictions,
        "case_count": len(REQUIRED_CASES), "prediction_count": len(predictions),
        "confirmation": "NOT_RUN", "real_art": "NOT_RUN",
        "private_review": "NOT_LOADED_IN_PREDICTION_PROCESS",
    }
    payload["receipt_sha256"] = sha256(payload)
    return payload


def verify_receipt(payload: dict, *, expected_sha: str) -> dict:
    """Fail closed on edited/partial/non-development evidence."""
    if (payload.get("receipt_sha256") != expected_sha or len(expected_sha) != 64
            or sha256({k: v for k, v in payload.items() if k != "receipt_sha256"})
            != expected_sha):
        raise ValueError("receipt-integrity-or-external-sha-mismatch")
    if (payload.get("protocol") != PROTOCOL or
            payload.get("split") != "development-and-controls-only" or
            payload.get("model_version") != EXPECTED_MODEL_VERSION or
            payload.get("config") != FIXED or
            payload.get("confirmation") != "NOT_RUN" or
            payload.get("prediction_count") != 39 or
            payload.get("case_count") != 15):
        raise ValueError("unexpected-run-contract")
    expected_keys = {(f"dev-{i:02d}-m{j}", arm)
                     for i in range(6) for j in range(2) for arm in ARMS}
    expected_keys |= {(f"control-{i}", "B") for i in range(3)}
    rows = payload.get("predictions", [])
    observed = [(r["case_key"], r["decision"]["arm"]) for r in rows]
    if set(observed) != expected_keys or len(observed) != len(expected_keys):
        raise ValueError("prediction-keys-duplicate-or-missing")
    if any(r["decision"]["candidate_set_sha256"] !=
           r["graph"]["candidate_set_sha256"] for r in rows):
        raise ValueError("decision-graph-sha-mismatch")
    for row in rows:
        graph = row["graph"]
        reference = {
            "nodes": graph["nodes"], "edges": graph["edges"],
            "version": graph["version"], "threshold": FIXED["threshold"],
            "max_gap": FIXED["max_gap"],
        }
        if sha256(reference) != graph["candidate_set_sha256"]:
            raise ValueError("graph-content-sha-mismatch")
    return {(r["case_key"], r["decision"]["arm"]): r for r in rows}


def private_cases():
    from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
        create_controls, create_development_pair, validate_pair,
    )
    pair_manifests = []
    for i in range(6):
        pair = create_development_pair(i)
        pair_manifests.append(validate_pair(pair))
        for j, (public, private) in enumerate(pair):
            yield f"dev-{i:02d}-m{j}", public, private, pair_manifests
    for i, (public, private) in enumerate(create_controls()):
        yield f"control-{i}", public, private, pair_manifests


def excluded_paths(case_key: str, private: object):
    """Source-derived DEV distractor strokes only; no confirmation oracle."""
    from adapters.imageprogram_reference.cc02_arc_review import _arc_points
    if case_key.startswith("control-"):
        if private.scene_kind == "neutral-context":
            return _arc_points(((60, 54), (68, 54)))
        return set()  # ambiguous alternatives have no single forbidden branch
    i = int(case_key[4:6])
    y = 27 + i
    if private.expected_action == "stop":
        if i in (0, 1, 2, 3):
            paths = (((60, y + 8), (60, y + 19)),)
        elif i == 4:
            paths = (((59, y + 7), (69, y + 7)),
                     ((59, y + 12), (68, y + 12)))
        else:
            paths = (((60, y + 7), (69, y + 15)),
                     ((63, y + 15), (68, y + 15)))
    elif i == 1:
        paths = (((64, y), (64, y + 10)),)
    elif i == 4:
        paths = (((59, y + 12), (68, y + 12)),)
    elif i == 5:
        paths = (((64, y), (69, y - 5)), ((64, y), (69, y + 5)))
    else:
        paths = ()
    excluded = set()
    for path in paths:
        excluded.update(_arc_points(path))
    return excluded


def _ns_graph(snapshot: dict) -> SimpleNamespace:
    return SimpleNamespace(
        nodes=tuple(SimpleNamespace(**n) for n in snapshot["nodes"]),
        edges=tuple(SimpleNamespace(**e) for e in snapshot["edges"]),
        candidate_set_sha256=snapshot["candidate_set_sha256"],
    )


def private_grade(payload: dict, *, expected_sha: str) -> dict:
    """Imports no Model module. Saved frozen graph + public replay only."""
    from adapters.imageprogram_reference.cc02_arc_review import (
        _arc_points,
        _verified_node_supports,
        audit_continue,
        development_continue_annotation,
    )
    registry = verify_receipt(payload, expected_sha=expected_sha)
    if checkout_sha(Path(__file__).resolve().parents[2]) != payload["arena_checkout_sha"]:
        raise ValueError("arena-checkout-sha-changed-between-stages")

    manifest = []
    reviews = []
    arc_reviews = []
    for case_key, public, private, manifest_state in private_cases():
        manifest = manifest_state
        sha = public["raster_digest"]
        if hashlib.sha256(public["pixels_l8"].tobytes()).hexdigest() != sha:
            raise ValueError("public-raster-digest-mismatch")
        arms = ARMS if case_key.startswith("dev-") else ("B",)
        for arm in arms:
            receipt = registry[(case_key, arm)]
            if receipt["public_sha256"] != sha:
                raise ValueError("receipt-source-raster-mismatch")
            graph = _ns_graph(receipt["graph"])
            decision = SimpleNamespace(**receipt["decision"])
            supports = _verified_node_supports(public, graph, FIXED["threshold"],
                                               FIXED["max_nodes"])
            exclusion = excluded_paths(case_key, private)
            target = set()
            if private.expected_action == "continue":
                i = int(case_key[4:6])
                target = _arc_points(development_continue_annotation(i).path)
                exclusion -= target  # crossing point is shared, not a forbidden branch
            if any(public["pixels_l8"][y, x] == 255 for x, y in exclusion):
                raise ValueError("private-excluded-ink-not-visible")
            context_ids = {n.node_id for n in graph.nodes if n.region == "context"}
            focus_ids = {n.node_id for n in graph.nodes if n.region == "focus"}
            target_hits = {k for k in context_ids if supports[k] & target}
            contaminating = {k for k in context_ids if supports[k] & exclusion}
            suspicious_edges = sum(
                e.kind == "possible_continuation"
                and ((e.src in focus_ids and e.dst in contaminating)
                     or (e.dst in focus_ids and e.src in contaminating))
                for e in graph.edges
            )
            target_support = set().union(*(supports[k] for k in target_hits)) if target_hits else set()
            purity = (len(target_support & target) / len(target_support)
                      if target_support else None)
            row = {
                "case_key": case_key, "arm": arm, "source_scene": private.scene_kind,
                "expected": private.expected_action, "actual": decision.action,
                "correct_action": decision.action == private.expected_action,
                "reason": decision.reason,
                "public_sha256": sha, "graph_sha256": graph.candidate_set_sha256,
                "node_count": len(graph.nodes), "edge_count": len(graph.edges),
                "excluded_pixels": len(exclusion),
                "excluded_pixels_in_context": len(set().union(
                    *(supports[k] & exclusion for k in context_ids)) if context_ids else set()),
                "target_support_purity_exact_px": (
                    round(purity, 6) if purity is not None else None),
                "candidate_nodes_touching_exclusion": len(contaminating),
                "suspected_forbidden_focus_context_edges": suspicious_edges,
                "wrong_confident_continue": (
                    decision.action == "continue"
                    and private.expected_action != "continue"),
            }
            reviews.append(row)
            if private.expected_action == "continue" and arm == "B":
                arc_reviews.append(audit_continue(public, graph, decision,
                                   development_continue_annotation(int(case_key[4:6]))))
    if sha256(manifest) != EXPECTED_DEV_MANIFEST:
        raise ValueError("frozen-development-manifest-mismatch")
    scores = {}
    for arm in ARMS:
        subset = [r for r in reviews if r["arm"] == arm and
                  r["case_key"].startswith("dev-")]
        pairs = [[r for r in subset if r["case_key"].startswith(f"dev-{i:02d}-")]
                 for i in range(6)]
        scores[arm] = {
            "correct_members": sum(r["correct_action"] for r in subset),
            "total_members": len(subset),
            "both_correct_pairs": sum(len(pair) == 2 and
                                      all(r["correct_action"] for r in pair)
                                      for pair in pairs),
            "wrong_confident_continues": sum(r["wrong_confident_continue"] for r in subset),
            "suspected_forbidden_links": sum(r["suspected_forbidden_focus_context_edges"]
                                            for r in subset),
        }
    controls = [r for r in reviews if r["case_key"].startswith("control-")]
    return {
        "protocol": PROTOCOL, "status": "development-and-controls-graded",
        "receipt_sha256": expected_sha,
        "model_checkout_sha": payload["model_checkout_sha"],
        "arena_checkout_sha": payload["arena_checkout_sha"],
        "development_manifest_sha256": EXPECTED_DEV_MANIFEST,
        "evidence_provenance": "source-derived-synthetic-unblinded",
        "human_adjudication": "NOT_RUN",
        "confirmation": "NOT_SCORED", "real_art": "NOT_RUN",
        "score": scores, "controls_correct": sum(r["correct_action"] for r in controls),
        "controls_total": len(controls),
        "stage_counts": {stage: sum(a["diagnostic_stage"] == stage for a in arc_reviews)
                         for stage in sorted({a["diagnostic_stage"] for a in arc_reviews})},
        "all_member_reviews": reviews,
        "continue_arc_reviews": arc_reviews,
        "selected_path_edges": "UNAVAILABLE_IN_FROZEN_V2",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--predict", action="store_true")
    group.add_argument("--grade", action="store_true")
    parser.add_argument("--receipts", type=Path,
                        help="Existing output from a separate --predict invocation")
    parser.add_argument("--receipt-sha", type=str,
                        help="SHA printed at --predict time and externally preserved")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.predict:
        result = predict()
    else:
        if args.receipts is None or not args.receipt_sha:
            parser.error("--grade requires --receipts and --receipt-sha")
        result = private_grade(json.loads(args.receipts.read_text("utf-8")),
                               expected_sha=args.receipt_sha)
    write_once(args.out, result)
    print(json.dumps({
        "mode": "predict" if args.predict else "grade", "out": str(args.out),
        "receipt_sha256": result.get("receipt_sha256"),
        "stage_counts": result.get("stage_counts"), "score": result.get("score"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
