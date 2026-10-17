"""Arena-only, post-prediction scorer for CC-02-R visible open contour paths.

This consumes saved public graphs, immutable decisions, and private acceptance.
It never imports ImageProgram or runs a model. Research-only: no drawing/Skill.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

VERSION = "arena-visible-contour-path-grade-v0"
SATISFIED = "satisfied"
REASONS = {"verified_visible_endpoint", "ambiguous", "observation_insufficient",
           "budget_exhausted", "execution_error"}
GOALS = {"satisfied", "unsatisfied", "unknown"}
KINDS = {"unique_path", "ambiguous", "observation_insufficient", "budget_exhausted"}


def digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load(path: Path, expected_sha: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if digest(data) != expected_sha:
        raise ValueError("anchored-canonical-sha-mismatch:" + path.name)
    if not isinstance(data, dict):
        raise ValueError("not-an-object")
    return data


def exact_keys(value: dict, keys: set[str], name: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(name + "-contract")


def walk(edges: dict, start: str, path: list[str]) -> str:
    if not isinstance(path, list) or not all(isinstance(p, str) for p in path):
        raise ValueError("invalid-path-type")
    if len(set(path)) != len(path):
        raise ValueError("repeated-edge")
    node = start
    visited = {start}
    for edge_id in path:
        if edge_id not in edges:
            raise ValueError("unknown-edge:" + edge_id)
        a, b = edges[edge_id]
        if node != a and node != b:
            raise ValueError("disconnected-path")
        node = b if node == a else a
        if node in visited:
            raise ValueError("non-open-path")
        visited.add(node)
    return node


def grade(public: dict, private: dict, prediction: dict,
          public_sha: str, private_sha: str, prediction_sha: str) -> dict:
    exact_keys(public, {"protocol", "cases", "split"}, "public")
    exact_keys(private, {"protocol", "public_sha256", "cases"}, "private")
    exact_keys(prediction, {"protocol", "public_sha256", "cases"}, "prediction")
    if (public["protocol"] != VERSION or private["protocol"] != VERSION
            or prediction["protocol"] != VERSION
            or private["public_sha256"] != public_sha
            or prediction["public_sha256"] != public_sha):
        raise ValueError("protocol-or-parent-hash-mismatch")
    if public["split"] not in {"development", "confirmation"}:
        raise ValueError("invalid-split")
    if not isinstance(public["cases"], list) or not public["cases"]:
        raise ValueError("missing-public-cases")
    def index(rows, title):
        if not isinstance(rows, list):
            raise ValueError(title + "-not-list")
        ids = [row.get("case_id") for row in rows if isinstance(row, dict)]
        if len(ids) != len(rows) or len(ids) != len(set(ids)) or not all(
                isinstance(x, str) and x for x in ids):
            raise ValueError(title + "-duplicate-or-missing-id")
        return dict(zip(ids, rows))
    pubs, privs, preds = (index(public["cases"], "public"),
                         index(private["cases"], "private"),
                         index(prediction["cases"], "prediction"))
    if pubs.keys() != privs.keys() or pubs.keys() != preds.keys():
        raise ValueError("missing-or-extra-case")
    rows = []
    for case_id, case in pubs.items():
        exact_keys(case, {"case_id", "family_id", "raster_sha256", "start_node",
                          "nodes", "edges", "candidate_graph_sha256"}, "public-case")
        exact_keys(privs[case_id], {"case_id", "kind", "allowed_edge_paths",
                                    "expected_goal", "expected_reasons"}, "private-case")
        exact_keys(preds[case_id], {"case_id", "candidate_graph_sha256", "candidate_paths",
                                    "selected_path", "goal_status", "termination_reason",
                                    "endpoint_evidence", "work_units"}, "prediction-case")
        decision = preds[case_id]
        truth = privs[case_id]
        if (not isinstance(case["nodes"], list) or len(set(case["nodes"])) != len(case["nodes"])
                or not isinstance(case["start_node"], str)
                or case["start_node"] not in case["nodes"]):
            raise ValueError("invalid-public-nodes")
        edgelist = case["edges"]
        if not isinstance(edgelist, list) or any(
                not isinstance(e, dict) or set(e) != {"id", "u", "v"} for e in edgelist):
            raise ValueError("invalid-edges")
        edges = {e["id"]: (e["u"], e["v"]) for e in edgelist}
        if (len(edges) != len(edgelist) or any(a not in case["nodes"] or b not in case["nodes"]
                                              or a == b for a, b in edges.values())
                or digest({"nodes": case["nodes"], "edges": edgelist}) != case["candidate_graph_sha256"]
                or decision["candidate_graph_sha256"] != case["candidate_graph_sha256"]):
            raise ValueError("candidate-graph-integrity")
        if (truth["kind"] not in KINDS or truth["expected_goal"] not in GOALS
                or not truth["expected_reasons"] or any(
                    v not in REASONS for v in truth["expected_reasons"])):
            raise ValueError("private-acceptance-contract")
        allowed = truth["allowed_edge_paths"]
        if not isinstance(allowed, list):
            raise ValueError("allowed-paths-type")
        if truth["kind"] == "unique_path" and (not allowed or not all(p for p in allowed)):
            raise ValueError("unique-path-missing-oracle")
        if truth["kind"] != "unique_path" and allowed:
            raise ValueError("control-has-private-path")
        for p in allowed:
            walk(edges, case["start_node"], p)
        candidates = decision["candidate_paths"]
        if not isinstance(candidates, list) or any(not p for p in candidates):
            raise ValueError("invalid-candidates")
        for p in candidates:
            walk(edges, case["start_node"], p)
        path = decision["selected_path"]
        if path is not None:
            endpoint = walk(edges, case["start_node"], path)
            if path not in candidates:
                raise ValueError("selection-not-proposed")
        else:
            endpoint = None
        if (decision["goal_status"] not in GOALS or decision["termination_reason"] not in REASONS
                or type(decision["work_units"]) not in {int, float} or decision["work_units"] < 0):
            raise ValueError("invalid-decision-status-or-work")
        evidence = decision["endpoint_evidence"]
        if evidence is not None:
            exact_keys(evidence, {"node_id", "observation_sha256", "unresolved_continuations"},
                       "endpoint-evidence")
            if (evidence["node_id"] != endpoint or evidence["observation_sha256"] != case["raster_sha256"]
                    or type(evidence["unresolved_continuations"]) is not int
                    or evidence["unresolved_continuations"] < 0):
                raise ValueError("invalid-public-endpoint-evidence")
        if decision["goal_status"] == SATISFIED and (path is None or evidence is None
                or evidence["unresolved_continuations"] != 0
                or decision["termination_reason"] != "verified_visible_endpoint"):
            raise ValueError("unsupported-satisfied-claim")
        available = any(p in candidates for p in allowed) if allowed else None
        path_correct = path in allowed if allowed else None
        reason_correct = decision["termination_reason"] in truth["expected_reasons"]
        goal_correct = decision["goal_status"] == truth["expected_goal"]
        if truth["kind"] == "unique_path":
            # A strict non-prefix is a false join; a prefix is a missed continuation.
            permitted_edges = set().union(*(set(p) for p in allowed))
            wrong_edges = sorted(set(path or []) - permitted_edges)
            wrong_join = bool(path) and not any(
                p[:len(path)] == path for p in allowed)
            correct = bool(path_correct and reason_correct and goal_correct)
        else:
            wrong_edges = []
            wrong_join = False
            correct = bool(path is None and reason_correct and goal_correct)
        rows.append({"case_id": case_id, "family_id": case["family_id"],
                     "kind": truth["kind"], "candidate_available": available,
                     "path_correct": path_correct, "goal_correct": goal_correct,
                     "reason_correct": reason_correct, "false_join": wrong_join,
                     "wrong_edges": wrong_edges,
                     "premature_satisfied": decision["goal_status"] == SATISFIED and not correct,
                     "success": correct, "work_units": decision["work_units"]})
    totals = Counter()
    for row in rows:
        totals["cases"] += 1
        totals["unique" if row["kind"] == "unique_path" else "control"] += 1
        for metric in ("success", "false_join", "premature_satisfied"):
            totals[metric] += int(row[metric])
        if row["candidate_available"] is not None:
            totals["candidate_available"] += int(row["candidate_available"])
        totals["work_units"] += row["work_units"]
    return {"protocol": VERSION, "stage": "grade", "split": public["split"],
            "public_sha256": public_sha, "private_sha256": private_sha,
            "prediction_sha256": prediction_sha, "results": rows, "counts": dict(totals),
            "qualification": "synthetic-path-identity-not-natural-art-or-drawing",
            "original_confirmation": "NOT_RUN" if public["split"] == "development" else "EVALUATED",
            "model_was_reinvoked": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("public", "private", "prediction"):
        parser.add_argument("--" + name, type=Path, required=True)
        parser.add_argument("--" + name + "-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    public = load(a.public, a.public_sha256)
    private = load(a.private, a.private_sha256)
    prediction = load(a.prediction, a.prediction_sha256)
    report = grade(public, private, prediction, a.public_sha256,
                   a.private_sha256, a.prediction_sha256)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(report["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
