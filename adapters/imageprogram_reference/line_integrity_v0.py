"""Evaluator-private actual-raster diagnostics for one thin smooth contour.

This module does not import ImageProgram or inspect candidate Program/stroke
counts. The centre path belongs to Arena's independently prepared source.
It is a bounded style profile, not universal aesthetic judgment.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from adapters.imageprogram_reference.continuity_v0 import count_8_connected_components

VERSION = "arena-line-integrity-v0"
PROFILE = "thin-smooth-open-contour-v0"


@dataclass(frozen=True)
class IntegrityThresholdsV0:
    max_integrated_width_world_px: float = 1.65
    max_thick_section_fraction: float = 0.02
    max_multiple_section_fraction: float = 0.02
    max_centroid_second_difference_world_px: float = 1.4
    min_observed_section_fraction: float = 0.97

    def __post_init__(self):
        values = tuple(asdict(self).values())
        if any(
            isinstance(x, bool)
            or not isinstance(x, (int, float))
            or not math.isfinite(x)
            for x in values
        ):
            raise ValueError("finite numeric line-integrity thresholds required")
        if not (
            1.1 <= values[0] <= 3
            and 0 <= values[1] <= 0.1
            and 0 <= values[2] <= 0.1
            and 0.5 <= values[3] <= 3
            and 0.9 <= values[4] <= 1
        ):
            raise ValueError("line-integrity thresholds outside bounded profile")


def _source_samples(points):
    points = np.asarray(points, dtype=float)
    if (
        points.ndim != 2
        or points.shape[1] != 2
        or len(points) < 2
        or not np.isfinite(points).all()
    ):
        raise ValueError("finite ordered source polyline required")
    if (
        np.any(points < 0)
        or np.any(points > 256)
        or np.linalg.norm(points[0] - points[-1]) < 12
    ):
        raise ValueError("open source within World required")
    lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
    if np.any(lengths <= 0):
        raise ValueError("source has duplicate vertices")
    arc = np.r_[0.0, np.cumsum(lengths)]
    if not 32 <= arc[-1] <= 480:
        raise ValueError("source length unsupported")
    sample_arc = np.arange(8.0, arc[-1] - 8.0, 1.0)
    xy = np.column_stack([np.interp(sample_arc, arc, points[:, k]) for k in (0, 1)])
    before = np.column_stack(
        [np.interp(sample_arc - 3.0, arc, points[:, k]) for k in (0, 1)]
    )
    after = np.column_stack(
        [np.interp(sample_arc + 3.0, arc, points[:, k]) for k in (0, 1)]
    )
    direction = after - before
    norm = np.linalg.norm(direction, axis=1)
    if np.any(norm < 1e-8):
        raise ValueError("source direction ambiguous")
    tangent = direction / norm[:, None]
    separation = np.linalg.norm(xy[:, None, :] - xy[None, :, :], axis=2)
    nonlocal_pairs = np.abs(sample_arc[:, None] - sample_arc[None, :]) > 24
    if np.any(nonlocal_pairs & (separation < 12)):
        raise ValueError("overlapping normal-section neighbourhoods unsupported")
    return xy, np.column_stack([-tangent[:, 1], tangent[:, 0]])


def _bilinear_ink(raster, points):
    # Image pixels are located at centre i+0.5. Samples outside are white.
    x, y = points[..., 0] - 0.5, points[..., 1] - 0.5
    ix, iy = np.floor(x).astype(int), np.floor(y).astype(int)
    ink = np.zeros(x.shape)
    for dx in (0, 1):
        for dy in (0, 1):
            cols, rows = ix + dx, iy + dy
            valid = (cols >= 0) & (cols < 256) & (rows >= 0) & (rows < 256)
            values = np.zeros(x.shape)
            values[valid] = (255.0 - raster[rows[valid], cols[valid]]) / 255.0
            ink += values * (1 - np.abs(x - cols)) * (1 - np.abs(y - rows))
    return ink


def evaluate_line_integrity_v0(
    raster: np.ndarray,
    *,
    source_path_world_px,
    editable_mask: np.ndarray,
    thresholds: IntegrityThresholdsV0 | None = None,
    profile: str = PROFILE,
) -> dict:
    if profile != PROFILE:
        return dict(
            format=VERSION,
            status="unsupported",
            reason="unsupported-line-intent-profile",
            line_integrity_pass=False,
            policy_visible=False,
        )
    thresholds = thresholds or IntegrityThresholdsV0()
    if not isinstance(thresholds, IntegrityThresholdsV0):
        raise ValueError("typed thresholds required")
    if raster.shape != (256, 256) or raster.dtype != np.uint8:
        raise ValueError("canonical L8 raster required")
    if editable_mask.shape != (256, 256) or editable_mask.dtype != np.bool_:
        raise ValueError("canonical editable mask required")
    common = dict(
        format=VERSION,
        profile=PROFILE,
        policy_visible=False,
        thresholds=asdict(thresholds),
        learned=False,
    )
    ink = raster < 250
    outside = int(np.count_nonzero(ink & ~editable_mask))
    components = count_8_connected_components(ink & editable_mask)
    try:
        xy, normals = _source_samples(source_path_world_px)
    except ValueError as exc:
        return dict(
            **common, status="unknown", reason=str(exc), line_integrity_pass=False
        )
    offsets = np.arange(-6.0, 6.001, 0.25)
    sections = _bilinear_ink(
        raster, xy[:, None, :] + normals[:, None, :] * offsets[None, :, None]
    )
    width = np.trapezoid(sections, offsets, axis=1)
    observed = width > 0.25
    centroid = np.full(len(width), np.nan)
    centroid[observed] = (
        np.trapezoid(sections * offsets, offsets, axis=1)[observed] / width[observed]
    )
    occupied = sections >= 0.2
    peaks = occupied[:, 0].astype(int) + np.count_nonzero(
        occupied[:, 1:] & ~occupied[:, :-1], axis=1
    )
    # 4px on either side: detects residual bends, not target curvature itself.
    valid = observed[:-8] & observed[4:-4] & observed[8:]
    rough = np.abs(centroid[8:] - 2 * centroid[4:-4] + centroid[:-8])
    rough_max = float(np.max(rough[valid])) if valid.any() else None
    observed_fraction = float(observed.mean())
    thick_fraction = float((width > thresholds.max_integrated_width_world_px).mean())
    multiple_fraction = float((peaks > 1).mean())
    reasons = []
    if not ink.any():
        reasons.append("blank")
    if outside:
        reasons.append("protected-ink")
    if components != 1:
        reasons.append("not-one-connected-contour")
    if observed_fraction < thresholds.min_observed_section_fraction:
        reasons.append("incomplete-contour")
    if thick_fraction > thresholds.max_thick_section_fraction:
        reasons.append("excess-width")
    if multiple_fraction > thresholds.max_multiple_section_fraction:
        reasons.append("extra-parallel-ink")
    if rough_max is None:
        reasons.append("unmeasurable-local-direction")
    elif rough_max > thresholds.max_centroid_second_difference_world_px:
        reasons.append("local-bend-or-jitter")
    return dict(
        **common,
        status="measured",
        reason="within-profile" if not reasons else ";".join(reasons),
        line_integrity_pass=not reasons,
        violations=reasons,
        protected_ink_px=outside,
        connected_components=components,
        observed_section_fraction=observed_fraction,
        integrated_width_max_world_px=float(width.max()),
        thick_section_fraction=thick_fraction,
        multiple_section_fraction=multiple_fraction,
        centroid_second_difference_max_world_px=rough_max,
        section_count=len(width),
        endpoint_margin_world_px=8.0,
        section_spacing_world_px=1.0,
        normal_radius_world_px=6.0,
        centroid_offsets_world_px=[
            None if not np.isfinite(v) else float(v) for v in centroid
        ],
        integrated_widths_world_px=width.tolist(),
    )
