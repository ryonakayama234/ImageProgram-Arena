"""Fast safety/contract tests. Not substitutes for full W0 validation."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cc02_p02_w0_runner as r


class W0RunnerContract(unittest.TestCase):
    def test_distinct_heads_and_sha_required(self):
        with self.assertRaisesRegex(ValueError, "full-40"):
            r.preflight(Path("/model"), Path("/arena"), Path("/old"), "bad", "bad")
        with self.assertRaisesRegex(ValueError, "distinct"):
            r.preflight(Path("/same"), Path("/same"), Path("/old"), "0" * 40, "1" * 40)

    def test_dirty_repo_rejected_before_consuming_data(self):
        with patch.object(r, "repo_head", side_effect=["1" * 40, "2" * 40, r.LEGACY_SHA]):
            with patch.object(r, "repo_clean", side_effect=[True, False, True]):
                with self.assertRaisesRegex(RuntimeError, "dirty"):
                    r.preflight(Path("/a"), Path("/b"), Path("/old"), "1" * 40, "2" * 40)

    def test_wrong_head_rejected_before_checking_dirty(self):
        with patch.object(r, "repo_head", side_effect=["2" * 40, "1" * 40, r.LEGACY_SHA]):
            with self.assertRaisesRegex(RuntimeError, "head-mismatch"):
                r.preflight(Path("/a"), Path("/b"), Path("/old"), "1" * 40, "2" * 40)

    def test_immutable_json_and_log_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            r.json_new(path, {"passed": False, "fails": ["overflow"]})
            self.assertEqual(json.loads(path.read_text())["fails"], ["overflow"])
            with self.assertRaises(FileExistsError):
                r.json_new(path, {"passed": True})
            test = r.execute("failed", ["python", "-c", "import sys;sys.exit(3)"],
                             Path(tmp), Path(tmp))
            self.assertEqual(test["return_code"], 3)
            self.assertFalse(test["passed"])
            self.assertEqual(len(test["log_sha256"]), 64)

    def test_no_confirmation_import(self):
        source = Path(r.__file__).read_text()
        self.assertNotIn("create_confirmation_pair", source)
        self.assertEqual(r.LEGACY_SHA, "6d8e6399a2b0a44d08054a08b71b4a68d4d9e374")


if __name__ == "__main__":
    unittest.main()
