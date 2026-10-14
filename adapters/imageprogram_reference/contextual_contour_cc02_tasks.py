"""CC-02 Arena-owned synthetic tasks. No private oracle enters the public task.

The confirmation grammar is separately authored, pre-registered and NOT scored
while CC-02 v3 development is ongoing. No natural artwork is included.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

VERSION = "arena-contextual-contour-cc02-v1"
FOCUS = (6, 12, 55, 59)


@dataclass(frozen=True)
class PrivateTarget:
    pair_id: str
    member_id: str
    split: str
    family: str
    scene_kind: str
    expected_action: str
    target_region: tuple[int, int, int, int] | None
    excluded_region: tuple[int, int, int, int] | None
    evidence_policy: str


def _line(image, a, b, *, ink=0):
    """Rasterize a finite, endpoint-inclusive 1-pixel polyline segment."""
    x0, y0 = a
    x1, y1 = b
    steps = max(abs(x1 - x0), abs(y1 - y0))
    for j in range(steps + 1):
        alpha = j / max(1, steps)
        x = int(round(x0 + alpha * (x1 - x0)))
        y = int(round(y0 + alpha * (y1 - y0)))
        if not (0 <= x < 72 and 0 <= y < 72):
            raise ValueError("point-out-of-bounds")
        image[y, x] = ink


def _sha(image):
    return hashlib.sha256(image.tobytes()).hexdigest()


def create_development_pair(index):
    """Six hard development pairs; identical local raster, opposite private actions.

    Synthetic task convention: strokes are finite observed marks. Except for an
    explicitly annotated <=8px fragment gap, no invisible ink is presumed.
    This convention CANNOT be assumed for genuine illustrations.
    """
    if type(index) is not int or not 0 <= index < 6:
        raise ValueError("index-out-of-range")
    y = 27 + index
    xoff = index % 2
    case_names = (
        "slanted-successor", "t-junction-successor", "curved-successor",
        "low-contrast-successor", "parallel-neighbor", "branched-successor",
    )
    records = []
    for action in ("continue", "stop"):
        image = np.full((72, 72), 255, dtype=np.uint8)
        _line(image, (10 + xoff, y), (28 + xoff, y))
        _line(image, (33 + xoff, y), (52 + xoff, y))
        # Only peripheral x >= 58 pixels change across pair members.
        if action == "continue":
            if index == 0:
                _line(image, (59, y + 1), (68, y + 5))
            elif index == 1:
                _line(image, (59, y), (69, y))
                _line(image, (64, y), (64, y + 10))
            elif index == 2:
                _line(image, (59, y), (63, y))
                _line(image, (63, y), (69, y + 4))
            elif index == 3:
                _line(image, (59, y), (69, y), ink=218)
            elif index == 4:
                _line(image, (59, y), (69, y))
                _line(image, (59, y + 12), (68, y + 12))
            else:
                _line(image, (59, y), (69, y))
                _line(image, (64, y), (69, y - 5))
                _line(image, (64, y), (69, y + 5))
            target_region = (58, y - 1, 71, y + 11)
            excluded_region = None
        else:
            if index in (0, 1, 2, 3):
                ink = 218 if index == 3 else 0
                _line(image, (60, y + 8), (60, y + 19), ink=ink)
            elif index == 4:
                _line(image, (59, y + 7), (69, y + 7))
                _line(image, (59, y + 12), (68, y + 12))
            else:
                _line(image, (60, y + 7), (69, y + 15))
                _line(image, (63, y + 15), (68, y + 15))
            target_region = None
            excluded_region = (58, y + 5, 71, y + 20)
        family = ("low-contrast" if index == 3 else
                  "junction" if index in (1, 5) else "hard-neighbor")
        public = {
            "format": VERSION, "pixels_l8": image, "focus_box": FOCUS,
            "anchor_px": (10 + xoff + 0.5, y + 0.5),
            "raster_digest": _sha(image), "budget_pixels": 8192,
        }
        private = PrivateTarget(
            f"dev-{index:02d}", f"dev-{index:02d}-{action}",
            "development", family, case_names[index], action,
            target_region, excluded_region, "finite-visible-ink",
        )
        records.append((public, private))
    return tuple(records)


def create_confirmation_pair(index):
    """UNSCORED prospective family of noncardinal arcs, not rotated development.

    Model tuning may never read private labels. Template authorship is not
    evidence of independent natural-source generalization.
    """
    if type(index) is not int or not 0 <= index < 6:
        raise ValueError("index-out-of-range")
    cy = 27 + index
    records = []
    for action in ("continue", "stop"):
        image = np.full((72, 72), 255, dtype=np.uint8)
        _line(image, (11, cy - 4), (27, cy))
        _line(image, (34, cy + 1), (51, cy + 5))
        if action == "continue":
            _line(image, (59, cy + 7), (64, cy + 10))
            _line(image, (64, cy + 10), (69, cy + 10 - index % 3))
            region, excluded = (58, cy + 6, 71, cy + 14), None
        else:
            _line(image, (61, cy - 9), (68, cy - 11))
            _line(image, (61, cy + 16), (69, cy + 18))
            region, excluded = None, (58, cy - 12, 71, cy + 20)
        public = {
            "format": VERSION, "pixels_l8": image, "focus_box": FOCUS,
            "anchor_px": (11.5, cy - 3.5), "raster_digest": _sha(image),
            "budget_pixels": 8192,
        }
        private = PrivateTarget(
            f"conf-{index:02d}", f"conf-{index:02d}-{action}",
            "confirmation", "angled-arc-grammar-v1",
            "noncardinal-arcs", action, region, excluded, "finite-visible-ink",
        )
        records.append((public, private))
    return tuple(records)


def create_controls():
    """Ambiguous/true-stop/context-neutral controls outside six binary pairs."""
    items = []
    for variant in ("ambiguous", "true-stop", "neutral-context"):
        image = np.full((72, 72), 255, dtype=np.uint8)
        _line(image, (10, 35), (28, 35))
        _line(image, (33, 35), (52, 35))
        expected = "hold" if variant == "ambiguous" else "stop"
        if variant == "ambiguous":
            _line(image, (59, 33), (69, 33))
            _line(image, (59, 37), (69, 37))
        if variant == "neutral-context":
            _line(image, (60, 54), (68, 54))
        public = {
            "format": VERSION, "pixels_l8": image, "focus_box": FOCUS,
            "anchor_px": (10.5, 35.5), "raster_digest": _sha(image),
            "budget_pixels": 8192,
        }
        private = PrivateTarget(
            "control-" + variant, "control-" + variant,
            "control", "independent-controls", variant, expected,
            None, None, "ambiguity" if expected == "hold" else "finite-visible-ink",
        )
        items.append((public, private))
    return tuple(items)


def validate_pair(pair):
    if len(pair) != 2:
        raise ValueError("pair-length")
    (a, pa), (b, pb) = pair
    keys = {
        "format", "pixels_l8", "focus_box", "anchor_px",
        "raster_digest", "budget_pixels",
    }
    for public in (a, b):
        if (set(public) != keys or public["pixels_l8"].shape != (72, 72)
                or public["pixels_l8"].dtype != np.uint8):
            raise ValueError("public-contract")
        if public["raster_digest"] != _sha(public["pixels_l8"]):
            raise ValueError("raster-hash-invalid")
    if (pa.pair_id != pb.pair_id or pa.split != pb.split
            or {pa.expected_action, pb.expected_action} != {"continue", "stop"}):
        raise ValueError("invalid-oracle-pair")
    if a["focus_box"] != b["focus_box"] or a["anchor_px"] != b["anchor_px"]:
        raise ValueError("changed-local-task")
    x0, y0, x1, y1 = a["focus_box"]
    a_crop = a["pixels_l8"][y0:y1, x0:x1]
    b_crop = b["pixels_l8"][y0:y1, x0:x1]
    if not np.array_equal(a_crop, b_crop):
        raise ValueError("local-input-not-identical")
    if np.array_equal(a["pixels_l8"], b["pixels_l8"]):
        raise ValueError("context-not-intervened")
    return {
        "pair_id": pa.pair_id, "split": pa.split, "family": pa.family,
        "local_sha256": _sha(a_crop),
        "public_sha256": (a["raster_digest"], b["raster_digest"]),
    }
