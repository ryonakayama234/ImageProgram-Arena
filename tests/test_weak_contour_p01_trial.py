"""Arena-only source-mask checks and sealed experiment boundaries."""
import unittest
from unittest.mock import patch

from adapters.imageprogram_reference.weak_contour_p01_trial import (
    CONFIG,
    annotation,
    grade,
    public_cases,
)


class WeakTrialTests(unittest.TestCase):
    def test_twenty_nine_inputs_without_confirmation_or_public_answers(self):
        from adapters.imageprogram_reference import (
            contextual_contour_cc02_tasks as tasks,
        )

        with patch.object(tasks, "create_confirmation_pair", side_effect=AssertionError("sealed")):
            cases = dict(public_cases())
        self.assertEqual(len(cases), 29)
        for public in cases.values():
            self.assertNotIn("target", public)
            self.assertNotIn("expected_action", public)
        self.assertEqual(CONFIG["repetitions"], 3)

    def test_source_target_and_competing_pixels_are_disjoint_and_visible(self):
        for key, public in public_cases():
            target, excluded = annotation(key, public)
            self.assertFalse(target & excluded)
            self.assertTrue(all(public["pixels_l8"][y, x] < 255 for x, y in target | excluded))
        cases = dict(public_cases())
        target, excluded = annotation("screen-parallel", cases["screen-parallel"])
        self.assertEqual(target, {(x, 30) for x in range(59, 70)})
        self.assertEqual(excluded, {(x, 43) for x in range(59, 70)})

    def test_grading_rejects_receipt_without_valid_external_digest(self):
        with self.assertRaisesRegex(ValueError, "receipt-digest"):
            grade({"receipt_sha256": "0" * 64}, "0" * 64)


if __name__ == "__main__":
    unittest.main()
