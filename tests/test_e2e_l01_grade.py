import importlib.util
import unittest
from pathlib import Path

import numpy as np

module_file = Path(__file__).resolve().parents[1] / "benchmarks" / "e2e_l01" / "grade.py"
spec = importlib.util.spec_from_file_location("e2e_l01_grade", module_file)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GradeTest(unittest.TestCase):
    def truth(self):
        return {"orientation": "h", "cross": 128, "left_start": 50,
                "left_end": 99, "right_start": 110, "right_end": 160}

    def test_gap_fixed_and_false_spill(self):
        before = np.full((256, 256), 255, dtype=np.uint8)
        before[128, 50:100] = 0
        before[128, 110:161] = 0
        after = before.copy()
        after[128, 99:111] = 0
        self.assertTrue(module.grade_image(before, after, self.truth())["quality_pass"])
        after[100, 100] = 0
        self.assertFalse(module.grade_image(before, after, self.truth())["quality_pass"])

    def test_missing_gap(self):
        before = np.full((256, 256), 255, dtype=np.uint8)
        before[128, 50:100] = 0
        before[128, 110:161] = 0
        self.assertFalse(module.grade_image(before, before, self.truth())["quality_pass"])

    def test_vertical(self):
        t = self.truth()
        t["orientation"] = "v"
        before = np.full((256, 256), 255, dtype=np.uint8)
        before[50:100, 128] = 0
        before[110:161, 128] = 0
        after = before.copy()
        after[99:111, 128] = 0
        self.assertTrue(module.grade_image(before, after, t)["quality_pass"])


if __name__ == "__main__":
    unittest.main()
