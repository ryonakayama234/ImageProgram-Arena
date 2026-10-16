"""Synthetic public fixed-Fragment G1-only development bank (NO raster perception)."""
from __future__ import annotations

import math
from dataclasses import dataclass

from imageprogram.models.contextual_contour_cc01 import Fragment

VERSION = "arena-cc02-g1-fixed-geometry-dev-v0"


def _fragment(name, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    norm = math.hypot(dx, dy)
    return Fragment(name, a, b, (dx / norm, dy / norm), 11, 0.0, "focus")


@dataclass(frozen=True)
class PublicTask:
    task_id: str
    fragments: tuple[Fragment, ...]
    evidence_split: str = "synthetic-geometry-dev"


def public_tasks() -> tuple[PublicTask, ...]:
    origin = ((0., 0.), (10., 0.))
    families = (
        ("gdev-00", (((14., 1.), (21., 6.)),)),
        ("gdev-01", (((14., -1.), (21., -5.)),)),
        ("gdev-02", (((14., 0.), (24., 0.)),)),
        ("gdev-03", (((10., 5.), (21., 5.)),)),
        ("gdev-04", (((6., 3.), (6., -3.)),)),
        ("gdev-05", (((15., 6.), (23., 11.)),)),
        ("gdev-06", (((14., 1.), (22., 4.)), ((14., -1.), (22., -4.)))),
        ("gdev-07", (((10., 0.), (20., 0.)),)),
    )
    return tuple(PublicTask(label, tuple([_fragment("a", *origin)] + [
        _fragment(chr(98 + j), *ends) for j, ends in enumerate(others)
    ])) for label, others in families)
