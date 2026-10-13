"""Fixed candidates, fresh families, and pre-execution choices are separate gates."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.line_integrity_benchmark_v0 import (
    _cases,
    _check_development,
    run,
)


class LineIntegrityBenchmarkV0Tests(unittest.TestCase):
    def evidence(self):
        config = dict(
            split="development",
            model_sha="model",
            arena_sha="arena",
            source_fingerprints={"x": "hash"},
        )
        rows = []
        for case in _cases("development"):
            rows.append(
                dict(
                    id=case["id"],
                    good_id="g",
                    bad_id="b",
                    arms={
                        "g": dict(
                            integrity=dict(line_integrity_pass=True),
                            shape=dict(f1_2px=1.0),
                            source_replay_verified=True,
                            protected_ink_px=0,
                        ),
                        "b": dict(
                            integrity=dict(line_integrity_pass=False),
                            shape=dict(f1_2px=1.0),
                            source_replay_verified=True,
                            protected_ink_px=0,
                        ),
                    },
                    quality_choice=dict(selected_candidate_id="g"),
                    quality_selected_actual_pass=True,
                    decisions_before_execution=True,
                    no_measurement_motor=True,
                )
            )
        raw = (json.dumps(config, indent=2, sort_keys=True) + "\n").encode()
        return dict(
            configuration=config,
            configuration_hash="sha256:" + hashlib.sha256(raw).hexdigest(),
            results=rows,
        )

    def test_reserved_freeze_rejects_source_change_failure_and_missing_rows(self):
        report = self.evidence()
        _check_development(report, "model", "arena", {"x": "hash"})
        with self.assertRaises(ValueError):
            _check_development(report, "other", "arena", {"x": "hash"})
        report["results"][0]["decisions_before_execution"] = False
        with self.assertRaises(ValueError):
            _check_development(report, "model", "arena", {"x": "hash"})
        report = self.evidence()
        report["results"].pop()
        with self.assertRaises(ValueError):
            _check_development(report, "model", "arena", {"x": "hash"})

    def test_missing_development_and_pilot_reserved_create_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "absent"
            for report, pilot in [(None, False), (Path(tmp) / "unread.json", True)]:
                with self.assertRaises(ValueError):
                    run(out, "reserved", report, pilot)
                self.assertFalse(out.exists())

    def test_development_and_reserved_cover_all_defects_and_different_families(self):
        dev, test = _cases("development"), _cases("reserved")
        self.assertEqual(len(dev), 20)
        self.assertEqual(len(test), 10)
        self.assertEqual({c["damage"] for c in dev}, {c["damage"] for c in test})
        self.assertFalse({c["family"] for c in dev} & {c["family"] for c in test})
        self.assertEqual({c["good_mode"] for c in dev}, {0, 1, 2})


if __name__ == "__main__":
    unittest.main()
