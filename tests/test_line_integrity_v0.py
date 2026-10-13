"""Synthetic pixel fixtures for diagnostics; World evidence is in the benchmark."""

import unittest

import numpy as np
from adapters.imageprogram_reference.line_integrity_v0 import (
    IntegrityThresholdsV0,
    evaluate_line_integrity_v0,
)
from PIL import Image, ImageDraw


class LineIntegrityV0Tests(unittest.TestCase):
    def evaluate(self, pixels):
        return evaluate_line_integrity_v0(
            pixels,
            source_path_world_px=[(30.5, 128.5), (225.5, 128.5)],
            editable_mask=np.ones((256, 256), dtype=bool),
        )

    def line(self):
        x = np.full((256, 256), 255, dtype=np.uint8)
        x[128, 30:226] = 0
        return x

    def test_thin_line_and_identical_raster_have_identical_quality(self):
        pixels = self.line()
        before = pixels.copy()
        first = self.evaluate(pixels)
        self.assertTrue(first["line_integrity_pass"])
        self.assertEqual(first, self.evaluate(pixels.copy()))
        np.testing.assert_array_equal(pixels, before)

    def test_extra_parallel_and_thick_ink_are_separate_violations(self):
        pixels = self.line()
        pixels[131, 90:160] = 0
        result = self.evaluate(pixels)
        self.assertFalse(result["line_integrity_pass"])
        self.assertIn("extra-parallel-ink", result["violations"])
        pixels = self.line()
        pixels[127:130, 90:160] = 0
        result = self.evaluate(pixels)
        self.assertIn("excess-width", result["violations"])

    def test_connected_kink_is_not_accepted_by_connectedness_alone(self):
        image = Image.new("L", (256, 256), 255)
        ImageDraw.Draw(image).line(
            [(30, 128), (96, 128), (104, 131), (112, 128), (225, 128)], fill=0
        )
        result = self.evaluate(np.array(image))
        self.assertEqual(result["connected_components"], 1)
        self.assertIn("local-bend-or-jitter", result["violations"])

    def test_blank_and_gap_are_not_clean_completed_contours(self):
        self.assertFalse(
            self.evaluate(np.full((256, 256), 255, dtype=np.uint8))[
                "line_integrity_pass"
            ]
        )
        pixels = self.line()
        pixels[128, 100:112] = 255
        result = self.evaluate(pixels)
        self.assertFalse(result["line_integrity_pass"])
        self.assertIn("incomplete-contour", result["violations"])

    def test_protected_ink_unknown_source_and_invalid_thresholds(self):
        pixels = self.line()
        mask = np.ones((256, 256), dtype=bool)
        mask[128, 30] = False
        result = evaluate_line_integrity_v0(
            pixels,
            source_path_world_px=[(30.5, 128.5), (225.5, 128.5)],
            editable_mask=mask,
        )
        self.assertIn("protected-ink", result["violations"])
        result = evaluate_line_integrity_v0(
            pixels,
            source_path_world_px=[(30.0, 30.0), (40.0, 30.0)],
            editable_mask=mask,
        )
        self.assertEqual(result["status"], "unknown")
        for v in (True, float("nan"), 0, 99):
            with self.assertRaises(ValueError):
                IntegrityThresholdsV0(max_integrated_width_world_px=v)


if __name__ == "__main__":
    unittest.main()
