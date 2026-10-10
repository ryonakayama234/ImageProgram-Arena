"""Export *explicitly permitted* ROI pixels for an ART-1 reference task.

Management-only source path/rights/family/hash are never copied into the
Painter-facing task. Only the ROI itself, not hidden targets or full artwork,
is accessible to the ImageProgram reference-based restoration baseline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageOps

from adapters.imageprogram_reference.source_artwork import ingest_local_source


def export_permitted_roi(source: Path, management_manifest: Path, output: Path) -> dict:
    source = Path(source)
    management_manifest = Path(management_manifest)
    if management_manifest.is_symlink() or not management_manifest.is_file():
        raise ValueError("management manifest must be a regular local file")
    if management_manifest.stat().st_size > 16384:
        raise ValueError("oversized management manifest")
    management = json.loads(management_manifest.read_text(encoding="utf-8"))
    if management.get("format") != "arena-local-source-roi-v0":
        raise ValueError("unexpected intake manifest version")
    info = management["source"]
    roi = management["roi"]
    checked = ingest_local_source(
        source, editable_bbox=tuple(roi["editable_bbox"]),
        source_family=info["source_family"], rights=info["rights"],
        protected_bboxes=tuple(tuple(b) for b in roi["protected_bboxes"]),
    )
    if checked != management:
        raise ValueError("management manifest no longer matches original source/ROI")
    # Same normalization as source_artwork.ingest_local_source; verify bytes and
    # pixel-stream hash again above before exporting any policy-visible pixels.
    with Image.open(source) as original:
        normalized = ImageOps.exif_transpose(original)
        if normalized.mode in ("RGBA", "LA"):
            rgba = normalized.convert("RGBA")
            rgb = Image.new("RGB", rgba.size, (255, 255, 255))
            rgb.paste(rgba, mask=rgba.getchannel("A"))
        else:
            rgb = normalized.convert("RGB")
        x0, y0, x1, y1 = roi["editable_bbox"]
        crop = rgb.crop((x0, y0, x1, y1)).convert("L")
        if crop.width * crop.height > 256 * 256 or min(crop.size) < 12:
            raise ValueError("ART-1 v0 accepts only 12..256px ROI and <=65536 pixels")
    if output.is_symlink() or output.exists():
        raise ValueError("output directory must not exist or be symlinked")
    output.mkdir(parents=True, exist_ok=False)
    crop_path = output / "reference_roi.png"
    crop.save(crop_path, format="PNG")
    png = crop_path.read_bytes()
    task = {
        "format": "arena-public-reference-roi-v0",
        "canvas_size_px": [info["width_px"], info["height_px"]],
        "editable_bbox": list(roi["editable_bbox"]),
        "protected_bboxes": [list(b) for b in roi["protected_bboxes"]],
        "reference_visibility": "permitted_reference_processed",
        "reference_roi_sha256": "sha256:" + hashlib.sha256(png).hexdigest(),
    }
    (output / "task.json").write_text(json.dumps(task, sort_keys=True, indent=2) + "\n",
                                      encoding="utf-8")
    return task


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    task = export_permitted_roi(a.source, a.manifest, a.out)
    print(json.dumps({"status": "LOCAL_POLICY_REFERENCE_ROI_EXPORTED",
                      "bbox": task["editable_bbox"], "output": str(a.out)}))


if __name__ == "__main__":
    main()
