"""No-Model-import P03 scorer contract and generator tests."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference import cc02_p03_pilot as pilot
from adapters.imageprogram_reference import cc02_p03_review as p03
from adapters.imageprogram_reference.cc02_r2_candidate_review import MODEL_VERSION as R2_VERSION
from adapters.imageprogram_reference.cc02_r2_candidate_review import digest


def candidate(y, lo, hi):
    path = [[float(x) + 0.5, float(y) + 0.5] for x in range(lo, hi + 1)]
    tup = tuple(tuple(xy) for xy in path)
    sha = digest(min(tup, tuple(reversed(tup))))
    return {
        "candidate_id": "path-" + sha[:20],
        "source_candidate_id": "candidate-000",
        "path_sha256": sha,
        "ordered_xy": path,
        "start_xy": path[0],
        "end_xy": path[-1],
        "endpoint_kinds": ["observed-termination", "observed-termination"],
        "length_px": float(hi - lo),
        "support_vertices": len(path),
    }


def fixture():
    target, decoy = candidate(23, 13, 39), candidate(41, 10, 52)
    base = {
        "protocol": R2_VERSION, "stage": "public-candidate-bank",
        "private_target_used": False, "observer_source_sha256": "f" * 64,
        "raster_sha256": "a" * 64, "candidates": [decoy],
        "legacy_selected_candidate_id": decoy["candidate_id"],
        "status": "observed", "reason": "dominant-unbranched-focus-segment",
        "goal_status": "unknown", "endpoint_verified": False,
        "diagnostic_work": {"candidate_count": 1, "exported_path_vertices": 43},
    }
    base["canonical_sha256"] = digest(base)
    path = copy.deepcopy(target)
    path["candidate_id"] = "weak-path-" + path["path_sha256"][:20]
    for unused in ("source_candidate_id", "length_px"):
        path.pop(unused)
    path.update({"mean_observed_l8": 180.0,
                 "evidence_kind": "weak-only-ordered-path", "ownership": "unknown"})
    weak = {
        "protocol": p03.MODEL_VERSION, "stage": "public-weak-path-evidence",
        "raster_sha256": "a" * 64, "base_r2_sha256": base["canonical_sha256"],
        "base_r2": base, "weak_observer_source_sha256": "b" * 64,
        "weak_band_l8": [145, 200], "weak_status": "ok",
        "weak_observer_status": "observed", "weak_paths": [path],
        "diagnostic_work": {"weak_candidate_count": 1, "weak_path_vertices": 27},
        "private_target_used": False, "goal_status": "unknown",
        "endpoint_verified": False, "weak_selected_candidate_id": None,
    }
    weak["canonical_sha256"] = digest(weak)
    public = {"protocol": p03.VERSION, "split": "development", "cases": [
        {"case_id": "test", "raster_sha256": "a" * 64,
         "public_task_sha256": "c" * 64}
    ]}
    private = {"protocol": p03.VERSION, "public_sha256": digest(public),
               "cases": [{"case_id": "test", "family_id": "test-family",
                          "kind": "unique_path",
                          "accepted_paths_xy": [target["ordered_xy"]],
                          "excluded_paths_xy": [decoy["ordered_xy"]]}]}
    prediction = {"protocol": p03.VERSION, "public_sha256": digest(public),
                  "cases": [{"case_id": "test", "public_task_sha256": "c" * 64,
                             "model_git_commit": "1" * 40, "observation": weak}]}
    return public, private, prediction


def grade(bundle):
    return p03.grade(*bundle, *(digest(value) for value in bundle))


def rehash(bundle):
    obs = bundle[2]["cases"][0]["observation"]
    obs["canonical_sha256"] = digest({key: value for key, value in obs.items()
                                       if key != "canonical_sha256"})


class P03IndependentReviewTests(unittest.TestCase):
    def setUp(self):
        self.bundle = fixture()

    def test_missing_r2_target_recovered_without_changing_selection(self):
        result = grade(self.bundle)
        self.assertEqual(result["counts"]["newly_recovered"], 1)
        self.assertEqual(result["counts"]["baseline_available"], 0)
        self.assertEqual(result["counts"]["p03_available"], 1)
        self.assertEqual(result["completion"], "NOT_EVALUABLE")
        self.assertFalse(result["model_was_reinvoked"])

    def test_target_only_prefix_does_not_match(self):
        self.bundle[1]["cases"][0]["accepted_paths_xy"] = [
            self.bundle[1]["cases"][0]["accepted_paths_xy"][0][:-5]]
        self.assertEqual(grade(self.bundle)["counts"]["newly_recovered"], 0)

    def test_forced_ownership_rejected(self):
        self.bundle[2]["cases"][0]["observation"]["weak_paths"][0]["ownership"] = "target"
        rehash(self.bundle)
        with self.assertRaisesRegex(ValueError, "unearned-target-ownership"):
            grade(self.bundle)

    def test_weak_selected_rejected(self):
        self.bundle[2]["cases"][0]["observation"]["weak_selected_candidate_id"] = "x"
        rehash(self.bundle)
        with self.assertRaisesRegex(ValueError, "false-selection"):
            grade(self.bundle)

    def test_base_forgery_rejected(self):
        self.bundle[2]["cases"][0]["observation"]["base_r2"]["status"] = "unknown"
        rehash(self.bundle)
        with self.assertRaisesRegex(ValueError, "base-r2-sha-drift"):
            grade(self.bundle)

    def test_wrong_external_prediction_sha_rejected(self):
        b = self.bundle
        with self.assertRaisesRegex(ValueError, "external-sha-mismatch"):
            p03.grade(*b, digest(b[0]), digest(b[1]), "0" * 64)

    def test_weak_geometry_splice_rejected(self):
        c = self.bundle[2]["cases"][0]["observation"]["weak_paths"][0]
        c["ordered_xy"][1] = [63.5, 63.5]
        rehash(self.bundle)
        with self.assertRaisesRegex(ValueError, "gap-or-duplicate"):
            grade(self.bundle)

    def test_fail_closed_budget(self):
        obs = self.bundle[2]["cases"][0]["observation"]
        obs["weak_status"] = "weak-candidate-budget-exceeded"
        rehash(self.bundle)
        with self.assertRaisesRegex(ValueError, "non-atomic-weak-budget"):
            grade(self.bundle)

    def test_dev_and_confirmation_generators_are_disjoint(self):
        with tempfile.TemporaryDirectory() as temp:
            dev, _ = pilot.prepare(Path(temp) / "dev", "development")
            confirm, _ = pilot.prepare(Path(temp) / "confirm", "confirmation")
        self.assertEqual(len(dev["cases"]), 29)
        self.assertEqual(len(confirm["cases"]), 17)
        self.assertFalse({x["case_id"] for x in dev["cases"]}
                         & {x["case_id"] for x in confirm["cases"]})

    def test_generated_target_uses_actual_public_pixels(self):
        for shape in ("flat", "incline", "arc", "sine"):
            data, target, excluded = pilot.new_task(shape, 180)
            self.assertEqual(len(target), 37)
            self.assertEqual(len(excluded), 1)
            for x, y in target:
                self.assertEqual(data["pixels_l8"][int(y)][int(x)], 180)
            for a, b in zip(target, target[1:]):
                self.assertLessEqual(abs(b[1] - a[1]), 1.0)


if __name__ == "__main__":
    unittest.main()
