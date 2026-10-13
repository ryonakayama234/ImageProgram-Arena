"""Reproducible development-only four-family synthetic actual-World pilot.

This is not a held-out suite. Analytic source is used only by Arena after
public proposals have been saved and canonical episodes have been executed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from adapters.imageprogram_reference.public_reference_roi_v1 import (
    export_permitted_roi_v1,
)
from adapters.imageprogram_reference.smooth_contour_review_v0 import review
from adapters.imageprogram_reference.source_artwork import ingest_local_source


def run(output):
    import imageprogram
    from imageprogram.experiments.smooth_contour_session_v0 import run as run_session

    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    t = np.linspace(0, 1, 1501)
    cases = {
        "arc": np.column_stack([25+110*np.sin(t*np.pi/2), 25+110*(1-np.cos(t*np.pi/2))]),
        "s": np.column_stack([25+110*t, 80+35*np.sin(t*2*np.pi)]),
        "gentle": np.column_stack([25+110*t, 25+105*t+9*np.sin(t*np.pi)]),
        "straight": np.column_stack([25+110*t, 30+70*t]),
    }
    model_root = Path(imageprogram.__file__).resolve().parents[2]
    arena_root = Path(__file__).resolve().parents[2]
    provenance = {"split": "development", "reserved": False, "source_generation": "smooth-demo-v0"}
    for key, checkout in (("model", model_root), ("arena", arena_root)):
        provenance[key+"_sha"] = subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        provenance[key+"_dirty"] = bool(subprocess.check_output(
            ["git", "-C", str(checkout), "status", "--porcelain"], text=True).strip())
    rows = []
    for key, path in cases.items():
        d = root/key
        d.mkdir()
        image = Image.new("L", (640, 640), 255)
        ImageDraw.Draw(image).line([tuple(p*4) for p in path], fill=0, width=4)
        image.resize((160, 160), Image.Resampling.LANCZOS).save(d/"source.png")
        manifest = ingest_local_source(d/"source.png", editable_bbox=(0, 0, 160, 160),
                                       source_family="smooth-development-"+key,
                                       rights="procedural test source")
        (d/"source_manifest.json").write_text(json.dumps(manifest))
        export_permitted_roi_v1(d/"source.png", d/"source_manifest.json", d/"public_roi")
        centre = (path*1.5+8).tolist()
        (d/"private_centre.json").write_text(json.dumps(centre))
        result = run_session(d/"public_roi", d/"session")
        evaluated = review(d/"session", source_path_world_px=centre)
        (d/"private_review.json").write_text(json.dumps(evaluated, indent=2))
        rows.append(dict(id=key, report=result, review=evaluated))
    summary = dict(provenance=provenance, results=rows, capability_pass=False,
                   held_out_evaluation=False, learned_skill=False, human_accepted=False)
    (root/"summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.out)
    print({r["id"]: {k: v["synthetic_profile_gate_pass"]
                     for k, v in r["review"]["arms"].items()} for r in result["results"]})


if __name__ == "__main__":
    main()
