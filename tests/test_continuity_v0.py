"""Strict continuity tests that intentionally disagree with tolerant F1."""
import unittest

import numpy as np

from adapters.imageprogram_reference.continuity_v0 import (
    count_8_connected_components,
    diagnose_continuity_v0,
)
from adapters.imageprogram_reference.reference_target_v1 import FirstContactScoreError
from adapters.imageprogram_reference.score_first_contact import score_mask


class E1ContinuityV0Tests(unittest.TestCase):
    def setUp(self):
        self.target = np.zeros((256, 256), dtype=np.bool_)
        self.target[120, 40:52] = True
        self.editable = np.ones((256, 256), dtype=np.bool_)
        self.before = np.full((256, 256), 255, dtype=np.uint8)
        self.before[120, 40:45] = 0

    def _run(self, after):
        return diagnose_continuity_v0(
            target_mask=self.target,
            editable_mask=self.editable,
            poststroke_world_l8=self.before,
            terminal_world_l8=after,
        )

    def test_two_pixel_gap_passes_tolerant_f1_but_fails_connectedness(self):
        after = self.before.copy()
        after[120, 47:52] = 0
        tolerant = score_mask(self.target, after < 250, self.editable)
        self.assertEqual(tolerant["f1_2px"], 1.0)
        result = self._run(after)
        self.assertEqual(result["target_8_connected_components"], 1)
        self.assertEqual(result["terminal_8_connected_components"], 2)
        self.assertEqual(result["minimum_initial_added_blank_gap_px"], 2)
        self.assertEqual(result["status"], "fail")
        self.assertFalse(result["strict_connected"])

    def test_genuine_join_passes(self):
        after = self.before.copy()
        after[120, 45:52] = 0
        result = self._run(after)
        self.assertEqual(result["terminal_8_connected_components"], 1)
        self.assertEqual(result["minimum_initial_added_blank_gap_px"], 0)
        self.assertEqual(result["status"], "pass")

    def test_stop_with_same_single_line_is_not_false_gap(self):
        before = self.before.copy()
        before[120, 45:52] = 0
        result = diagnose_continuity_v0(
            target_mask=self.target,
            editable_mask=self.editable,
            poststroke_world_l8=before,
            terminal_world_l8=before.copy(),
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["appended_ink_px"], 0)
        self.assertIsNone(result["minimum_initial_added_blank_gap_px"])

    def test_disconnected_target_is_explicitly_unsupported(self):
        disconnected = self.target.copy()
        disconnected[120, 47:50] = False
        result = diagnose_continuity_v0(
            target_mask=disconnected,
            editable_mask=self.editable,
            poststroke_world_l8=self.before,
            terminal_world_l8=self.before,
        )
        self.assertEqual(result["status"], "unsupported")
        self.assertFalse(result["strict_connected"])

    def test_outside_editable_is_protected(self):
        editable = self.editable.copy()
        editable[0, 0] = False
        after = self.before.copy()
        after[0, 0] = 0
        with self.assertRaises(FirstContactScoreError):
            diagnose_continuity_v0(
                target_mask=self.target,
                editable_mask=editable,
                poststroke_world_l8=self.before,
                terminal_world_l8=after,
            )

    def test_bounded_components_and_invalid_types(self):
        self.assertEqual(count_8_connected_components(self.target), 1)
        with self.assertRaises(FirstContactScoreError):
            count_8_connected_components(self.target.astype(np.uint8))
        with self.assertRaises(FirstContactScoreError):
            self._run(np.ones((64, 64), dtype=np.uint8))


if __name__ == "__main__":
    unittest.main()
