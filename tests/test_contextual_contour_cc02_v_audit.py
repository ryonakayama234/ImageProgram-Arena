"""CC-02-V: independent geometry annotation / evaluation controls.

Integration test requires the branch of ImageProgram with public trace installed.
No confirmation task factory is imported or evaluated by the audit runner.
"""
import copy
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
    create_development_pair,
)
from adapters.imageprogram_reference.contextual_contour_cc02_v_audit import (
    DEVELOPMENT_MANIFEST_SHA256,
    _public_observe,
    _review_dev,
    _sha_json,
    _write_new,
    development_private_arc,
    grade_development,
    predict_development,
    run_development_audit,
)


class CC02VArcEvidenceTests(unittest.TestCase):
    def test_positive_action_success_does_not_certify_selected_path(self):
        result = run_development_audit()
        positive = result["private_reviews"][8]
        self.assertTrue(positive["reviews"][1]["correct"])
        self.assertEqual(positive["reviews"][1]["earliest_blocker"],
                         "action-correct-path-unverified")
        self.assertEqual(positive["reviews"][1]["selected_path_verdict"], "UNKNOWN")

    def test_relation_uses_actual_selected_pair_with_extra_focus_node(self):
        public, private = create_development_pair(4)[0]
        public["pixels_l8"][45, 45:55] = 0
        public["raster_digest"] = hashlib.sha256(public["pixels_l8"].tobytes()).hexdigest()
        trace, receipt = _public_observe(public)
        review = _review_dev(private, development_private_arc(4, private), trace, receipt, public)
        self.assertTrue(review["target_edge_accessible"])

    def test_full_coverage_with_excluded_ink_does_not_certify_ownership(self):
        public, private = create_development_pair(4)[0]
        trace, receipt = _public_observe(public)
        arc = development_private_arc(4, private)
        arc = replace(arc, excluded_xy=arc.excluded_xy + ((59, 31),),
                      target_xy=tuple(xy for xy in arc.target_xy if xy != (59, 31)))
        review = _review_dev(private, arc, trace, receipt, public)
        self.assertEqual(review["admitted_target_coverage"], 1.)
        self.assertEqual(review["target_component_excluded_pixels"], 1)
        self.assertEqual(review["reviews"][1]["earliest_blocker"], "target-ownership-unresolved")

    def test_predict_never_calls_private_arc_grader(self):
        with patch("adapters.imageprogram_reference.contextual_contour_cc02_v_audit."
                   "development_private_arc", side_effect=AssertionError("private grading")):
            prediction = predict_development()
        self.assertEqual(prediction["phase"], "PREDICT")
        payload = json.dumps(prediction)
        for key in ("target_xy", "excluded_xy", "member_id", "expected_action", "private_reviews"):
            self.assertNotIn(key, payload)

    def test_saved_predictions_grade_without_reinvoking_model(self):
        prediction = json.loads(json.dumps(predict_development()))
        with patch("adapters.imageprogram_reference.contextual_contour_cc02_v_audit."
                   "_public_observe", side_effect=AssertionError("inference during grading")):
            result = grade_development(prediction, expected_prediction_sha256=_sha_json(prediction))
        self.assertEqual(result["summary"]["by_arm"]["B"]["correct_members"], 7)

    def test_anchored_digest_rejects_modified_decision(self):
        prediction = predict_development()
        digest = _sha_json(prediction)
        prediction["pregrade_receipts"][0]["decisions"][1]["action"] = "continue"
        with self.assertRaisesRegex(ValueError, "prediction-digest-mismatch"):
            grade_development(prediction, expected_prediction_sha256=digest)

    def test_wrong_case_order_omissions_config_and_source_fail_closed(self):
        original = predict_development()
        for mutation in ("order", "omission", "config", "source", "shape", "graph"):
            with self.subTest(mutation=mutation):
                prediction = copy.deepcopy(original)
                receipts = prediction["pregrade_receipts"]
                if mutation == "order":
                    receipts[0], receipts[1] = receipts[1], receipts[0]
                elif mutation == "omission":
                    receipts.pop()
                elif mutation == "config":
                    prediction["config"]["max_gap"] = 9
                elif mutation == "source":
                    prediction["source_file_sha256"]["arena_generator"] = "0" * 64
                elif mutation == "shape":
                    receipts[0]["trace"]["raster_shape"] = [36, 144]
                else:
                    receipts[0]["trace"]["graph"]["nodes"][0]["region"] = "context"
                prediction["pregrade_receipts_sha256"] = _sha_json(receipts)
                with self.assertRaises(ValueError):
                    grade_development(prediction, expected_prediction_sha256=_sha_json(prediction))

    def test_exclusive_evidence_write_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "prediction.json"
            _write_new(path, {"first": True})
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                _write_new(path, {"first": False})
            self.assertEqual(path.read_bytes(), original)

    def test_six_positive_arcs_are_literal_visible_public_pixels(self):
        for i in range(6):
            public, private = create_development_pair(i)[0]
            arc = development_private_arc(i, private)
            self.assertTrue(arc.target_xy)
            self.assertTrue(all(public["pixels_l8"][y, x] != 255
                                for x, y in arc.target_xy))
            self.assertEqual(arc.member_id, private.member_id)

    def test_six_negative_members_have_no_positive_target_arc(self):
        for i in range(6):
            public, private = create_development_pair(i)[1]
            arc = development_private_arc(i, private)
            self.assertEqual(arc.target_xy, ())
            self.assertTrue(arc.excluded_xy)
            self.assertTrue(all(public["pixels_l8"][y, x] != 255
                                for x, y in arc.excluded_xy))

    def test_weak_arc_retained_in_raster_but_lost_at_threshold(self):
        public, private = create_development_pair(3)[0]
        arc = development_private_arc(3, private)
        self.assertEqual({int(public["pixels_l8"][y, x])
                          for x, y in arc.target_xy}, {218})
        self.assertFalse(any(public["pixels_l8"][y, x] < 200
                             for x, y in arc.target_xy))

    def test_private_annotation_is_not_part_of_public_task(self):
        public, private = create_development_pair(4)[0]
        arc = development_private_arc(4, private)
        self.assertNotIn("target_xy", public)
        self.assertNotIn("excluded_xy", public)
        self.assertNotIn("expected_action", public)
        self.assertNotIn("member_id", public)
        self.assertNotIn("target_xy", str(sorted(public.keys())))
        self.assertNotEqual(_sha_json(arc.target_xy), public["raster_digest"])

    def test_development_only_stage_audit_remains_v2_and_sealed(self):
        result = run_development_audit()
        self.assertEqual(result["development_manifest_sha256"],
                         DEVELOPMENT_MANIFEST_SHA256)
        self.assertEqual(result["model_version"], "contextual-contour-cc01-v2")
        self.assertEqual(result["confirmation"], "NOT SCORED")
        self.assertEqual(result["real_art"], "NOT RUN")
        self.assertEqual(len(result["private_reviews"]), 12)
        self.assertEqual(len(result["controls"]), 3)
        self.assertEqual(len(result["pregrade_receipts"]), 15)
        self.assertEqual(result["summary"]["by_arm"]["B"]["correct_members"], 7)
        self.assertEqual(result["summary"]["by_arm"]["B"]["both_correct_pairs"], 1)
        self.assertEqual(result["summary"]["by_arm"]["B"]["false_continues"], 0)
        self.assertEqual(result["unidentifiable_public_input_count"], 0)
        self.assertEqual(
            sum(result["summary"]["b_positive_earliest_blockers"].values()), 6)
        for rec in result["pregrade_receipts"]:
            self.assertEqual(len({d["candidate_set_sha256"]
                                 for d in rec["decisions"]}), 1)
            self.assertNotIn("expected_action", rec)
            self.assertNotIn("target_xy", rec)

    def test_public_scenes_remain_distinct_with_identical_focus(self):
        for i in range(6):
            (a, _), (b, _) = create_development_pair(i)
            x0, y0, x1, y1 = a["focus_box"]
            self.assertTrue(np.array_equal(
                a["pixels_l8"][y0:y1, x0:x1],
                b["pixels_l8"][y0:y1, x0:x1],
            ))
            self.assertNotEqual(a["raster_digest"], b["raster_digest"])


if __name__ == "__main__":
    unittest.main()
