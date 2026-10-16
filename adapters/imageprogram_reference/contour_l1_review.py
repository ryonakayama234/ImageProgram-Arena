"""CC02 L0/L1 blind review packets: public raster only, no G output or private labels.

Reviewers independently judge visible support (L0) and contour relation (L1).
L2 artist/goal intent is deliberately NOT_EVALUABLE from these public rasters.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from xml.sax.saxutils import escape

VERSION = "cc02-blind-l0-l1-review-v1"
L0 = {"supported", "contradicted", "uncertain", "pending"}
L1 = {"same_visible_curve", "different_visible_curve", "ambiguous", "not_evaluable", "pending"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def load_verified(path: Path, sha256: str):
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise ValueError("invalid-external-sha256")
    data = json.loads(path.read_text(encoding="utf-8"))
    if digest(data) != sha256:
        raise ValueError("altered-anchored-artifact")
    return data


def make_packet(observation: dict, scope: dict):
    if (scope.get("protocol") != VERSION
            or observation.get("protocol") != "arena-g1-observed-p02-v1"
            or observation.get("stage") != "observe"
            or observation.get("original_confirmation") != "NOT_RUN"
            or digest(observation) != scope.get("observation_sha256")):
        raise ValueError("observation-or-scope-drift")
    expected_source = scope.get("source_heads")
    if observation.get("source", {}).get("heads") != expected_source:
        raise ValueError("source-head-drift")
    rows = observation.get("rows", [])
    if len(rows) != 27 or len({r["task_id"] for r in rows}) != 27:
        raise ValueError("scene-universe-drift")
    by_task = {r["task_id"]: r for r in rows}
    tasks = []
    for req in scope["tasks"]:
        row = by_task[req["task_id"]]
        nodes = row["fragments"]
        if (row["fragment_sha256"] != req["fragment_sha256"]
                or digest(nodes) != row["fragment_sha256"]):
            raise ValueError("fragment-digest-drift")
        ids = [x["node_id"] for x in nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate-fragment-ids")
        pairs = [list(x) for x in combinations(ids, 2)]
        if pairs != req["pairs"]:
            raise ValueError("pair-universe-drift")
        if len(row["p02_arms"]) != len(nodes):
            raise ValueError("arm-fragment-contract-drift")
        tasks.append({
            "task_id": row["task_id"],
            "raster_sha256": row["raster_sha256"],
            "focus_box": row["focus"],
            "fragment_sha256": row["fragment_sha256"],
            "nodes": [{"id": n["node_id"], "endpoint_a": n["endpoint_a"],
                       "endpoint_b": n["endpoint_b"],
                       "support_xy": arm["support_xy"]}
                      for n, arm in zip(nodes, row["p02_arms"])],
            "pairs": pairs,
            "raw_image": f'{row["task_id"]}.png',
            "geometry_overlay": f'{row["task_id"]}-geometry.svg',
        })
    if sum(len(x["pairs"]) for x in tasks) != 10 or len(tasks) != 3:
        raise ValueError("review-universe-drift")
    return {"protocol": VERSION, "observation_sha256": scope["observation_sha256"],
            "original_confirmation": "NOT_RUN", "review_status": "UNREVIEWED",
            "l2_intent": "NOT_EVALUABLE", "tasks": tasks,
            "method": "public-pixels-and-unlabeled-p02-support; no-G-output; no-source-label"}


def blank_response(packet, reviewer_id: str):
    if not reviewer_id or len(reviewer_id) > 64:
        raise ValueError("invalid-reviewer-id")
    return {"protocol": VERSION, "packet_sha256": digest(packet),
            "reviewer_id": reviewer_id,
            "l0": {f'{t["task_id"]}:{n["id"]}': "pending"
                   for t in packet["tasks"] for n in t["nodes"]},
            "l1": {f'{t["task_id"]}:{a}:{b}': "pending"
                   for t in packet["tasks"] for a, b in t["pairs"]},
            "l2_intent": "not_evaluable"}


def combine(packet, a, b):
    if packet.get("protocol") != VERSION or packet.get("review_status") != "UNREVIEWED":
        raise ValueError("not-a-frozen-review-packet")
    template = blank_response(packet, "template")
    results = []
    for label, ans in (("a", a), ("b", b)):
        if (ans.get("protocol") != VERSION
                or ans.get("packet_sha256") != digest(packet)
                or ans.get("l2_intent") != "not_evaluable"
                or ans.get("reviewer_id") in (None, "", "template")
                or set(ans.get("l0", {})) != set(template["l0"])
                or set(ans.get("l1", {})) != set(template["l1"])
                or not set(ans["l0"].values()) <= L0
                or not set(ans["l1"].values()) <= L1):
            raise ValueError(f"invalid-{label}-response")
    if a["reviewer_id"] == b["reviewer_id"]:
        raise ValueError("reviewers-not-independent-identities")
    for task in packet["tasks"]:
        for src, dst in task["pairs"]:
            key = f'{task["task_id"]}:{src}:{dst}'
            values = (a["l1"][key], b["l1"][key])
            node_keys = (f'{task["task_id"]}:{src}', f'{task["task_id"]}:{dst}')
            support = all(ans["l0"][k] == "supported" for ans in (a, b) for k in node_keys)
            if "pending" in values or any(ans["l0"][k] == "pending"
                                          for ans in (a, b) for k in node_keys):
                state = "PENDING"
            elif not support:
                state = "UNRESOLVED_L0"
            elif values[0] != values[1]:
                state = "DISPUTED"
            elif values[0] in ("ambiguous", "not_evaluable"):
                state = "UNRESOLVED_L1"
            else:
                state = "CONSENSUS"
            results.append({"pair_id": key, "status": state,
                            "agreed_l1": values[0] if state == "CONSENSUS" else None})
    return {"protocol": VERSION, "packet_sha256": digest(packet),
            "reviewers": [a["reviewer_id"], b["reviewer_id"]], "rows": results,
            "counts": dict(Counter(x["status"] for x in results)),
            "original_confirmation": "NOT_RUN", "l2_intent": "NOT_EVALUABLE",
            "g0_g1_scores": "NOT_RUN", "blind_human_annotation": "NOT_COMPLETE"
            if any(x["status"] != "CONSENSUS" for x in results) else "TWO_REVIEWERS_AGREED_ON_L1_ONLY"}


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(data, f, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")


def overlay_svg(task, shape):
    # Labels and colors are unrelated to source truth or G0/G1 output.
    h, w = shape
    tags = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w*6}" height="{h*6}" viewBox="0 0 {w} {h}">',
            f'<image href="{task["raw_image"]}" width="{w}" height="{h}"/>']
    colors = ("#db4437", "#2466e0", "#11965a", "#bd60ba", "#f09012")
    for j, node in enumerate(task["nodes"]):
        color = colors[j % len(colors)]
        for x, y in node["support_xy"]:
            tags.append(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{color}" opacity="0.5"/>')
        x, y = node["endpoint_a"]
        tags.append(f'<text x="{x}" y="{y}" font-size="3" fill="{color}">{escape(node["id"])}</text>')
    return "\n".join((*tags, "</svg>")) + "\n"


def prepare_artifacts(observation, scope, out):
    packet = make_packet(observation, scope)
    # Use exactly public case generation; never import source-private grade labels.
    from PIL import Image

    from adapters.imageprogram_reference.branch_contour_p02_trial import _public_cases

    public = list(_public_cases())
    if len(public) != len(observation["rows"]):
        raise ValueError("public-raster-count-drift")
    images = {}
    for row, (family, case_id, case) in zip(observation["rows"], public):
        raster = case["pixels_l8"]
        if (row["family"] != family or row["case_id"] != case_id
                or row["raster_sha256"] != hashlib.sha256(raster.tobytes()).hexdigest()):
            raise ValueError("public-raster-sha-drift")
        images[row["task_id"]] = raster
    out.mkdir(parents=True, exist_ok=False)
    for task in packet["tasks"]:
        raster = images[task["task_id"]]
        Image.fromarray(raster).save(out / task["raw_image"])
        (out / task["geometry_overlay"]).write_text(
            overlay_svg(task, raster.shape), encoding="utf-8")
    write_new(out / "packet.json", packet)
    write_new(out / "reviewer-A.json", blank_response(packet, "reviewer-A"))
    write_new(out / "reviewer-B.json", blank_response(packet, "reviewer-B"))
    return digest(packet)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("prepare", "reconcile"))
    parser.add_argument("--observation", type=Path)
    parser.add_argument("--observation-sha256")
    parser.add_argument("--scope", type=Path)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--review-a", type=Path)
    parser.add_argument("--review-b", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.phase == "prepare":
        if not args.observation or not args.observation_sha256 or not args.scope:
            parser.error("prepare-requires-observation-sha-and-frozen-scope")
        if any((args.packet, args.review_a, args.review_b)):
            parser.error("prepare-rejects-reviewer-inputs")
        obs = load_verified(args.observation, args.observation_sha256)
        scope = json.loads(args.scope.read_text(encoding="utf-8"))
        if scope.get("observation_sha256") != args.observation_sha256:
            parser.error("external-scope-hash-mismatch")
        print("BLIND_PACKET_SHA256", prepare_artifacts(obs, scope, args.out))
    else:
        if not all((args.packet, args.review_a, args.review_b)):
            parser.error("reconcile-requires-packet-and-two-reviewers")
        if any((args.observation, args.observation_sha256, args.scope)):
            parser.error("reconcile-rejects-observation-private-inputs")
        data = combine(json.loads(args.packet.read_text(encoding="utf-8")),
                       json.loads(args.review_a.read_text(encoding="utf-8")),
                       json.loads(args.review_b.read_text(encoding="utf-8")))
        write_new(args.out, data)
        print("BLIND_RECONCILIATION_SHA256", digest(data))


if __name__ == "__main__":
    main()
