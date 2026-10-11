"""Cross-repository synthetic P1 episode scoring, no private artwork required."""
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from adapters.imageprogram_reference.reference_target_v1 import make_public_v1_task
from adapters.imageprogram_reference.score_feedback_e1_v1 import score_paired_e1_v1
from adapters.imageprogram_reference.score_first_contact import FirstContactScoreError


@unittest.skipUnless(importlib.util.find_spec("imageprogram"),
                     "paired ImageProgram installation needed for canonical P1 replay")
class E1IndependentEpisodeScoreTests(unittest.TestCase):
    def test_independent_full_episodes_and_tamper_rejection(self):
        from imageprogram.experiments.art1_feedback_session_v1 import run_feedback_session_v1

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public = root / "public"
            public.mkdir()
            crop = np.full((160, 128), 255, dtype=np.uint8)
            crop[70, 20:100] = 0
            with io.BytesIO() as stream:
                Image.fromarray(crop).save(stream, format="PNG")
                png = stream.getvalue()
            (public / "reference_roi.png").write_bytes(png)
            task = make_public_v1_task(png)
            (public / "task.json").write_text(json.dumps(task))
            run = root / "episodes"
            run_feedback_session_v1(public, run, seed=17, initial_fraction=0.55)
            report = score_paired_e1_v1(public, run, root / "score.json")
            self.assertEqual(report["format"], "art1-e1-independent-episode-score-v1")
            self.assertTrue(report["initial_actions_identical"])
            self.assertTrue(report["intermediate_replay_raster_bound"])
            self.assertEqual(report["scores"]["noop"]["f1_2px"], 0)
            self.assertGreater(report["delta_f1_on_minus_off"], 0)
            self.assertFalse(report["human_accepted"])
            # Falsifying the decision linkage never becomes a valid Arena score.
            receipt = run / "feedback_on_receipt.json"
            data = json.loads(receipt.read_text())
            data["decision_receipt"]["canvas_image_sha256"] = "sha256:" + "0" * 64
            receipt.write_text(json.dumps(data))
            with self.assertRaises(FirstContactScoreError):
                score_paired_e1_v1(public, run, root / "forged-score.json")
            self.assertFalse((root / "forged-score.json").exists())

    def test_rejects_nonexistent_episode_without_scoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises((ValueError, FileNotFoundError)):
                score_paired_e1_v1(root, root, root / "no-score.json")


if __name__ == "__main__":
    unittest.main()
