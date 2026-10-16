"""Actual raster extraction and adversarial evidence-boundary regression tests."""
import copy
import unittest
from unittest.mock import patch

from adapters.imageprogram_reference import contour_relation_g1_observed as trial
from adapters.imageprogram_reference import contour_relation_g1_observed_grade as scoring


class ObservedG1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Git cleanliness belongs to CLI preflight, not test-runner workspace policy.
        with patch.object(trial, "source_identity", return_value={"unit_identity": True}):
            cls.observation = trial.observe()
            cls.observation_sha = trial.digest(cls.observation)
            cls.prediction = trial.predict(cls.observation, cls.observation_sha)
        cls.labels = scoring.label(cls.observation, cls.observation_sha)

    def grade(self, *, prediction=None, observation=None):
        p = self.prediction if prediction is None else prediction
        o = self.observation if observation is None else observation
        return scoring.grade(o, trial.digest(o), self.labels, trial.digest(self.labels),
                             p, trial.digest(p))

    def test_actual_p02_support_is_preserved_without_injected_geometry(self):
        self.assertEqual(len(self.observation["rows"]), 27)
        self.assertEqual(sum(bool(r["fragments"]) for r in self.observation["rows"]), 10)
        for row in self.observation["rows"]:
            self.assertEqual(row["fragment_sha256"], trial.digest(row["fragments"]))
        scoring.validate_observation(self.observation)

    def test_crossing_source_labels_do_not_follow_predicted_edges(self):
        row = self.labels["rows"][19]  # frozen X raster, four actually observed arms
        self.assertEqual(sum(p["truth"] == "positive" for p in row["pairs"]), 2)
        self.assertEqual(sum(p["truth"] == "negative" for p in row["pairs"]), 4)
        report = self.grade()
        self.assertEqual(report["scenes"], 27)
        self.assertEqual(report["original_confirmation"], "NOT_RUN")
        self.assertGreater(report["counts"]["g1"]["unknown_possible"], 0)

    def test_anchored_mutation_is_rejected_before_scoring(self):
        changed = copy.deepcopy(self.prediction)
        changed["rows"][15]["g1"] = []
        with self.assertRaisesRegex(ValueError, "altered"):
            scoring.grade(self.observation, self.observation_sha, self.labels,
                          trial.digest(self.labels), changed, trial.digest(self.prediction))

    def test_rehashed_nonidentity_adapter_is_still_rejected(self):
        changed = copy.deepcopy(self.observation)
        node = changed["rows"][15]["fragments"][0]
        node["endpoint_a"] = (node["endpoint_a"][0] + 1, node["endpoint_a"][1])
        row = changed["rows"][15]
        row["fragment_sha256"] = trial.digest(row["fragments"])
        with self.assertRaisesRegex(ValueError, "non-identity"):
            scoring.label(changed, trial.digest(changed))

    def test_rehashed_foreign_edge_is_rejected(self):
        changed = copy.deepcopy(self.prediction)
        changed["rows"][15]["g1"][0]["dst"] = "foreign"
        with self.assertRaisesRegex(ValueError, "invalid-predicted-pair"):
            self.grade(prediction=changed)

    def test_budget_abstention_is_not_negative_control_success(self):
        changed = copy.deepcopy(self.prediction)
        changed["rows"][15]["g1"] = []
        changed["rows"][15]["g1_status"] = "pair-budget-exceeded"
        report = self.grade(prediction=changed)
        row = report["reviews"][15]["counts"]["g1"]
        self.assertEqual(row["abstain_positive"], 1)
        self.assertEqual(row["abstain_negative"], 2)
        self.assertNotIn("TN", row)

    def test_grade_does_not_call_relation_models_or_observer(self):
        from imageprogram.models import (
            branch_contour_p02,
            contextual_contour_cc01,
            contour_relation_g1,
        )

        with (patch.object(branch_contour_p02, "observe_branch", side_effect=AssertionError),
              patch.object(contextual_contour_cc01, "_relation", side_effect=AssertionError),
              patch.object(contour_relation_g1, "propose_relations", side_effect=AssertionError)):
            self.assertEqual(self.grade()["scenes"], 27)


if __name__ == "__main__":
    unittest.main()
