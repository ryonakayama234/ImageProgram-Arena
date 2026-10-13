"""Prepare source-private context/focus tasks and run the paired development pilot."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from adapters.imageprogram_reference.partial_contour_review_v0 import review
from adapters.imageprogram_reference.public_reference_roi_v1 import (
    export_permitted_roi_v1,
)
from adapters.imageprogram_reference.source_artwork import ingest_local_source


def prepare_task(source, focus_global_box, output, *, context_px=12, rights="unknown"):
    from PIL import Image, ImageOps

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with Image.open(source) as image:
        w, h = ImageOps.exif_transpose(image).size
    if (not isinstance(focus_global_box, tuple) or len(focus_global_box) != 4
            or any(type(v) is not int for v in focus_global_box)
            or type(context_px) is not int or not 2 <= context_px <= 24):
        raise ValueError("bounded source-private rectangle/context required")
    x0, y0, x1, y1 = focus_global_box
    window = (max(0, x0-context_px), max(0, y0-context_px),
              min(w, x1+context_px), min(h, y1+context_px))
    box = [x0-window[0], y0-window[1], x1-window[0], y1-window[1]]
    manifest = ingest_local_source(source, editable_bbox=window,
        source_family="partial-contour-development", rights=rights)
    (output/"source_manifest.json").write_text(json.dumps(manifest, indent=2))
    (output/"private_focus.json").write_text(json.dumps(dict(focus_global_box=focus_global_box,
                                                          context_px=context_px)))
    export_permitted_roi_v1(source, output/"source_manifest.json", output/"public_roi")
    focus = dict(format="partial-contour-focus-context-v0", focus_box_local_px=box,
                 target_rule="dominant-unbranched-segment", threshold_l8=145,
                 dominance_ratio=1.35, focus_halo_world_px=2.0)
    (output/"public_roi/focus.json").write_text(json.dumps(focus, indent=2))
    return output/"public_roi"


def run(source, focus_boxes, output, *, rights="unknown"):
    import imageprogram
    from imageprogram.experiments.partial_contour_session_v0 import run as run_session

    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    rows = []
    provenance = dict(split="development", held_out=False, rights=rights)
    for key, checkout in (("model", Path(imageprogram.__file__).resolve().parents[2]),
                          ("arena", Path(__file__).resolve().parents[2])):
        provenance[key+"_sha"] = subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        provenance[key+"_dirty"] = bool(subprocess.check_output(
            ["git", "-C", str(checkout), "status", "--porcelain"], text=True).strip())
    for i, box in enumerate(focus_boxes):
        d = root/f"roi-{i:02d}"
        try:
            public = prepare_task(source, tuple(box), d, rights=rights)
            report = run_session(public, d/"session")
            evaluation = review(d/"session")
            row = dict(id=f"roi-{i:02d}", status="processed", report=report, review=evaluation)
            (d/"private_review.json").write_text(json.dumps(evaluation, indent=2))
        except ValueError as exc:
            row = dict(id=f"roi-{i:02d}", status="failed", reason=str(exc))
        rows.append(row)
        print(row["id"], row["status"],
              {k: v["status"] for k, v in row.get("report", {}).get("arms", {}).items()},
              flush=True)
    summary = dict(provenance=provenance, results=rows, capability_pass=False,
                   human_accepted=False, learned_skill=False)
    (root/"summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--private-boxes", type=Path, required=True,
                   help="private JSON array of source-global rectangles")
    p.add_argument("--rights", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    run(args.source, json.loads(args.private_boxes.read_text()), args.out, rights=args.rights)


if __name__ == "__main__":
    main()
