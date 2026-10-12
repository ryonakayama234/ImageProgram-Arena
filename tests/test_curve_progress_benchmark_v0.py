"""The reserved split cannot run on missing, changed, or failed development evidence."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.curve_progress_benchmark_v0 import (
    _cases,
    _project_arc,
    _validate_reserved_report,
    run,
)


class CurveProgressBenchmarkTests(unittest.TestCase):
    def evidence(self):
        config = {
            "split": "development",
            "model_sha": "model",
            "arena_sha": "arena",
            "source_fingerprints": {
                "model_observer": "observer",
                "arena_benchmark": "benchmark",
            },
        }
        payload = (json.dumps(config, indent=2, sort_keys=True) + "\n").encode()
        rows = [
            {"id": c["id"], "passed": True, "source_replay_verified": True}
            for c in _cases("development")
        ]
        return {
            "configuration": config,
            "configuration_hash": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "total": len(rows),
            "passed": len(rows),
            "results": rows,
        }

    def test_missing_development_gate_creates_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "must-not-exist"
            with self.assertRaisesRegex(ValueError, "development report"):
                run(out, "reserved")
            self.assertFalse(out.exists())

    def test_changed_model_or_hidden_failed_row_is_rejected(self):
        evidence = self.evidence()
        fingerprints = evidence["configuration"]["source_fingerprints"]
        _validate_reserved_report(evidence, "model", "arena", fingerprints)
        with self.assertRaises(ValueError):
            _validate_reserved_report(evidence, "changed-model", "arena", fingerprints)
        evidence["results"][0]["passed"] = False
        with self.assertRaises(ValueError):
            _validate_reserved_report(evidence, "model", "arena", fingerprints)

    def test_arena_source_geometry_label_has_known_arc_position(self):
        arc, distance = _project_arc((4.0, 1.0), [(0.0, 0.0), (10.0, 0.0)])
        self.assertEqual(arc, 4.0)
        self.assertEqual(distance, 1.0)


if __name__ == "__main__":
    unittest.main()
