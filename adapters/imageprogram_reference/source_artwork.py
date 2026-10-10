"""Arena-local source-artwork/ROI intake. Management-only; never a policy task view.

A02 v0 pilot: one PNG/JPEG, post-EXIF normalized pixel space, one editable
bbox, optional protected bboxes. No source image bytes are exported by this API.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import warnings
from pathlib import Path


class SourceIntakeError(ValueError):
    pass


MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_PIXELS = 16_777_216
NORMALIZATION_VERSION = "exif_transpose_rgb_white_v1"


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _rect(name: str, box: object, width: int, height: int) -> list[int]:
    if (not isinstance(box, (tuple, list)) or len(box) != 4
            or any(type(v) is not int for v in box)):
        raise SourceIntakeError(f"{name}: expected exactly four integer pixel coordinates")
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise SourceIntakeError(f"{name}: empty, reversed, or out-of-bounds bbox")
    return [x0, y0, x1, y1]


def _overlap(a: list[int], b: list[int]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def ingest_local_source(
    path: str | Path,
    *,
    editable_bbox: tuple[int, int, int, int],
    source_family: str,
    rights: str,
    protected_bboxes: tuple[tuple[int, int, int, int], ...] = (),
) -> dict:
    """Return a local *management* record, never policy-visible image data.

    Bboxes refer to fully EXIF-transposed pixels. No image bytes, absolute path,
    hidden target, or evaluator witness is included in the returned object.
    """
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise SourceIntakeError("Pillow required in the Arena execution environment") from exc

    if not isinstance(source_family, str) or not source_family.strip():
        raise SourceIntakeError("source_family must be nonempty management provenance")
    if not isinstance(rights, str) or not rights.strip():
        raise SourceIntakeError("rights must be explicitly recorded (e.g. unknown)")

    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise SourceIntakeError("source must be an existing non-symlink local file")
    with source.open("rb") as handle:
        raw = handle.read(MAX_SOURCE_BYTES + 1)
    if not raw or len(raw) > MAX_SOURCE_BYTES:
        raise SourceIntakeError("source file is empty or exceeds the byte budget")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as verify_image:
                source_format = verify_image.format
                if source_format not in ("PNG", "JPEG"):
                    raise SourceIntakeError("only PNG/JPEG are supported")
                if verify_image.width * verify_image.height > MAX_PIXELS:
                    raise SourceIntakeError("decoded source exceeds pixel budget")
                verify_image.verify()
            with Image.open(io.BytesIO(raw)) as original:
                if getattr(original, "n_frames", 1) != 1:
                    raise SourceIntakeError("animated/multi-frame images unsupported")
                if original.info.get("icc_profile"):
                    raise SourceIntakeError("ICC profile: unsupported until color management is defined")
                source_mode = original.mode
                orientation = original.getexif().get(274, 1)
                if type(orientation) is not int or orientation not in range(1, 9):
                    raise SourceIntakeError("invalid EXIF orientation")
                if source_mode not in ("RGB", "RGBA", "L", "LA"):
                    raise SourceIntakeError("unsupported image mode")
                normalized = ImageOps.exif_transpose(original)
                if normalized.width * normalized.height > MAX_PIXELS:
                    raise SourceIntakeError("normalized source exceeds pixel budget")
                normalized.load()
                if normalized.mode in ("RGBA", "LA"):
                    rgba = normalized.convert("RGBA")
                    rgb = Image.new("RGB", rgba.size, (255, 255, 255))
                    rgb.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    rgb = normalized.convert("RGB")
                width, height = rgb.size
                pixel_stream = (width.to_bytes(4, "big") +
                                height.to_bytes(4, "big") + rgb.tobytes())
    except SourceIntakeError:
        raise
    except (OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning, UnidentifiedImageError) as exc:
        raise SourceIntakeError(f"image decode/verification failed: {type(exc).__name__}") from exc

    editable = _rect("editable", editable_bbox, width, height)
    protected = [_rect(f"protected[{i}]", b, width, height)
                 for i, b in enumerate(protected_bboxes)]
    if any(_overlap(editable, box) for box in protected):
        raise SourceIntakeError("editable and protected regions overlap")

    return {
        "format": "arena-local-source-roi-v0",
        "access_class": "management_private",
        "source": {
            "source_bytes_sha256": _sha(raw),
            "normalized_pixels_sha256": _sha(pixel_stream),
            "source_format": source_format,
            "source_mode": source_mode,
            "exif_orientation_original": orientation,
            "normalization_version": NORMALIZATION_VERSION,
            "alpha_background_rgb": [255, 255, 255],
            "width_px": width,
            "height_px": height,
            "source_family": source_family,
            "rights": rights,
        },
        "roi": {
            "coordinate_frame": "normalized_pixels_xy_half_open",
            "annotation_revision": 1,
            "focus_bbox": editable.copy(),
            "editable_bbox": editable,
            "protected_bboxes": protected,
            "observation_channel": "permitted_reference_processed",
            "scored_region_visibility": "evaluator_private",
            "scored_bbox_management_only": editable.copy(),
        },
        "claims": {"runtime_task_bound": False, "motor_executed": False,
                   "learning_demonstrated": False},
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Local private SourceArtwork intake (not an ART-1 drawing)")
    p.add_argument("image", help="local PNG/JPEG path, never uploaded")
    p.add_argument("--roi", required=True, type=int, nargs=4,
                   metavar=("X0", "Y0", "X1", "Y1"))
    p.add_argument("--source-family", required=True, help="management provenance (not policy input)")
    p.add_argument("--rights", required=True, help="usage/redistribution status")
    p.add_argument("--out", default="runs/real_reference/source_manifest.json",
                   help="LOCAL/IGNORED management JSON path; do not commit it")
    a = p.parse_args()
    record = ingest_local_source(
        a.image, editable_bbox=tuple(a.roi), source_family=a.source_family, rights=a.rights,
    )
    output = Path(a.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(f"LOCAL_MANAGEMENT_RECORD: {output}")


if __name__ == "__main__":
    main()
