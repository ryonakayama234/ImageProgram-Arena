"""Synthetic-only independent Arena ROI v1 target and scoring tests.

No original user artwork, policy predicted masks or private source data.
Scoring mechanics here do NOT certify P1 replay/real-art E2E.
"""
import hashlib
import io
import unittest

import numpy as np
from PIL import Image

from adapters.imageprogram_reference.reference_target_v1 import (
    IndependentPlacementV1,
    make_public_v1_task,
    score_terminal_v1,
    target_and_masks_v1,
)
from adapters.imageprogram_reference.score_first_contact import FirstContactScoreError


def encode_l8(image):
    with io.BytesIO() as output:
        Image.fromarray(image, mode="L").save(output, format="PNG")
        return output.getvalue()


class ReferenceTargetV1Tests(unittest.TestCase):
    def setUp(self):
        crop = np.full((160, 128), 255, dtype=np.uint8)
        crop[70, 20:100] = 0
        self.png = encode_l8(crop)
        self.task = make_public_v1_task(self.png)

    def test_wolfram_geometry_and_protected_mask(self):
        p = IndependentPlacementV1(128, 160)
        self.assertEqual(p.scale, 1.5)
        self.assertEqual(p.offset, (32.0, 8.0))
        self.assertEqual(p.bounds, (32.0, 8.0, 224.0, 248.0))
        self.assertAlmostEqual(2 / p.scale, 4 / 3)
        target, editable, protected = target_and_masks_v1(self.task, self.png)
        self.assertEqual(int(editable.sum()), 192 * 240)
        self.assertTrue(np.all(~editable[:8]))
        self.assertTrue(editable[8, 32])
        self.assertTrue(editable[247, 223])
        self.assertFalse(editable[248, 224])
        np.testing.assert_array_equal(protected, ~editable)
        self.assertEqual(target.shape, (256, 256))
        self.assertEqual(target.dtype, np.dtype(bool))
        # Exact synthetic target has two adjacent raster rows due to bilinear scaling.
        self.assertTrue(target[113, 100])
        self.assertTrue(target[114, 100])
        self.assertFalse(target[115, 100])

    def test_public_task_does_not_expose_source_original_identity(self):
        expected = {
            "format", "mode", "reference_visibility", "reference_roi_sha256",
            "roi_width_px", "roi_height_px", "placement", "sampling", "region_semantics",
        }
        self.assertEqual(set(self.task), expected)
        self.assertEqual(
            self.task["reference_roi_sha256"],
            "sha256:" + hashlib.sha256(self.png).hexdigest()
        )
        for field in ("source_family", "original_path", "editable_bbox", "canvas_size_px"):
            self.assertNotIn(field, self.task)

    def test_noop_has_zero_f1_and_perfect_synthetic_target_has_one(self):
        white = np.full((256, 256), 255, dtype=np.uint8)
        baseline = score_terminal_v1(self.task, self.png, white)
        self.assertEqual(baseline["f1_2px"], 0)
        self.assertEqual(baseline["alignment_metric"], "Linf-Chebyshev")
        self.assertEqual(baseline["alignment_tolerance_world_px"], 2)
        self.assertAlmostEqual(baseline["alignment_tolerance_reference_px"], 4 / 3)
        target, _, _ = target_and_masks_v1(self.task, self.png)
        exact = np.where(target, 0, 255).astype(np.uint8)
        scored = score_terminal_v1(self.task, self.png, exact)
        self.assertAlmostEqual(scored["f1_2px"], 1.0)

    def test_rejects_private_fields_wrong_version_crop_tamper_and_protected_ink(self):
        cases = [
            dict(self.task, original_path="should-not-be-public"),
            dict(self.task, format="arena-public-reference-roi-v0"),
            dict(self.task, placement={**self.task["placement"], "margin_world_px": 0}),
            dict(self.task, roi_width_px=127),
        ]
        for task in cases:
            with self.subTest(task=task), self.assertRaises(FirstContactScoreError):
                target_and_masks_v1(task, self.png)
        tampered = encode_l8(np.zeros((160, 128), dtype=np.uint8))
        with self.assertRaisesRegex(FirstContactScoreError, "digest"):
            target_and_masks_v1(self.task, tampered)
        frame = np.full((256, 256), 255, dtype=np.uint8)
        frame[0, 0] = 0
        with self.assertRaisesRegex(FirstContactScoreError, "protected"):
            score_terminal_v1(self.task, self.png, frame)

    def test_portrait_landscape_square_isotropic_and_rejects_invalid(self):
        for width, height in ((12, 256), (256, 12), (256, 256), (93, 191)):
            with self.subTest(size=(width, height)):
                p = IndependentPlacementV1(width, height)
                x0, y0, x1, y1 = p.bounds
                self.assertAlmostEqual((x1 - x0) / width, (y1 - y0) / height)
                self.assertGreaterEqual(min(x0, y0), 8 - 1e-12)
                self.assertLessEqual(max(x1, y1), 248 + 1e-12)
        for bad in ((0, 20), (128, 0), (11, 12), (257, 12), (True, 160)):
            with self.subTest(bad=bad), self.assertRaises(FirstContactScoreError):
                IndependentPlacementV1(*bad)


if __name__ == "__main__":
    unittest.main()
