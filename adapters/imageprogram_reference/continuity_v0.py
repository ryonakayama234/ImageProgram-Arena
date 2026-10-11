"""Independent ART-1 E1 v0 raster connectivity diagnostics.

This is a *new* strict diagnostic. It does not change the frozen v1
two-world-pixel tolerant F1 score. It is applied only after verified P1 replay.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from adapters.imageprogram_reference.reference_target_v1 import FirstContactScoreError

FORMAT = "arena-e1-continuity-diagnostic-v0"
WORLD_SHAPE = (256, 256)
INK_THRESHOLD = 250
NEIGHBORS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1), (0, 1),
    (1, -1), (1, 0), (1, 1),
)


def _binary(mask: np.ndarray) -> np.ndarray:
    if mask.shape != WORLD_SHAPE or mask.dtype != np.bool_:
        raise FirstContactScoreError("continuity mask must be 256x256 boolean")
    return mask


def _raster(raster: np.ndarray) -> np.ndarray:
    if raster.shape != WORLD_SHAPE or raster.dtype != np.uint8:
        raise FirstContactScoreError("continuity raster must be 256x256 L8")
    return raster


def count_8_connected_components(mask: np.ndarray) -> int:
    """Count real foreground components; no tolerance dilation is allowed."""
    mask = _binary(mask)
    visited = np.zeros(WORLD_SHAPE, dtype=np.bool_)
    count = 0
    for y, x in np.argwhere(mask):
        y, x = int(y), int(x)
        if visited[y, x]:
            continue
        count += 1
        visited[y, x] = True
        queue = deque([(y, x)])
        while queue:
            cy, cx = queue.popleft()
            for dy, dx in NEIGHBORS:
                ny, nx = cy + dy, cx + dx
                if (
                    0 <= ny < 256 and 0 <= nx < 256
                    and mask[ny, nx] and not visited[ny, nx]
                ):
                    visited[ny, nx] = True
                    queue.append((ny, nx))
    return count


def _min_linf_distance(initial: np.ndarray, added: np.ndarray) -> int | None:
    """Chebyshev pixel distance between sets, exact on the grid.

    Multi-source 8-neighbour BFS avoids O(n_initial*n_added) comparisons.
    """
    if not initial.any() or not added.any():
        return None
    distance = np.full(WORLD_SHAPE, -1, dtype=np.int16)
    queue = deque()
    for y, x in np.argwhere(initial):
        y, x = int(y), int(x)
        distance[y, x] = 0
        queue.append((y, x))
    while queue:
        y, x = queue.popleft()
        if added[y, x]:
            return int(distance[y, x])
        d = distance[y, x] + 1
        for dy, dx in NEIGHBORS:
            ny, nx = y + dy, x + dx
            if 0 <= ny < 256 and 0 <= nx < 256 and distance[ny, nx] < 0:
                distance[ny, nx] = d
                queue.append((ny, nx))
    return None


def diagnose_continuity_v0(
    *,
    target_mask: np.ndarray,
    editable_mask: np.ndarray,
    poststroke_world_l8: np.ndarray,
    terminal_world_l8: np.ndarray,
) -> dict:
    """Posthoc E1 single-component diagnostic; not a learned Eye judgment.

    Here gap is the minimum *raster-set separation*, not inferred pen-tip
    endpoint distance. The latter needs a separate geometry/pen-state probe.
    """
    target = _binary(target_mask)
    editable = _binary(editable_mask)
    before = _raster(poststroke_world_l8) < INK_THRESHOLD
    after = _raster(terminal_world_l8) < INK_THRESHOLD
    if np.any(after & ~editable) or np.any(before & ~editable):
        raise FirstContactScoreError("protected area contains ink")
    lost = int(np.count_nonzero(before & ~after))
    if lost:
        raise FirstContactScoreError("drawing unexpectedly erased existing ink")
    before &= editable
    after &= editable
    added = after & ~before
    target_components = count_8_connected_components(target & editable)
    before_components = count_8_connected_components(before)
    after_components = count_8_connected_components(after)
    min_distance = _min_linf_distance(before, added)
    blank_gap = None if min_distance is None else max(0, min_distance - 1)
    supported = target_components == 1
    strict_connected = supported and after_components == 1 and (
        not added.any() or blank_gap == 0
    )
    status = (
        "unsupported" if not supported else
        "pass" if strict_connected else
        "fail"
    )
    return {
        "format": FORMAT,
        "scope": "single_8_connected_reference_raster_only",
        "policy_visible": False,
        "world_ink_threshold_l8": INK_THRESHOLD,
        "neighborhood": 8,
        "target_8_connected_components": target_components,
        "poststroke_8_connected_components": before_components,
        "terminal_8_connected_components": after_components,
        "poststroke_ink_px": int(np.count_nonzero(before)),
        "appended_ink_px": int(np.count_nonzero(added)),
        "lost_ink_px": lost,
        "minimum_initial_added_linf_distance_px": min_distance,
        "minimum_initial_added_blank_gap_px": blank_gap,
        "strict_connected": bool(strict_connected),
        "status": status,
        "limitation": (
            "Raster connectivity only; no reliable tangent, brush-width or "
            "physical pen-tip continuity inference from L8 pixels alone"
        ),
    }
