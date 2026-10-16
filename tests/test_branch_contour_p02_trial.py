"""Independent Arena P02 fixture/sealing tests, with no confirmation scoring."""
import unittest

from adapters.imageprogram_reference.branch_contour_p02_trial import (
    CASES,
    _public_cases,
    _source_masks,
    _technical_public,
    grade,
)


class BranchContourP02ArenaTests(unittest.TestCase):
    def test_exact_technical_fixture_and_private_masks(self):
        self.assertEqual(len(CASES), 12)
        for case in CASES:
            self.assertEqual(len(case), 2)  # no target/excluded labels in PUBLIC bank
        for i in range(len(CASES)):
            name, public = _technical_public(i)
            self.assertEqual(public["pixels_l8"].shape, (72, 72))
            self.assertNotIn("expected_action", public)
            self.assertNotIn("target", public)
            target, excluded = _source_masks("technical", name + ":dummy", public)
            self.assertFalse(target & excluded)

    def test_no_confirmation_in_dataset(self):
        self.assertEqual(len(list(_public_cases())), 27)

    def test_wrong_sha_never_grades(self):
        with self.assertRaisesRegex(ValueError, "unanchored"):
            grade({"rows": [], "confirmation": "NOT_RUN"}, "0" * 64)


if __name__ == "__main__":
    unittest.main()
