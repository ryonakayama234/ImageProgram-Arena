"""Causal ART-1 E1 Review Pack: actual poststroke Eye frame, not n//2.

All files are sourced from one verified immutable private snapshot. Existing
v0 Drawing Session Review Pack and its duplicate-policy are unchanged.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from adapters.imageprogram_reference.continuity_v0 import diagnose_continuity_v0
from adapters.imageprogram_reference.reference_target_v1 import (
    FirstContactScoreError,
    target_and_masks_v1,
)
from adapters.imageprogram_reference.score_feedback_e1_v1 import (
    MODES,
    _frame,
    _json,
    _score_frozen_e1_v1,
    _world_hash,
)
from adapters.imageprogram_reference.verified_e1_snapshot_v1 import snapshot_e1_inputs

FORMAT = "arena-e1-causal-review-v1"


def _png_url(array: np.ndarray, *, scale: int = 2) -> str:
    image = Image.fromarray(array.astype(np.uint8))
    if scale != 1:
        image = image.resize(
            (image.width * scale, image.height * scale),
            Image.Resampling.NEAREST,
        )
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def _overlay(
    target: np.ndarray, before: np.ndarray, after: np.ndarray
) -> np.ndarray:
    """Blue: target. Gray: initial stroke. Green: appended World ink."""
    rgb = np.full((256, 256, 3), 255, dtype=np.uint8)
    rgb[target] = (183, 206, 252)
    rgb[before < 250] = (78, 82, 91)
    rgb[(after < 250) & (before >= 250)] = (33, 151, 111)
    return rgb


def _zoom(array: np.ndarray, appended: np.ndarray) -> np.ndarray:
    """Heuristic visual zoom, *not* a certified pen-tip endpoint estimate."""
    ys, xs = np.where(appended)
    if len(xs) == 0:
        return array
    x, y = int(xs[0]), int(ys[0])
    x0, y0 = max(0, x - 14), max(0, y - 14)
    x1, y1 = min(256, x + 15), min(256, y + 15)
    result = np.full((29, 29, 3), 255, dtype=np.uint8)
    region = array[y0:y1, x0:x1]
    result[:region.shape[0], :region.shape[1]] = region
    return result


def build_causal_e1_review_v1(
    public_dir: Path, sessions_dir: Path, output_dir: Path
) -> dict:
    """One read-only posthoc view of independently re-scored paired evidence."""
    output_dir = Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise FirstContactScoreError("Review Pack output must be a new directory")
    with snapshot_e1_inputs(public_dir, sessions_dir) as pinned:
        scored = _score_frozen_e1_v1(pinned.public_dir, pinned.sessions_dir)
        task = _json(pinned.public_dir / "task.json")
        crop = (pinned.public_dir / "reference_roi.png").read_bytes()
        target, editable, _ = target_and_masks_v1(task, crop)
        summary = _json(pinned.sessions_dir / "summary.json")
        off = summary["episodes"]["feedback_off"]
        on = summary["episodes"]["feedback_on"]
        split = off["first_action_count"]
        receipt = on["decision_receipt"]
        if (
            not isinstance(split, int) or split <= 0
            or on["first_action_count"] != split
            or receipt["initial_action_count"] != split
        ):
            raise FirstContactScoreError("Eye boundary is not bound to paired P1 prefix")
        mid_name = f"frames/{split:06d}.png"
        mid_on = _frame(pinned.sessions_dir / "feedback_on_episode" / mid_name)
        mid_off = _frame(pinned.sessions_dir / "feedback_off_episode" / mid_name)
        if not np.array_equal(mid_on, mid_off):
            raise FirstContactScoreError("on/off decision boundary raster differs")
        if receipt["canvas_image_sha256"] != _world_hash(mid_on):
            raise FirstContactScoreError("review Eye frame hash is not replay bound")
        finals = {}
        images = {}
        for mode in MODES:
            root = pinned.sessions_dir / (mode + "_episode")
            first = _frame(root / "frames/000000.png")
            final = _frame(root / "final.png")
            finals[mode] = final
            images[mode] = {
                "initial": _png_url(first),
                "decision_boundary": (
                    _png_url(mid_on) if mode == "feedback_on" else
                    _png_url(mid_off) if mode == "feedback_off" else None
                ),
                "final": _png_url(final),
            }
        quality = diagnose_continuity_v0(
            target_mask=target,
            editable_mask=editable,
            poststroke_world_l8=mid_on,
            terminal_world_l8=finals["feedback_on"],
        )
        overlay = _overlay(target, mid_on, finals["feedback_on"])
        appended = (finals["feedback_on"] < 250) & (mid_on >= 250)
        visual_overlay = _png_url(overlay)
        visual_zoom = _png_url(_zoom(overlay, appended), scale=8)
        with Image.open(io.BytesIO(crop)) as source:
            reference_url = _png_url(np.asarray(source.convert("RGB")))
        report = {
            "format": FORMAT,
            "policy_visible": False,
            "human_accepted": False,
            "physical_on_off_equivalent": bool(
                np.array_equal(finals["feedback_on"], finals["feedback_off"])
            ),
            "model_actual_eye_decision_frame_index": split,
            "model_actual_eye_frame_id": receipt["canvas_frame_id"],
            "model_actual_eye_world_raster_sha256": _world_hash(mid_on),
            "naive_halfway_frame_index_not_an_eye_frame": (
                len(_json(pinned.sessions_dir / "feedback_on_episode"
                          / "program.json")["actions"]) // 2
            ),
            "source_replay_verified_arms": scored["replay_verified_arms"],
            "delta_f1_on_minus_off": scored["delta_f1_on_minus_off"],
            "f1_2px_by_mode": {
                mode: scored["scores"][mode]["f1_2px"] for mode in MODES
            },
            "continuity": quality,
            "evidence_snapshot": {
                "manifests_sha256": pinned.manifest_digests,
                "task_sha256": pinned.input_digests["public_task"],
                "reference_png_sha256": pinned.input_digests["public_reference_png"],
            },
        }
        # No output files are created before all checks and source replay pass.
        frames = []
        for mode in MODES:
            items = images[mode]
            cells = []
            for title, src in (
                ("initial frame 0", items["initial"]),
                (f"actual Eye boundary frame {split}", items["decision_boundary"]),
                ("terminal", items["final"]),
            ):
                if src is None:
                    cells.append("<div class='frame'><em>not acquired by noop</em></div>")
                else:
                    cells.append(
                        "<div class='frame'><img alt='" + html.escape(title) + "' src='"
                        + src + "'><small>" + html.escape(title) + "</small></div>"
                    )
            frames.append(
                "<section><h2>" + html.escape(mode) + "</h2><div class='frames'>"
                + "".join(cells) + "</div></section>"
            )
        title = "ART-1 E1 causal boundary & continuity Review Pack"
        html_text = (
            "<!doctype html><html lang='en'><meta charset='utf-8'><title>"
            + title + "</title><style>"
            "body{font:16px sans-serif;margin:2rem;color:#24303d;}"
            ".frames{display:flex;gap:1rem;flex-wrap:wrap}.frame{display:flex;"
            "flex-direction:column;align-items:center;border:1px solid #aaa;"
            "padding:8px}.frame img{max-width:280px;image-rendering:pixelated;}"
            "small{margin-top:6px}.details{background:#f4f6f8;padding:1rem;}"
            "</style><h1>" + title + "</h1>"
            "<p>This is a posthoc Arena-only view. It is NOT Model Eye input, "
            "human acceptance, or evidence of learning.</p>"
            "<div class='details'>Actual Eye poststroke boundary: action "
            + str(split) + ", frame " + html.escape(receipt["canvas_frame_id"])
            + ". Old n//2 would display "
            + str(report["naive_halfway_frame_index_not_an_eye_frame"])
            + ".<p>F1 improvement: "
            + str(report["delta_f1_on_minus_off"])
            + "; strict continuity: " + html.escape(quality["status"])
            + "; connected components (final): "
            + str(quality["terminal_8_connected_components"])
            + "; raster blank gap (px): "
            + str(quality["minimum_initial_added_blank_gap_px"])
            + "</p></div>"
            + "".join(frames)
            + "<h2>Arena-only target and correction overlay</h2>"
            "<p>Blue = reference; gray = actual poststroke ink; "
            "green = ink appended after Eye observation. Zoom centers on first "
            "new raster pixel, not a certified pen endpoint.</p>"
            "<div class='frames'><div class='frame'><img alt='reference ROI' src='"
            + reference_url + "'><small>permitted reference ROI</small></div>"
            "<div class='frame'><img alt='Arena retrospective overlay' src='"
            + visual_overlay + "'><small>posthoc target/ink overlay</small></div>"
            "<div class='frame'><img alt='heuristic junction zoom' src='"
            + visual_zoom + "'><small>heuristic 8x zoom</small></div></div>"
            "</html>"
        )
    output_dir.mkdir(parents=True)
    (output_dir / "index.html").write_text(html_text, encoding="utf-8")
    (output_dir / "continuity_diagnostic.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-roi", required=True, type=Path)
    parser.add_argument("--sessions", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = build_causal_e1_review_v1(args.public_roi, args.sessions, args.out)
    print(json.dumps({
        "format": report["format"],
        "decision_frame_index": report["model_actual_eye_decision_frame_index"],
        "continuity": report["continuity"]["status"],
        "human_accepted": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
