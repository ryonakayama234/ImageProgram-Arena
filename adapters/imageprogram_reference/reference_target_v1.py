"""ART-1 Arena v1: independent ROI-local World target, placement and masks.

No ImageProgram module is imported. This is an independent evaluator-side
implementation. v0 full-source resize and v0 results remain unchanged.
"""
from __future__ import annotations

import hashlib
import io
import math
from dataclasses import dataclass

import numpy as np
from PIL import Image

from adapters.imageprogram_reference.score_first_contact import (
    FirstContactScoreError,
    score_mask,
)

TASK_FORMAT = "arena-public-reference-roi-v1"
TRANSFORM = "art1-roi-contain-v1"
SAMPLING = "inverse_world_pixel_centre_to_roi_bilinear_v1"
SCORE_FORMAT = "art1-first-contact-independent-scoring-v1"
WORLD_SIZE = 256
MARGIN = 8


@dataclass(frozen=True, slots=True)
class IndependentPlacementV1:
    width: int
    height: int

    def __post_init__(self):
        if (
            type(self.width) is not int or type(self.height) is not int
            or not (12 <= self.width <= 256 and 12 <= self.height <= 256)
            or self.width * self.height > 65536
        ):
            raise FirstContactScoreError("ROI v1 dimensions unsupported")

    @property
    def scale(self) -> float:
        return min(240 / self.width, 240 / self.height)

    @property
    def offset(self) -> tuple[float, float]:
        s = self.scale
        return (128 - s * self.width / 2, 128 - s * self.height / 2)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        x, y = self.offset
        return (x, y, x + self.width * self.scale, y + self.height * self.scale)

    def editable_mask(self) -> np.ndarray:
        x0, y0, x1, y1 = self.bounds
        # Half-open rectangle; membership is tested at World pixel centres.
        xs = np.arange(256, dtype=np.float64) + 0.5
        ys = np.arange(256, dtype=np.float64) + 0.5
        return (
            (xs[None, :] >= x0) & (xs[None, :] < x1)
            & (ys[:, None] >= y0) & (ys[:, None] < y1)
        )

    def public_placement(self) -> dict:
        x, y = self.offset
        return {
            "transform_version": TRANSFORM,
            "method": "fit_contain",
            "world_px": [256, 256],
            "margin_world_px": MARGIN,
            "scale_world_px_per_source_px": self.scale,
            "offset_world_px": [x, y],
        }


def make_public_v1_task(crop_png: bytes) -> dict:
    """Allowlisted policy metadata for an already authorized L8 local crop.

    This helper is not source intake or rights authorization; it must only be
    called *after* Arena has verified the management manifest and source bytes.
    """
    with Image.open(io.BytesIO(crop_png)) as image:
        if image.format != "PNG" or image.mode != "L":
            raise FirstContactScoreError("v1 crop must be normalized PNG L8")
        width, height = image.size
        image.load()
    placement = IndependentPlacementV1(width, height)
    return {
        "format": TASK_FORMAT,
        "mode": "restore_reference",
        "reference_visibility": "permitted_reference_processed",
        "reference_roi_sha256": "sha256:" + hashlib.sha256(crop_png).hexdigest(),
        "roi_width_px": width,
        "roi_height_px": height,
        "placement": placement.public_placement(),
        "sampling": SAMPLING,
        "region_semantics": {
            "focus": "local_roi",
            "observation": "local_roi",
            "editable": "world_E",
            "scored": "world_E",
            "protected": "world_complement_E",
        },
    }


def _validate_public_view(task: dict, crop_png: bytes) -> tuple[np.ndarray, IndependentPlacementV1]:
    # No ignored/private fields may travel in the model-visible task.
    expected = {
        "format", "mode", "reference_visibility", "reference_roi_sha256",
        "roi_width_px", "roi_height_px", "placement", "sampling", "region_semantics",
    }
    if set(task) != expected or task["format"] != TASK_FORMAT:
        raise FirstContactScoreError("v1 public task has private, missing or wrong-version fields")
    if task["mode"] != "restore_reference" or task["reference_visibility"] != "permitted_reference_processed":
        raise FirstContactScoreError("v1 reference visibility mismatch")
    if task["sampling"] != SAMPLING:
        raise FirstContactScoreError("unknown v1 sampling")
    if task["reference_roi_sha256"] != "sha256:" + hashlib.sha256(crop_png).hexdigest():
        raise FirstContactScoreError("v1 reference digest mismatch")
    with Image.open(io.BytesIO(crop_png)) as image:
        if image.format != "PNG" or image.mode != "L":
            raise FirstContactScoreError("v1 crop must be PNG L8")
        arr = np.asarray(image.copy())
    height, width = arr.shape
    placement = IndependentPlacementV1(width, height)
    if (task["roi_width_px"], task["roi_height_px"]) != (width, height):
        raise FirstContactScoreError("v1 dimensions do not match crop")
    if task["placement"] != placement.public_placement():
        raise FirstContactScoreError("v1 transform version/geometry mismatch")
    if task["region_semantics"] != make_public_v1_task(crop_png)["region_semantics"]:
        raise FirstContactScoreError("v1 region semantics mismatch")
    return arr, placement


def _bilinear_white_outside(
    source: np.ndarray, placement: IndependentPlacementV1
) -> np.ndarray:
    """Inverse-mapped L8 target, independently sampled with white off-ROI."""
    ox, oy = placement.offset
    inv = 1.0 / placement.scale
    xs = (np.arange(256, dtype=np.float64) + 0.5 - ox) * inv - 0.5
    ys = (np.arange(256, dtype=np.float64) + 0.5 - oy) * inv - 0.5
    xx, yy = np.meshgrid(xs, ys)
    ix = np.floor(xx).astype(np.int32)
    iy = np.floor(yy).astype(np.int32)
    result = np.zeros((256, 256), dtype=np.float64)
    # Four bilinear neighbors; invalid source coordinates sample white.
    for row_offset in (0, 1):
        for col_offset in (0, 1):
            px, py = ix + col_offset, iy + row_offset
            weight = (
                (1.0 - np.abs(xx - px))
                * (1.0 - np.abs(yy - py))
            )
            inside = (
                (px >= 0) & (px < placement.width)
                & (py >= 0) & (py < placement.height)
            )
            sampled = np.full((256, 256), 255.0)
            sampled[inside] = source[py[inside], px[inside]]
            result += weight * sampled
    return np.floor(np.clip(result, 0, 255) + 0.5).astype(np.uint8)


def target_and_masks_v1(
    task: dict, permitted_crop_png: bytes
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Target ink, E and P. Never reuse Model's sampling or prediction code."""
    source, placement = _validate_public_view(task, permitted_crop_png)
    editable = placement.editable_mask()
    target = (_bilinear_white_outside(source, placement) < 145) & editable
    return target, editable, ~editable


def score_terminal_v1(
    task: dict, permitted_crop_png: bytes, terminal_world_l8: np.ndarray
) -> dict:
    """Independent terminal score, NOT full canonical Episode/replay verification."""
    target, editable, _ = target_and_masks_v1(task, permitted_crop_png)
    if terminal_world_l8.dtype != np.uint8 or terminal_world_l8.shape != (256, 256):
        raise FirstContactScoreError("final World raster must be 256x256 L8")
    drawn = terminal_world_l8 < 250
    metrics = score_mask(target, drawn, editable)
    if metrics["drawn_ink_outside_editable_px"]:
        raise FirstContactScoreError("protected area received new ink")
    return {
        "format": SCORE_FORMAT,
        "transform_version": TRANSFORM,
        "reference_threshold_L8": 145,
        "world_threshold_L8": 250,
        "alignment_metric": "Linf-Chebyshev",
        "alignment_tolerance_world_px": 2,
        "alignment_tolerance_reference_px": 2 / IndependentPlacementV1(
            task["roi_width_px"], task["roi_height_px"]
        ).scale,
        **metrics,
    }
