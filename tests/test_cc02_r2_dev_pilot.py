"""New DEV fixture contract; no need to import/execute ImageProgram."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.cc02_r2_candidate_review import digest
from adapters.imageprogram_reference.cc02_r2_dev_pilot import prepare, task


class PilotContracts(unittest.TestCase):
    def test_public_task_contains_no_labels(self):
        public, accepted = task("longer-neighbor", False)
        self.assertEqual(set(public), {
            "pixels_l8", "raster_sha256", "focus_box", "anchor_px", "threshold",
            "dominance_ratio", "max_candidates"})
        self.assertEqual(accepted[0], [13.5, 23.5])
        self.assertEqual(accepted[-1], [39.5, 23.5])
        self.assertEqual(public["pixels_l8"][23][13], 0)
        self.assertEqual(public["pixels_l8"][41][52], 0)

    def test_transpose_coordinates_and_pixels_agree(self):
        a, p = task("longer-neighbor", False)
        b, q = task("longer-neighbor", True)
        self.assertEqual(b["pixels_l8"][13][23], a["pixels_l8"][23][13])
        self.assertEqual(q, [[y, x] for x, y in p])
        self.assertEqual(b["anchor_px"], [23.5, 13.5])

    def test_faint_target_is_separate_negative_diagnostic(self):
        public, accepted = task("faint-target", False)
        self.assertEqual(public["pixels_l8"][23][13], 180)
        self.assertEqual(public["pixels_l8"][41][13], 0)
        self.assertEqual(accepted[0], [13.5, 23.5])

    def test_prepare_retains_all_cases_and_hash_binds_private(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "dev"
            public, private = prepare(root)
            self.assertEqual(len(public["cases"]), 9)
            self.assertEqual(len(private["cases"]), 9)
            self.assertEqual(private["public_sha256"], digest(public))
            self.assertEqual(len({row["case_id"] for row in public["cases"]}), 9)
            self.assertEqual(sum(x["kind"] == "unique_path" for x in private["cases"]), 8)
            self.assertEqual(private["cases"][-1]["accepted_paths_xy"], [])
            for i, row in enumerate(public["cases"]):
                task_body = json.loads((root / "public_tasks" / f"task-{i:02d}.json").read_text())
                self.assertEqual(row["public_task_sha256"], digest(task_body))
                self.assertNotIn("accepted_paths_xy", task_body)
            with self.assertRaises(FileExistsError):
                prepare(root)


if __name__ == "__main__":
    unittest.main()
