"""Independent scorer contract tests: handmade coordinates, NO Model invocation."""
from __future__ import annotations

import copy
import unittest

from adapters.imageprogram_reference.cc02_r2_candidate_review import (
    MODEL_VERSION,
    VERSION,
    digest,
    grade,
)


def candidate(y, lo, hi):
    path = [[x + 0.5, y + 0.5] for x in range(lo, hi + 1)]
    p = tuple(tuple(v) for v in path)
    sha = digest(min(p, tuple(reversed(p))))
    return {"candidate_id": "path-" + sha[:20], "source_candidate_id": "candidate-000",
            "path_sha256": sha, "ordered_xy": path, "start_xy": path[0],
            "end_xy": path[-1], "endpoint_kinds": [
                "observed-termination", "observed-termination"],
            "length_px": float(hi-lo), "support_vertices": len(path)}


def sample():
    target = candidate(23, 13, 39)
    decoy = candidate(41, 10, 52)
    obs = {"protocol": MODEL_VERSION, "stage": "public-candidate-bank",
           "private_target_used": False, "observer_source_sha256": "f" * 64,
           "raster_sha256": "a" * 64, "candidates": [target, decoy],
           "legacy_selected_candidate_id": decoy["candidate_id"], "status": "observed",
           "reason": "dominant-unbranched-focus-segment",
           "goal_status": "unknown", "endpoint_verified": False,
           "diagnostic_work": {"candidate_count": 2}}
    obs["canonical_sha256"] = digest(obs)
    public = {"protocol": VERSION, "split": "development", "cases": [
        {"case_id": "line", "raster_sha256": "a" * 64, "public_task_sha256": "b" * 64},
    ]}
    private = {"protocol": VERSION, "public_sha256": digest(public), "cases": [
        {"case_id": "line", "family_id": "longer-neighbor", "kind": "unique_path",
         "accepted_paths_xy": [target["ordered_xy"]]},
    ]}
    prediction = {"protocol": VERSION, "public_sha256": digest(public), "cases": [
        {"case_id": "line", "public_task_sha256": "b" * 64, "model_git_commit": "1" * 40,
         "observation": obs},
    ]}
    return public, private, prediction


def review(bundle):
    return grade(*bundle, *(digest(v) for v in bundle))


class CandidateReviewTests(unittest.TestCase):
    def setUp(self):
        self.bundle = sample()

    def test_candidate_present_but_old_selection_wrong(self):
        result = review(self.bundle)
        row = result["rows"][0]
        self.assertTrue(row["candidate_available"])
        self.assertFalse(row["legacy_selected_correct"])
        self.assertTrue(row["legacy_wrong_selected_candidate"])
        self.assertEqual(result["counts"]["candidate_recall"], 1.0)
        self.assertEqual(result["counts"]["selection_accuracy_given_available"], 0.0)
        self.assertEqual(result["full_visible_endpoint_completion"], "NOT_EVALUABLE")

    def test_candidate_missing_is_P_not_R(self):
        _, _, pred = self.bundle
        decoy = pred["cases"][0]["observation"]["candidates"][1]
        pred["cases"][0]["observation"]["candidates"] = [decoy]
        pred["cases"][0]["observation"]["diagnostic_work"]["candidate_count"] = 1
        pred["cases"][0]["observation"]["canonical_sha256"] = digest({
            k: v for k, v in pred["cases"][0]["observation"].items()
            if k != "canonical_sha256"})
        result = review(self.bundle)
        self.assertFalse(result["rows"][0]["candidate_available"])
        self.assertEqual(result["counts"]["candidate_recall"], 0)
        self.assertIsNone(result["counts"]["selection_accuracy_given_available"])

    def test_candidate_present_but_hold_is_not_success(self):
        _, _, pred = self.bundle
        obs = pred["cases"][0]["observation"]
        obs["legacy_selected_candidate_id"] = None
        obs["status"] = "unknown"
        obs["canonical_sha256"] = digest({k: v for k, v in obs.items()
                                           if k != "canonical_sha256"})
        result = review(self.bundle)
        self.assertTrue(result["rows"][0]["candidate_available"])
        self.assertEqual(result["counts"]["legacy_hold"], 1)
        self.assertEqual(result["counts"]["legacy_selected_correct"], 0)

    def test_true_path_reversed_is_accepted_for_candidate_availability(self):
        _, private, _ = self.bundle
        path = private["cases"][0]["accepted_paths_xy"][0]
        private["cases"][0]["accepted_paths_xy"] = [list(reversed(path))]
        self.assertEqual(review(self.bundle)["counts"]["candidate_available"], 1)

    def test_only_prefix_target_does_not_count_as_exact_available(self):
        _, private, _ = self.bundle
        private["cases"][0]["accepted_paths_xy"] = [
            private["cases"][0]["accepted_paths_xy"][0][:-4]]
        self.assertEqual(review(self.bundle)["counts"]["candidate_available"], 0)

    def test_private_label_in_public_denied(self):
        public, private, prediction = self.bundle
        public["cases"][0]["allowed_path"] = [[13.5, 23.5]]
        private["public_sha256"] = digest(public)
        prediction["public_sha256"] = digest(public)
        with self.assertRaisesRegex(ValueError, "public-task-contract"):
            review(self.bundle)

    def test_private_label_use_claim_rejected(self):
        _, _, pred = self.bundle
        o = pred["cases"][0]["observation"]
        o["private_target_used"] = True
        o["canonical_sha256"] = digest({k: v for k, v in o.items()
                                         if k != "canonical_sha256"})
        with self.assertRaisesRegex(ValueError, "missing-public-source-provenance"):
            review(self.bundle)

    def test_sha_tamper_rejected(self):
        public, private, pred = self.bundle
        pred["public_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "version-parent-or-split-drift"):
            review(self.bundle)

    def test_missing_case_rejected(self):
        self.bundle[2]["cases"].clear()
        with self.assertRaisesRegex(ValueError, "case-universe-drift"):
            review(self.bundle)

    def test_duplicate_vertex_rejected(self):
        _, _, pred = self.bundle
        obs = pred["cases"][0]["observation"]
        c = obs["candidates"][0]
        c["ordered_xy"].insert(1, copy.deepcopy(c["ordered_xy"][0]))
        obs["canonical_sha256"] = digest({k: v for k, v in obs.items()
                                          if k != "canonical_sha256"})
        with self.assertRaisesRegex(ValueError, "observed-candidate-gap-or-duplicate"):
            review(self.bundle)

    def test_identity_forgery_rejected(self):
        _, _, pred = self.bundle
        obs = pred["cases"][0]["observation"]
        obs["candidates"][0]["candidate_id"] = "path-forged"
        obs["canonical_sha256"] = digest({k: v for k, v in obs.items()
                                          if k != "canonical_sha256"})
        with self.assertRaisesRegex(ValueError, "candidate-identity-or-path-drift"):
            review(self.bundle)

    def test_control_is_not_positive_success(self):
        public, private, prediction = self.bundle
        public["cases"].append({"case_id": "blank", "raster_sha256": "z" * 64,
                                "public_task_sha256": "e" * 64})
        private["public_sha256"] = digest(public)
        private["cases"].append({"case_id": "blank", "family_id": "control",
                                 "kind": "observation_insufficient",
                                 "accepted_paths_xy": []})
        prediction["public_sha256"] = digest(public)
        obs = {"protocol": MODEL_VERSION, "stage": "public-candidate-bank",
               "private_target_used": False, "observer_source_sha256": "f" * 64,
               "raster_sha256": "z" * 64, "candidates": [],
               "legacy_selected_candidate_id": None, "status": "unsupported",
               "reason": "no-high-contrast-ink",
               "goal_status": "unknown", "endpoint_verified": False,
               "diagnostic_work": {"candidate_count": 0}}
        obs["canonical_sha256"] = digest(obs)
        prediction["cases"].append({"case_id": "blank", "public_task_sha256": "e" * 64,
                                     "model_git_commit": "1" * 40, "observation": obs})
        graded = review(self.bundle)
        self.assertEqual(graded["counts"]["unique"], 1)
        self.assertEqual(graded["counts"]["controls"], 1)


if __name__ == "__main__":
    unittest.main()
