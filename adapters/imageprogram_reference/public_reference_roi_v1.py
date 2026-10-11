"""Authorize and export a strictly v1, policy-visible local ROI task.

The existing v0 source intake/verifier is reused unchanged inside a private
temporary directory. The only output is a permitted ROI PNG and a v1 allowlisted
task view: no original artwork bytes, source-global box, rights or family.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from adapters.imageprogram_reference.public_reference_roi import export_permitted_roi
from adapters.imageprogram_reference.reference_target_v1 import (
    make_public_v1_task,
    target_and_masks_v1,
)


def export_permitted_roi_v1(
    source: Path, management_manifest: Path, output: Path
) -> dict:
    """Fail before publishing if private source or placement is inconsistent."""
    output = Path(output)
    if output.is_symlink() or output.exists():
        raise ValueError("v1 output already exists or is a symlink")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError("v1 destination must have an existing regular parent")
    with tempfile.TemporaryDirectory(prefix="art1-roi-v1-", dir=output.parent) as tmp:
        scratch = Path(tmp) / "verified"
        export_permitted_roi(Path(source), Path(management_manifest), scratch)
        png = (scratch / "reference_roi.png").read_bytes()
        task = make_public_v1_task(png)
        target, _, _ = target_and_masks_v1(task, png)
        if not target.any():
            raise ValueError("no measurable high-contrast reference ink")
        (scratch / "task.json").write_text(
            json.dumps(task, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        # Atomic same-filesystem publish of exactly two allowlisted outputs.
        # A concurrent writer must not be able to replace a nonempty folder.
        if output.exists() or output.is_symlink():
            raise ValueError("v1 destination appeared during verification")
        os.rename(scratch, output)
        return task


def main() -> None:
    parser = argparse.ArgumentParser(description="Export authorized ART-1 v1 ROI")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    task = export_permitted_roi_v1(args.source, args.manifest, args.out)
    print(json.dumps({
        "status": "ART1_V1_PUBLIC_ROI_READY",
        "transform_version": task["placement"]["transform_version"],
        "output": str(args.out),
    }))


if __name__ == "__main__":
    main()
