"""Provenance rejection must happen before matrix artifacts are created."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters.imageprogram_reference.run_e1_join_matrix_v0 import (
    BASELINE_SHA,
    _checked_model,
    run_matrix,
)


class JoinMatrixProvenanceTests(unittest.TestCase):
    def test_wrong_producer_commit_creates_no_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "must-not-exist"
            with patch(
                "adapters.imageprogram_reference.run_e1_join_matrix_v0._git",
                return_value="0" * 40,
            ), self.assertRaisesRegex(ValueError, "exact frozen commit"):
                run_matrix(out, root / "baseline", root / "candidate")
            self.assertFalse(out.exists())

    def test_dirty_frozen_producer_is_rejected(self):
        with patch(
            "adapters.imageprogram_reference.run_e1_join_matrix_v0._git",
            side_effect=[BASELINE_SHA, " M src/changed.py"],
        ), self.assertRaisesRegex(ValueError, "clean"):
            _checked_model(Path("unused"), BASELINE_SHA)

    def test_missing_producer_interpreter_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "adapters.imageprogram_reference.run_e1_join_matrix_v0._git",
            side_effect=[BASELINE_SHA, ""],
        ), self.assertRaisesRegex(ValueError, "locked render environment"):
            _checked_model(Path(tmp), BASELINE_SHA)


if __name__ == "__main__":
    unittest.main()
