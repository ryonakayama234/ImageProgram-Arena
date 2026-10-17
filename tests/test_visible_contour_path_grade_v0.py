"""Synthetic contract tests only; no historical CC-02 or confirmation data."""
from __future__ import annotations

import unittest

from adapters.imageprogram_reference.visible_contour_path_grade_v0 import (
    VERSION,
    digest,
    grade,
)


class PathGradeTests(unittest.TestCase):
    def setUp(self):
        graph = {"nodes": ["s", "a", "b", "c"],
                 "edges": [{"id": "e1", "u": "s", "v": "a"},
                           {"id": "e2", "u": "a", "v": "b"},
                           {"id": "e3", "u": "a", "v": "c"}]}
        graph_hash = digest(graph)
        self.public = {"protocol": VERSION, "split": "development", "cases": [
            {"case_id": "u", "family_id": "family-1", "start_node": "s",
             "raster_sha256": "a" * 64, "candidate_graph_sha256": graph_hash, **graph},
            {"case_id": "control", "family_id": "family-2", "start_node": "s",
             "raster_sha256": "b" * 64, "candidate_graph_sha256": graph_hash, **graph},
        ]}
        public_sha = digest(self.public)
        self.private = {"protocol": VERSION, "public_sha256": public_sha, "cases": [
            {"case_id": "u", "kind": "unique_path", "allowed_edge_paths": [["e1", "e2"]],
             "expected_goal": "satisfied", "expected_reasons": ["verified_visible_endpoint"]},
            {"case_id": "control", "kind": "ambiguous", "allowed_edge_paths": [],
             "expected_goal": "unknown", "expected_reasons": ["ambiguous"]},
        ]}
        self.pred = {"protocol": VERSION, "public_sha256": public_sha, "cases": [
            {"case_id": "u", "candidate_graph_sha256": graph_hash,
             "candidate_paths": [["e1", "e2"], ["e1", "e3"]],
             "selected_path": ["e1", "e2"], "goal_status": "satisfied",
             "termination_reason": "verified_visible_endpoint", "endpoint_evidence": {
                 "node_id": "b", "observation_sha256": "a" * 64,
                 "unresolved_continuations": 0}, "work_units": 3},
            {"case_id": "control", "candidate_graph_sha256": graph_hash,
             "candidate_paths": [], "selected_path": None, "goal_status": "unknown",
             "termination_reason": "ambiguous", "endpoint_evidence": None,
             "work_units": 1},
        ]}

    def run_grade(self):
        return grade(self.public, self.private, self.pred,
                     digest(self.public), digest(self.private), digest(self.pred))

    def test_correct_unique_and_ambiguous_control(self):
        report = self.run_grade()
        self.assertEqual(report["counts"]["success"], 2)
        self.assertEqual(report["counts"]["candidate_available"], 1)
        self.assertEqual(report["counts"]["false_join"], 0)

    def test_wrong_branch_fails_even_when_start_and_graph_valid(self):
        row = self.pred["cases"][0]
        row.update({"selected_path": ["e1", "e3"], "endpoint_evidence": {
            "node_id": "c", "observation_sha256": "a" * 64,
            "unresolved_continuations": 0}})
        output = self.run_grade()
        self.assertEqual(output["counts"]["false_join"], 1)
        self.assertEqual(output["counts"]["success"], 1)

    def test_all_hold_is_not_success(self):
        row = self.pred["cases"][0]
        row.update({"selected_path": None, "goal_status": "unknown",
                    "termination_reason": "ambiguous", "endpoint_evidence": None})
        self.assertEqual(self.run_grade()["counts"]["success"], 1)

    def test_disconnected_path_rejected(self):
        row = self.pred["cases"][0]
        row.update({"candidate_paths": [["e2"]], "selected_path": ["e2"],
                    "goal_status": "unknown", "endpoint_evidence": None})
        with self.assertRaisesRegex(ValueError, "disconnected-path"):
            self.run_grade()

    def test_case_missing_rejected(self):
        self.pred["cases"].pop()
        with self.assertRaisesRegex(ValueError, "missing-or-extra-case"):
            self.run_grade()

    def test_private_cannot_enter_public_contract(self):
        self.public["cases"][0]["private_truth"] = True
        self.private["public_sha256"] = digest(self.public)
        self.pred["public_sha256"] = digest(self.public)
        with self.assertRaisesRegex(ValueError, "public-case-contract"):
            self.run_grade()

    def test_changed_public_parent_sha_rejected(self):
        self.pred["public_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "protocol-or-parent-hash-mismatch"):
            self.run_grade()

    def test_satisfied_without_endpoint_evidence_rejected(self):
        self.pred["cases"][0]["endpoint_evidence"] = None
        with self.assertRaisesRegex(ValueError, "unsupported-satisfied-claim"):
            self.run_grade()

    def test_oracle_path_must_be_contiguous(self):
        self.private["cases"][0]["allowed_edge_paths"] = [["e2"]]
        with self.assertRaisesRegex(ValueError, "disconnected-path"):
            self.run_grade()


if __name__ == "__main__":
    unittest.main()
