"""Counterexamples for historical replay; no ImageProgram or task factory."""
import copy
import unittest

from adapters.imageprogram_reference.legacy17_replay_audit_v1 import (
    adapt,
    digest,
    geometry,
    grade,
)


class LegacyReplayTests(unittest.TestCase):
    def setUp(self):
        self.public = [{"anchor_px": [0.5, 0.5], "focus_box": [0, 0, 4, 4],
                        "max_candidates": 10, "pixels_l8": [[0, 0, 0]]}]
        self.sha = digest(self.public[0])
        self.target = [[0.5, 0.5], [1.5, 0.5], [2.5, 0.5]]
        self.private = [{"case_id": "u", "family": "line", "group": "unique",
                         "protocol": "arena-visible-path-dev-v0", "split": "development",
                         "public_sha256": self.sha, "target_xy": self.target,
                         "excluded_xy": [], "expected_goal": "satisfied"}]
        self.prediction = {
            "protocol": "visible-path-baseline-predictions-v0",
            "public_sha256": digest(self.public), "original_confirmation": "NOT_RUN",
            "training_updates": 0, "rows": [{
                "public_sha256": self.sha, "seconds": 0.01, "prediction": {
                    "adapter": "contour-path-baseline-adapter-v0", "anchored": True,
                    "cc01": {}, "cc01_full_path": "NOT_SUPPORTED", "graph": {},
                    "partial": {"candidates": []}, "goal_status": "satisfied",
                    "termination_reason": "endpoint_only_claim", "ordered_path": self.target,
                }}]}

    def normalize(self):
        anchors = {"public": digest(self.public), "private": digest(self.private),
                   "prediction": digest(self.prediction)}
        return adapt(self.public, self.private, self.prediction, anchors)

    def score(self):
        normalized = self.normalize()
        return grade(normalized, digest(normalized))

    def test_legacy_match_does_not_invent_strict_gate_evidence(self):
        report = self.score()
        self.assertEqual(report["counts"]["unique_legacy_claim_success"], 1)
        self.assertEqual(report["full_v0_gate"], "NOT_EVALUABLE")
        self.assertIsNone(report["results"][0]["candidate_available"])
        self.assertIsNone(report["results"][0]["false_join"])

    def test_source_edit_is_rejected_before_scoring(self):
        anchors = {"public": digest(self.public), "private": digest(self.private),
                   "prediction": digest(self.prediction)}
        self.prediction["rows"][0]["prediction"]["ordered_path"] = []
        with self.assertRaisesRegex(ValueError, "unanchored-source"):
            adapt(self.public, self.private, self.prediction, anchors)

    def test_missing_prediction_and_duplicate_truth_rejected(self):
        old = self.prediction["rows"]
        self.prediction["rows"] = []
        with self.assertRaisesRegex(ValueError, "missing-or-extra-case"):
            self.normalize()
        self.prediction["rows"] = old
        self.private.append(copy.deepcopy(self.private[0]))
        with self.assertRaisesRegex(ValueError, "duplicate-or-missing-id"):
            self.normalize()

    def test_binding_uses_hashes_not_row_order(self):
        other = copy.deepcopy(self.public[0])
        other["anchor_px"] = [1.5, 0.5]
        self.public.append(other)
        truth = copy.deepcopy(self.private[0])
        truth.update(case_id="other", public_sha256=digest(other))
        self.private.insert(0, truth)
        pred = copy.deepcopy(self.prediction["rows"][0])
        pred["public_sha256"] = digest(other)
        self.prediction["rows"].append(pred)
        self.prediction["public_sha256"] = digest(self.public)
        self.assertEqual([r["case_id"] for r in self.score()["results"]], ["u", "other"])

    def test_control_goal_match_does_not_assert_reason_or_path_success(self):
        self.private[0].update(group="control", expected_goal="unknown")
        self.prediction["rows"][0]["prediction"].update(goal_status="unknown",
                                                       termination_reason="unreviewed-reason")
        report = self.score()
        self.assertEqual(report["counts"]["control_goal_match"], 1)
        self.assertFalse(report["results"][0]["legacy_claim_success"])
        self.assertEqual(report["control_reason_acceptance"], "NOT_SPECIFIED_IN_SOURCE_ORACLE")

    def test_faint_continuation_control_false_completion_even_if_path_matches(self):
        self.private[0].update(group="control", expected_goal="unknown")
        report = self.score()
        self.assertTrue(report["results"][0]["path_correct"])
        self.assertEqual(report["counts"]["false_complete"], 1)

    def test_all_hold_fails_unique(self):
        self.prediction["rows"][0]["prediction"].update(ordered_path=[], goal_status="unknown")
        self.assertEqual(self.score()["counts"]["unique_legacy_claim_success"], 0)

    def test_reversed_order_and_teleport_fail(self):
        reverse = geometry(list(reversed(self.target)), self.target, [])
        self.assertEqual(reverse["coverage"], 1)
        self.assertFalse(reverse["ordered"])
        self.assertFalse(reverse["path_correct"])
        skip = geometry([self.target[0], self.target[-1]], self.target, [])
        self.assertFalse(skip["continuous"])
        self.assertFalse(skip["path_correct"])

    def test_excluded_line_overrides_geometric_match(self):
        result = geometry(self.target, self.target, [self.target[1]])
        self.assertTrue(result["excluded_line_selected"])
        self.assertFalse(result["path_correct"])

    def test_malformed_coordinates_rejected(self):
        for bad in ([[True, 0]], [[0]], [[float("nan"), 0]]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                geometry(bad, self.target, [])

    def test_adapted_tampering_rejected(self):
        normalized = self.normalize()
        sha = digest(normalized)
        normalized["cases"][0]["goal_status"] = "unknown"
        with self.assertRaisesRegex(ValueError, "unanchored-adapted-input"):
            grade(normalized, sha)


if __name__ == "__main__":
    unittest.main()
