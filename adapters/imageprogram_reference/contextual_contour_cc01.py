"""Arena CC-01 procedural contour-pair tasks and independent action review.

Private label, paired intervention and source family never appear in public input.
No third-party/Google Drive art copied. Decision-only, not Motor/Canvas validation.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
import numpy as np

VERSION = "arena-contextual-contour-cc01-v1"

@dataclass(frozen=True)
class PrivateAnswer:
    pair_id: str
    member_id: str
    correct_action: str
    source_family: str
    template_family: str
    split: str
    label_version: str = VERSION

def _paint_line(img, p, q):
    x0, y0 = p
    x1, y1 = q
    if x0 == x1:
        img[min(y0, y1):max(y0, y1) + 1, x0] = 0
    elif y0 == y1:
        img[y0, min(x0, x1):max(x0, x1) + 1] = 0
    else:
        raise ValueError("cardinal-only-template")

def _digest(arr):
    return hashlib.sha256(arr.tobytes()).hexdigest()

def create_pair(index, *, split="development"):
    """Same local evidence/anchor per pair; opposite *private* action labels.

    Development horizontal and confirmation vertical are different procedural
    template families, NOT independent real source families.
    """
    if type(index) is not int or not 0 <= index < 6 or split not in ("development", "confirmation"):
        raise ValueError("invalid-pair")
    y = 28 + index
    shift = index % 3
    focus = (6, 12, 55, 60)
    anchor = (10 + shift + 0.5, y + 0.5)
    first = (10 + shift, y), (28 + shift, y)
    second = (33 + shift, y), (52 + shift, y)
    cases = []
    for action in ("continue", "stop"):
        raster = np.full((72, 72), 255, dtype=np.uint8)
        _paint_line(raster, *first)
        _paint_line(raster, *second)
        if action == "continue":
            _paint_line(raster, (59 + shift, y), (67 + shift, y))
        else:
            # Nearby but distinct: a perpendicular branch is not forward support.
            _paint_line(raster, (60 + shift, y + 5), (60 + shift, y + 16))
        if split == "confirmation":
            raster = np.ascontiguousarray(raster.T)
            focus = (12, 6, 60, 55)
            anchor = (y + 0.5, 10 + shift + 0.5)
        member_id = f"{split[:3]}-{index:02d}-{action}"
        public = {"format": VERSION, "pixels_l8": raster,
                  "focus_box": focus, "anchor_px": anchor,
                  "raster_digest": _digest(raster), "budget_pixels": 8192}
        private = PrivateAnswer(f"{split[:3]}-{index:02d}", member_id, action,
                                f"synthetic-{split}",
                                ("cardinal-horizontal-v1" if split == "development"
                                 else "cardinal-vertical-v2"), split)
        cases.append((public, private))
        focus = (6, 12, 55, 60)
        anchor = (10 + shift + 0.5, y + 0.5)
    return tuple(cases)

def validate_pair(cases):
    if len(cases) != 2:
        raise ValueError("pair-size")
    (a, pa), (b, pb) = cases
    expected_keys = {"format", "pixels_l8", "focus_box", "anchor_px",
                     "raster_digest", "budget_pixels"}
    if any(set(public) != expected_keys for public in (a, b)):
        raise ValueError("unexpected-public-fields")
    if pa.pair_id != pb.pair_id or {pa.correct_action, pb.correct_action} != {"continue", "stop"}:
        raise ValueError("invalid-private-label-pair")
    if a["anchor_px"] != b["anchor_px"] or a["focus_box"] != b["focus_box"]:
        raise ValueError("local-anchor-difference")
    x0, y0, x1, y1 = a["focus_box"]
    ca, cb = a["pixels_l8"][y0:y1, x0:x1], b["pixels_l8"][y0:y1, x0:x1]
    if not np.array_equal(ca, cb):
        raise ValueError("local-pixel-difference")
    if np.array_equal(a["pixels_l8"], b["pixels_l8"]):
        raise ValueError("no-intervened-context")
    return {"pair_id": pa.pair_id, "local_digest": _digest(ca),
            "public_digests": (a["raster_digest"], b["raster_digest"]),
            "template_family": pa.template_family, "split": pa.split}

def evaluate(decision, private):
    """No Model import. Compare a post-decision receipt to private source truth."""
    if decision.action not in ("continue", "stop", "hold"):
        raise ValueError("invalid-action")
    if decision.arm not in ("A1", "B", "B-shuffle"):
        raise ValueError("invalid-arm")
    return {"member_id": private.member_id, "pair_id": private.pair_id,
            "arm": decision.arm, "predicted_action": decision.action,
            "correct": decision.action == private.correct_action,
            "false_join": private.correct_action == "stop" and decision.action == "continue",
            "hold": decision.action == "hold", "reason": decision.reason,
            "candidate_set_sha256": decision.candidate_set_sha256}

def aggregate(reviews):
    out = {}
    for arm in sorted({r["arm"] for r in reviews}):
        rows = [r for r in reviews if r["arm"] == arm]
        groups = {}
        for row in rows:
            groups.setdefault(row["pair_id"], []).append(row)
        out[arm] = {
            "members": len(rows),
            "member_correct": sum(r["correct"] for r in rows),
            "pairs": len(groups),
            "pair_both_correct": sum(len(g) == 2 and all(x["correct"] for x in g)
                                     for g in groups.values()),
            "false_joins": sum(r["false_join"] for r in rows),
            "holds": sum(r["hold"] for r in rows),
        }
    return out
