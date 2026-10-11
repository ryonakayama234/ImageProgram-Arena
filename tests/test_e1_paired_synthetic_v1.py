"""Paired, opt-in Model/Arena ART-1 E1 synthetic end-to-end acceptance.

Arena-only imports/test collection are allowed without Model; the G2 shell
explicitly asserts the paired Python import works and treats skips as a FAIL.
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.run_e1_synthetic_v1 import run_synthetic_g2_v1


@unittest.skipUnless(
    importlib.util.find_spec("imageprogram"),
    "paired ImageProgram checkout required; G2 gate MUST NOT skip this test",
)
class E1G2PairedSyntheticV1Tests(unittest.TestCase):
    def test_two_synthetic_modes_have_real_replays_independent_scores_and_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "experiment"
            report = run_synthetic_g2_v1(output)
            self.assertEqual(report["status"], "SYNTHETIC_CASES_PASS")
            self.assertEqual(report["checks"], {"underdraw": True, "complete": True})
            under = report["cases"]["underdraw"]
            complete = report["cases"]["complete"]
            self.assertEqual(under["decision_kind"], "execute")
            self.assertGreater(under["correction_motor_commands"], 0)
            self.assertGreater(under["delta_f1_on_minus_off"], 0)
            self.assertTrue(under["protected_ink_zero"])
            self.assertEqual(complete["decision_kind"], "stop")
            self.assertEqual(complete["correction_motor_commands"], 0)
            self.assertTrue(complete["protected_ink_zero"])
            self.assertTrue((output / "underdraw" / "review" / "index.html").is_file())
            for name in ("underdraw", "complete"):
                case = output / name
                scores = json.loads(
                    (case / "arena_independent_score.json").read_text()
                )
                self.assertEqual(scores["replay_verified_arms"],
                                 ["noop", "feedback_off", "feedback_on"])
                self.assertFalse(scores["human_accepted"])
                self.assertEqual(
                    set(scores["evidence_snapshot"]["episode_manifest_sha256"]),
                    {"noop", "feedback_off", "feedback_on"},
                )
                for arm in scores["scores"].values():
                    self.assertEqual(arm["drawn_ink_outside_editable_px"], 0)

    def test_synthetic_uses_a_real_source_intake_not_unverified_task_json(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "g2"
            run_synthetic_g2_v1(out)
            manifest = json.loads((out / "management" / "source_manifest.json").read_text())
            task = json.loads((out / "public_roi" / "task.json").read_text())
            self.assertEqual(manifest["format"], "arena-local-source-roi-v0")
            self.assertEqual(task["format"], "arena-public-reference-roi-v1")
            self.assertEqual({p.name for p in (out / "public_roi").iterdir()},
                             {"task.json", "reference_roi.png"})
            self.assertNotIn("generated-art1-e1-g2", json.dumps(task))
            self.assertNotIn("source_family", json.dumps(task))


if __name__ == "__main__":
    unittest.main()
