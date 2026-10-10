"""Synthetic ART-1 public image boundary and private-source separation tests."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from adapters.imageprogram_reference.public_reference_roi import export_permitted_roi
from adapters.imageprogram_reference.score_first_contact import score_mask
from adapters.imageprogram_reference.source_artwork import ingest_local_source


class PublicReferenceROITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "private-original.png"
        frame = Image.new("RGB", (128, 128), "white")
        ImageDraw.Draw(frame).line([(20, 60), (40, 45), (70, 78), (92, 53)],
                                   fill="black", width=2)
        frame.save(self.source)
        intake = ingest_local_source(self.source, editable_bbox=(8, 8, 120, 120),
                                     source_family="PRIVATE_SOURCE_FAMILY_A",
                                     rights="local-only-not-for-publication")
        self.manifest = self.root / "source_manifest.json"
        self.manifest.write_text(json.dumps(intake))

    def test_export_contains_only_explicitly_permitted_cropped_reference(self):
        out = self.root / "public"
        record = export_permitted_roi(self.source, self.manifest, out)
        self.assertEqual(set(record), {
            "format", "canvas_size_px", "editable_bbox", "protected_bboxes",
            "reference_visibility", "reference_roi_sha256",
        })
        self.assertNotIn("PRIVATE_SOURCE_FAMILY_A", (out / "task.json").read_text())
        self.assertNotIn(str(self.source), (out / "task.json").read_text())
        self.assertEqual(sorted(p.name for p in out.iterdir()),
                         ["reference_roi.png", "task.json"])
        with Image.open(out / "reference_roi.png") as roi:
            self.assertEqual(roi.mode, "L")
            self.assertEqual(roi.size, (112, 112))
        self.assertEqual(
            record["reference_roi_sha256"],
            "sha256:" + hashlib.sha256((out / "reference_roi.png").read_bytes()).hexdigest(),
        )

    def test_source_changed_after_intake_is_not_exported(self):
        Image.new("RGB", (128, 128), "black").save(self.source)
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            export_permitted_roi(self.source, self.manifest, self.root / "public")
        self.assertFalse((self.root / "public").exists())

    def test_source_replaced_after_intake_recheck_is_not_exported(self):
        # Simulate a local writer changing source between the management
        # verification and the final crop read. Never export unverified pixels.
        real_ingest = ingest_local_source

        def verify_then_replace(*args, **kwargs):
            result = real_ingest(*args, **kwargs)
            Image.new("RGB", (128, 128), "black").save(self.source)
            return result

        with patch(
            "adapters.imageprogram_reference.public_reference_roi.ingest_local_source",
            side_effect=verify_then_replace,
        ):
            with self.assertRaisesRegex(ValueError, "source changed after"):
                export_permitted_roi(self.source, self.manifest, self.root / "public")
        self.assertFalse((self.root / "public").exists())

    def test_tampered_annotation_is_not_exported(self):
        record = json.loads(self.manifest.read_text())
        record["roi"]["editable_bbox"] = [10, 10, 40, 40]
        self.manifest.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            export_permitted_roi(self.source, self.manifest, self.root / "public")

    def test_scoring_does_not_give_noop_credit_for_white_background(self):
        target = np.zeros((32, 32), dtype=bool)
        target[10:22, 15] = True
        allowed = np.ones_like(target)
        blank = np.zeros_like(target)
        self.assertEqual(score_mask(target, blank, allowed)["f1_2px"], 0.0)
        self.assertEqual(score_mask(target, target.copy(), allowed)["f1_2px"], 1.0)
        invalid = target.copy()
        invalid[0, 0] = True
        allowed[0, 0] = False
        self.assertEqual(score_mask(target, invalid, allowed)["drawn_ink_outside_editable_px"], 1)


if __name__ == "__main__":
    unittest.main()
