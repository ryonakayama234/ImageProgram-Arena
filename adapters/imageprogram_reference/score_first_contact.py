"""Independent Arena-side measurement of real ART-1 P1 episode frames.

Metrics are reference ink precision/recall with a predeclared 2px raster
alignment tolerance, plus actual ink outside E. This is not an art critic.
Never sends the source image to ImageProgram or includes source bytes in output.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


class FirstContactScoreError(ValueError):
    pass


def _dilate(binary: np.ndarray, radius: int = 2) -> np.ndarray:
    h, w = binary.shape
    padded = np.pad(binary, radius, mode="constant")
    result = np.zeros_like(binary)
    for dy in range(2 * radius + 1):
        for dx in range(2 * radius + 1):
            result |= padded[dy:dy + h, dx:dx + w]
    return result


def score_mask(target: np.ndarray, drawn: np.ndarray, allowed: np.ndarray) -> dict:
    if target.shape != drawn.shape or allowed.shape != target.shape:
        raise FirstContactScoreError("target, drawn, and editable masks must align")
    if target.dtype != np.bool_ or drawn.dtype != np.bool_ or allowed.dtype != np.bool_:
        raise FirstContactScoreError("expected boolean binary masks")
    outside = int(np.count_nonzero(drawn & ~allowed))
    candidate = drawn & allowed
    reference = target & allowed
    ink = int(candidate.sum())
    target_ink = int(reference.sum())
    if target_ink == 0:
        raise FirstContactScoreError("scored ROI has no reference ink")
    correct = int((candidate & _dilate(reference)).sum())
    found = int((reference & _dilate(candidate)).sum())
    precision = correct / ink if ink else 0.0
    recall = found / target_ink
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision_2px": precision, "recall_2px": recall, "f1_2px": f1,
            "target_ink_px": target_ink, "drawn_ink_px": ink,
            "drawn_ink_outside_editable_px": outside}


def score_first_contact(public_task_dir: Path, episodes_dir: Path,
                        out_file: Path) -> dict:
    """Recompute the target from allowed crop; audit actual source episode outputs.

    The policy knows the permitted crop for restore_reference. This evaluator is
    separate code and consumes *terminal P1 episode frames*, not model guesses.
    """
    public_task_dir = Path(public_task_dir)
    task = json.loads((public_task_dir / "task.json").read_text(encoding="utf-8"))
    from hashlib import sha256
    crop_bytes = (public_task_dir / "reference_roi.png").read_bytes()
    if task["reference_roi_sha256"] != "sha256:" + sha256(crop_bytes).hexdigest():
        raise FirstContactScoreError("ROI file digest mismatch")
    with Image.open(public_task_dir / "reference_roi.png") as im:
        if im.mode != "L" or im.format != "PNG":
            raise FirstContactScoreError("invalid normalized reference crop")
        crop = im.copy()
    width, height = task["canvas_size_px"]
    x0, y0, x1, y1 = task["editable_bbox"]
    if crop.size != (x1 - x0, y1 - y0):
        raise FirstContactScoreError("reference crop size inconsistent with public task")
    whole = Image.new("L", (width, height), 255)
    whole.paste(crop, (x0, y0))
    # Bilinear conversion is part of this v0 benchmark definition.
    target = np.array(whole.resize((256, 256), Image.Resampling.BILINEAR)) < 145
    allowed_input = Image.new("L", (width, height), 0)
    ImageDraw.Draw(allowed_input).rectangle((x0, y0, x1 - 1, y1 - 1), fill=255)
    allowed = np.array(allowed_input.resize((256, 256), Image.Resampling.NEAREST)) > 0
    result = {"format": "art1-first-contact-independent-scoring-v0",
              "reference_threshold_L8": 145, "rendered_threshold_L8": 250,
              "alignment_tolerance_px": 2, "scores": {}}
    initial_hashes = set()
    for label in ("fine", "coarse", "noop"):
        ep = Path(episodes_dir) / f"{label}_episode"
        if (ep / "final.png").is_symlink() or not (ep / "final.png").is_file():
            raise FirstContactScoreError("missing or symlink final frame")
        record = json.loads((ep / "result.json").read_text())
        if record.get("status") != "program_exhausted":
            raise FirstContactScoreError(f"{label}: incomplete P1 episode")
        initial_hashes.add(record.get("initial_state_hash"))
        with Image.open(ep / "final.png") as frame:
            if frame.mode != "L" or frame.size != (256, 256):
                raise FirstContactScoreError("unexpected rendered World frame")
            drawn = np.array(frame) < 250
        metrics = score_mask(target, drawn, allowed)
        if metrics["drawn_ink_outside_editable_px"] != 0:
            raise FirstContactScoreError(f"{label}: added ink outside editable ROI")
        if label == "noop" and metrics["drawn_ink_px"] != 0:
            raise FirstContactScoreError("no-op should not deposit ink")
        result["scores"][label] = {
            **metrics, "accepted_actions": record["accepted_actions"],
            "state_hash": record["final_state_hash"],
            "motor_commands": record["costs"]["motor_commands"],
        }
    if len(initial_hashes) != 1:
        raise FirstContactScoreError("different initial states in comparator arms")
    if result["scores"]["noop"]["f1_2px"] != 0.0:
        raise FirstContactScoreError("no-op wrongly got positive reference match")
    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--public-roi", type=Path, required=True)
    p.add_argument("--episodes", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = score_first_contact(a.public_roi, a.episodes, a.out)
    print(json.dumps({"status": "INDEPENDENT_SCORE_READY", "scores": result["scores"]},
                     indent=2))


if __name__ == "__main__":
    main()
