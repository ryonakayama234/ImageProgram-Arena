"""Independent focus/context Canvas diagnostics; no fitted-path witness.

Full-focus F1 is a diagnostic when the crop contains other lines or shading.
Without independently specified target annotations, correct selection and
real-line quality are unknown, even after successful legal execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from adapters.imageprogram_reference.continuity_v0 import count_8_connected_components
from adapters.imageprogram_reference.reference_target_v1 import (
    IndependentPlacementV1,
    target_and_masks_v1,
)
from adapters.imageprogram_reference.score_first_contact import score_mask

VERSION = "arena-partial-contour-review-v0"


def review(session):
    root = Path(session)
    task = json.loads((root/"task.json").read_text())
    png = (root/"reference_roi.png").read_bytes()
    target, _, _ = target_and_masks_v1(task, png)
    placement = IndependentPlacementV1(task["roi_width_px"], task["roi_height_px"])
    focus = json.loads((root/"focus.json").read_text())
    source_box = focus["focus_box_local_px"]
    ox, oy = placement.offset
    scale = placement.scale
    bounds = (ox+source_box[0]*scale, oy+source_box[1]*scale,
              ox+source_box[2]*scale, oy+source_box[3]*scale)
    halo = 2.0
    context = placement.bounds
    allowed = (max(bounds[0]-halo, context[0]), max(bounds[1]-halo, context[1]),
               min(bounds[2]+halo, context[2]), min(bounds[3]+halo, context[3]))
    xs, ys = np.arange(256)+.5, np.arange(256)+.5
    def mask(box):
        x0, y0, x1, y1 = box
        return ((xs[None, :] >= x0) & (xs[None, :] < x1)
                & (ys[:, None] >= y0) & (ys[:, None] < y1))
    focus_mask, allowed_mask = mask(bounds), mask(allowed)
    report = json.loads((root/"report.json").read_text())
    if (report["decision_sha256"] != "sha256:"+hashlib.sha256(
            (root/"public_decisions.json").read_bytes()).hexdigest()
            or not np.allclose(allowed, report["allowed_bounds_world_px"], atol=1e-12)):
        raise ValueError("public decision or independent allowed region mismatch")
    arms = {}
    for arm in ("isolated", "partial", "observed_trace"):
        info = report["arms"][arm]
        if "episode" not in info:
            arms[arm] = dict(status="not_executed", reason=info.get("reason"))
            continue
        episode = root/arm
        manifest = json.loads((episode/"manifest.json").read_text())
        for path, digest in manifest["files"].items():
            p = (episode/path).resolve()
            if not p.is_relative_to(episode.resolve()) or not p.is_file():
                raise ValueError("invalid episode path")
            if "sha256:"+hashlib.sha256(p.read_bytes()).hexdigest() != digest:
                raise ValueError("episode digest mismatch")
        raster = np.asarray(Image.open(episode/"final.png"))
        if raster.shape != (256, 256) or raster.dtype != np.uint8:
            raise ValueError("canonical L8 Canvas required")
        actual = json.loads((episode/"result.json").read_text())
        ink = raster < 250
        diagnostic = score_mask(target, ink, focus_mask)
        outside = int(np.count_nonzero(ink & ~allowed_mask))
        arms[arm] = dict(status=actual["status"], protected_ink_px=outside,
                         connected_components=count_8_connected_components(ink & allowed_mask),
                         whole_focus_shape_diagnostic=diagnostic,
                         diagnostic_is_target_selection_pass=False,
                         target_selection="unknown-no-independent-target-annotation",
                         line_quality="unknown-no-independent-target-annotation",
                         artifact_hashes_verified=True, costs=actual["costs"],
                         producer_replay_verified=info.get("replay_verified", False),
                         diagnostic_only=arm == "observed_trace",
                         legal_execution_gate=bool(actual["status"] == "program_exhausted"
                             and actual["costs"]["strokes"] == 1 and outside == 0
                             and info.get("replay_verified", False)))
    return dict(format=VERSION, arms=arms, human_accepted=False, learned_skill=False,
                observation_window_distinct_from_focus=True, capability_pass=False)
