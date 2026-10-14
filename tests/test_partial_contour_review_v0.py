import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from adapters.imageprogram_reference.partial_contour_pilot_v0 import prepare_task
from adapters.imageprogram_reference.partial_contour_review_v0 import review


class PartialReviewTests(unittest.TestCase):
    def fixture(self, root):
        from imageprogram.experiments.partial_contour_session_v0 import run

        source = root/"source.png"
        im = Image.new("L", (100, 100), 255)
        ImageDraw.Draw(im).line([(5, 50), (95, 50)], fill=0, width=1)
        im.save(source)
        public = prepare_task(source, (25, 30, 75, 70), root/"task", rights="procedural")
        run(public, root/"session")
        return root/"session", public

    def test_legal_cut_contour_and_uncertain_target_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            session, public = self.fixture(Path(tmp))
            result = review(session)
            self.assertTrue(result["arms"]["partial"]["legal_execution_gate"])
            self.assertEqual(result["arms"]["partial"]["protected_ink_px"], 0)
            self.assertTrue(result["arms"]["observed_trace"]["diagnostic_only"])
            self.assertFalse(result["capability_pass"])
            self.assertTrue(result["arms"]["partial"]["target_selection"].startswith("unknown"))
            focus = json.loads((public/"focus.json").read_text())
            self.assertNotIn("focus_global_box", focus)
            self.assertNotIn("source_family", focus)

    def test_final_canvas_modification_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            session, _ = self.fixture(Path(tmp))
            (session/"partial/final.png").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "digest"):
                review(session)

    def test_forged_halo_rejected_by_independent_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            session, _ = self.fixture(Path(tmp))
            p = session/"report.json"
            report = json.loads(p.read_text())
            report["allowed_bounds_world_px"][0] -= 10
            p.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "region mismatch"):
                review(session)
