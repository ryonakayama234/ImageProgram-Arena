import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from adapters.imageprogram_reference.public_reference_roi_v1 import (
    export_permitted_roi_v1,
)
from adapters.imageprogram_reference.smooth_contour_review_v0 import review
from adapters.imageprogram_reference.source_artwork import ingest_local_source


class SmoothReviewTests(unittest.TestCase):
    def make_session(self, root):
        from imageprogram.experiments.smooth_contour_session_v0 import run

        image = Image.new("L", (160, 160), 255)
        ImageDraw.Draw(image).line([(25, 70), (135, 70)], fill=0, width=1)
        source = root/"source.png"
        image.save(source)
        manifest = ingest_local_source(source, editable_bbox=(0, 0, 160, 160),
                                       source_family="unit-private", rights="procedural")
        (root/"manifest.json").write_text(json.dumps(manifest))
        export_permitted_roi_v1(source, root/"manifest.json", root/"public")
        run(root/"public", root/"session")
        return root/"session"

    def test_no_real_quality_claim_without_independent_centre(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = review(self.make_session(Path(tmp)))
            for arm in result["arms"].values():
                self.assertEqual(arm["integrity"]["status"], "unknown")
                self.assertFalse(arm["synthetic_profile_gate_pass"])
                self.assertEqual(arm["protected_ink_px"], 0)

    def test_endpoint_failure_not_hidden_by_high_shape_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = self.make_session(Path(tmp))
            # Deliberately displaced evaluator witness endpoint: even when F1
            # and interior quality are good, endpoint error must fail the gate.
            witness = [(35, 113.75), (211.25, 113.75)]
            result = review(session, source_path_world_px=witness)
            for arm in result["arms"].values():
                self.assertGreaterEqual(arm["shape"]["f1_2px"], 0.95)
                self.assertGreater(arm["endpoint_ink_distance_world_px"][0], 2)
                self.assertFalse(arm["synthetic_profile_gate_pass"])

    def test_modified_actual_png_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = self.make_session(Path(tmp))
            (session/"curve/final.png").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "digest"):
                review(session)
