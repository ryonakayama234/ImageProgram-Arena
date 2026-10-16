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
        ("slanted-positive", (((14., 1.), (21., 6.)),)),
        ("curved-positive", (((14., -1.), (21., -5.)),)),
        ("straight-positive", (((14., 0.), (24., 0.)),)),
        ("parallel-negative", (((10., 5.), (21., 5.)),)),
        ("crossing-negative", (((6., 3.), (6., -3.)),)),
        ("side-negative", (((15., 6.), (23., 11.)),)),
        ("competing-unknown", (((14., 1.), (22., 4.)), ((14., -1.), (22., -4.)))),
        ("junction-zero-unknown", (((10., 0.), (20., 0.)),)),
    )
    return tuple(PublicTask(label, tuple([_fragment("a", *origin)] + [
        _fragment(chr(98 + j), *ends) for j, ends in enumerate(others)
    ])) for label, others in families)
