"""Independent actual-PNG review. No ImageProgram or public fitted path import.

Analytic centre paths, when available, are management-private evaluation data.
For real artwork without independent centre annotations, quality is unknown.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from adapters.imageprogram_reference.continuity_v0 import count_8_connected_components
from adapters.imageprogram_reference.line_integrity_v0 import evaluate_line_integrity_v0
from adapters.imageprogram_reference.reference_target_v1 import (
    score_terminal_v1,
    target_and_masks_v1,
)

VERSION = "arena-smooth-contour-review-v0"


def review(session, *, source_path_world_px=None):
    root = Path(session)
    task = json.loads((root/"task.json").read_text())
    png = (root/"reference_roi.png").read_bytes()
    _, editable, _ = target_and_masks_v1(task, png)
    report = json.loads((root/"report.json").read_text())
    decisions_path = root/"public_decisions.json"
    if report["extraction_status"] != "extracted":
        return dict(format=VERSION, status="unsupported", reason=report.get("reason"), arms={})
    if report["decision_sha256"] != "sha256:"+hashlib.sha256(decisions_path.read_bytes()).hexdigest():
        raise ValueError("public decision digest changed")
    arms = {}
    for arm in ("rdp", "curve"):
        info = report["arms"].get(arm, {})
        if "episode" not in info:
            arms[arm] = dict(status="not_executed", reason=info.get("reason", "missing-arm"))
            continue
        episode = root/arm
        manifest = json.loads((episode/"manifest.json").read_text())
        for path, digest in manifest["files"].items():
            candidate = (episode/path).resolve()
            if not candidate.is_relative_to(episode.resolve()) or not candidate.is_file():
                raise ValueError("invalid episode file")
            if "sha256:"+hashlib.sha256(candidate.read_bytes()).hexdigest() != digest:
                raise ValueError("episode file digest mismatch")
        raster = np.asarray(Image.open(episode/"final.png").convert("L"))
        if raster.shape != (256, 256):
            raise ValueError("unexpected actual Canvas dimensions")
        result = json.loads((episode/"result.json").read_text())
        shape = score_terminal_v1(task, png, raster)
        ink = raster < 250
        outside = int(np.count_nonzero(ink & ~editable))
        quality = dict(status="unknown", reason="no-independent-real-centre-annotation",
                       line_integrity_pass=False)
        endpoints = None
        if source_path_world_px is not None:
            quality = evaluate_line_integrity_v0(
                raster, source_path_world_px=source_path_world_px, editable_mask=editable)
            # Add explicit whole-contour endpoint coverage, since the existing
            # normal-section evaluator excludes the first/last 8 World pixels.
            y, x = np.nonzero(ink & editable)
            ink_points = np.column_stack([x+0.5, y+0.5])
            endpoints = [float(np.linalg.norm(ink_points-np.asarray(p), axis=1).min())
                         if len(ink_points) else None
                         for p in (source_path_world_px[0], source_path_world_px[-1])]
        arms[arm] = dict(status=result["status"], shape=shape, integrity=quality,
                         connected_components=count_8_connected_components(ink & editable),
                         protected_ink_px=outside, endpoint_ink_distance_world_px=endpoints,
                         costs=result["costs"], artifact_hashes_verified=True,
                         producer_replay_verified=info.get("replay_verified", False),
                         centre_annotation_source="private-analytic" if source_path_world_px
                         is not None else "none", whole_artwork_appearance_pass=False)
        arms[arm]["synthetic_profile_gate_pass"] = bool(
            source_path_world_px is not None and result["status"] == "program_exhausted"
            and shape["f1_2px"] >= 0.95 and quality.get("line_integrity_pass", False)
            and endpoints is not None and all(v is not None and v <= 2.0 for v in endpoints)
            and outside == 0 and info.get("replay_verified", False))
    return dict(format=VERSION, status="reviewed", arms=arms,
                centre_path_policy_visible=False, human_accepted=False,
                learned_skill=False, full_capability_pass=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--private-centre", type=Path)
    args = parser.parse_args()
    centre = json.loads(args.private_centre.read_text()) if args.private_centre else None
    result = review(args.session, source_path_world_px=centre)
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
