"""Pure G fixed-input diagnostic and private grade binding regression."""
import unittest

from adapters.imageprogram_reference.contour_relation_g1_trial import (
    _canonical_sha,
    grade,
    predict,
)


class G1ArenaTests(unittest.TestCase):
    def test_score_all_declared_fixed_geometry_cases(self):
        report = predict()
        graded = grade(report, _canonical_sha(report))
        self.assertEqual(len(report["records"]), 8)
        self.assertEqual(graded["scored_pairs"], 6)
        self.assertEqual(graded["g0_correct"], 4)
        self.assertEqual(graded["g1_correct"], 6)
        self.assertEqual(graded["original_confirmation"], "NOT_RUN")

    def test_mutated_receipt_fails_before_private_grade(self):
        report = predict()
        original_sha = _canonical_sha(report)
        report["records"][0]["g1_status"] = "tampered"
        with self.assertRaisesRegex(ValueError, "unanchored"):
            grade(report, original_sha)

    def test_target_labels_not_in_public_record(self):
        report = predict()
        self.assertNotIn("source_derived_label", str(report))
        self.assertEqual(report["independent_annotation"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
