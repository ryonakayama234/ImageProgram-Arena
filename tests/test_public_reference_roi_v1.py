"""Synthetic-only v1 ROI export tests."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from adapters.imageprogram_reference.public_reference_roi_v1 import export_permitted_roi_v1
from adapters.imageprogram_reference.reference_target_v1 import target_and_masks_v1
from adapters.imageprogram_reference.source_artwork import ingest_local_source


class PublicExportV1Tests(unittest.TestCase):
    def test_export_and_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.png"
            image = Image.new("RGB", (128, 160), "white")
            ImageDraw.Draw(image).line([(20, 70), (99, 70)], fill="black", width=1)
            image.save(source)
            manifest = ingest_local_source(
                source, editable_bbox=(0, 0, 128, 160),
                source_family="synthetic-fixture", rights="generated-test-fixture"
            )
            record = root / "record.json"
            record.write_text(json.dumps(manifest))
            output = root / "public"
            task = export_permitted_roi_v1(source, record, output)
            self.assertEqual(sorted(p.name for p in output.iterdir()),
                             ["reference_roi.png", "task.json"])
            self.assertEqual(task["format"], "arena-public-reference-roi-v1")
            self.assertEqual(task["placement"]["offset_world_px"], [32.0, 8.0])
            target, editable, protected = target_and_masks_v1(
                task, (output / "reference_roi.png").read_bytes()
            )
            self.assertTrue(target.any())
            self.assertEqual(int(editable.sum()), 192 * 240)
            self.assertTrue(protected[0, 0])
            self.assertNotIn("synthetic-fixture", (output / "task.json").read_text())
            with self.assertRaises(ValueError):
                export_permitted_roi_v1(source, record, output)
            Image.new("RGB", (128, 160), "black").save(source)
            with self.assertRaises(ValueError):
                export_permitted_roi_v1(source, record, root / "forged")
            self.assertFalse((root / "forged").exists())


if __name__ == "__main__":
    unittest.main()
