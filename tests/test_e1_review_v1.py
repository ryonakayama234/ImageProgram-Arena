"""E1 causal Review Pack gates on actual poststroke frame and pinned replay."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.reference_target_v1 import FirstContactScoreError
from adapters.imageprogram_reference.run_e1_synthetic_v1 import run_synthetic_g2_v1
from adapters.imageprogram_reference.e1_review_v1 import build_causal_e1_review_v1


@unittest.skipUnless(
    importlib.util.find_spec("imageprogram"),
    "requires exact paired ImageProgram checkout; mandatory gate cannot skip",
)
class E1CausalReviewV1Tests(unittest.TestCase):
    def test_actual_eye_frame41_and_independent_continuity_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "experiment"
            generated = run_synthetic_g2_v1(output)
            self.assertEqual(generated["status"], "SYNTHETIC_CASES_PASS")
            case = output / "underdraw"
            report = json.loads(
                (case / "review_e1_v1" / "continuity_diagnostic.json").read_text()
            )
            self.assertEqual(report["format"], "arena-e1-causal-review-v1")
            self.assertTrue(report["source_replay_verified_arms"])
            self.assertTrue(report["model_actual_eye_decision_frame_index"] > 0)
            self.assertNotEqual(
                report["model_actual_eye_decision_frame_index"],
                report["naive_halfway_frame_index_not_an_eye_frame"],
            )
            self.assertFalse(report["human_accepted"])
            self.assertIn(report["continuity"]["status"], {"pass", "fail"})
            html = (case / "review_e1_v1" / "index.html").read_text()
            self.assertIn(
                "actual Eye boundary frame "
                + str(report["model_actual_eye_decision_frame_index"]), html
            )
            self.assertIn("Arena-only", html)

    def test_forged_decision_receipt_fails_before_review_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "experiment"
            run_synthetic_g2_v1(output)
            case = output / "underdraw"
            receipt = case / "sessions" / "feedback_on_receipt.json"
            contents = json.loads(receipt.read_text())
            contents["decision_receipt"]["canvas_image_sha256"] = "sha256:" + "0" * 64
            receipt.write_text(json.dumps(contents))
            dest = case / "should_not_exist"
            with self.assertRaises(FirstContactScoreError):
                build_causal_e1_review_v1(
                    output / "public_roi", case / "sessions", dest
                )
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
