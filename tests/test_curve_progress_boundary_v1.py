"""Paired experiment freeze, labels and one-factor management intervention."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from adapters.imageprogram_reference.curve_progress_boundary_v1 import (
    _acceptance,
    _cases,
    _intervene,
    _validate_reserved_report,
    run,
)


class CurveProgressBoundaryV1Tests(unittest.TestCase):
    def evidence(self):
        config = dict(
            split="development",
            model_sha="model",
            arena_sha="arena",
            source_fingerprints={
                "model_observer": "observer",
                "arena_benchmark": "benchmark",
            },
        )
        rows = []
        for case in _cases("development"):
            status = case["expected"] if case["expected"] != "diagnostic" else "unknown"
            rows.append(
                dict(
                    id=case["id"],
                    expected=case["expected"],
                    candidate_correct=status == "measured",
                    source_arc_error_world_px=0.0 if status == "measured" else None,
                    source_replay_verified=True,
                    protected_ink_px=0,
                    measurement_motor_actions=0,
                    measurement=dict(
                        status=status,
                        coverage="unverified",
                        baseline=dict(coverage="unverified"),
                    ),
                )
            )
        payload = (json.dumps(config, indent=2, sort_keys=True) + "\n").encode()
        return dict(
            configuration=config,
            configuration_hash="sha256:" + hashlib.sha256(payload).hexdigest(),
            results=rows,
        )

    def test_reserved_rejects_missing_changed_failed_or_dropped_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "absent"
            with self.assertRaisesRegex(ValueError, "development report"):
                run(out, "reserved")
            self.assertFalse(out.exists())
        report = self.evidence()
        fingerprints = report["configuration"]["source_fingerprints"]
        _validate_reserved_report(report, "model", "arena", fingerprints)
        with self.assertRaises(ValueError):
            _validate_reserved_report(report, "new-model", "arena", fingerprints)
        report["results"][0]["candidate_correct"] = False
        report["results"][0]["source_arc_error_world_px"] = 10.0
        self.assertFalse(_acceptance(report["results"]))
        with self.assertRaises(ValueError):
            _validate_reserved_report(report, "model", "arena", fingerprints)
        report = self.evidence()
        report["results"].pop()
        with self.assertRaises(ValueError):
            _validate_reserved_report(report, "model", "arena", fingerprints)

    def test_old_reserved_is_regression_and_new_families_are_disjoint(self):
        development = {
            c["family"] for c in _cases("development") + _cases("regression")
        }
        reserved = _cases("reserved")
        self.assertEqual(len(reserved), 48)
        self.assertEqual(len({c["family"] for c in reserved}), 4)
        self.assertFalse(development.intersection(c["family"] for c in reserved))
        self.assertEqual(len(_cases("regression")), 66)

    def test_normal_intervention_preserves_start_and_is_in_world_units(self):
        source = [(20.0, 40.0), (30.0, 40.0), (40.0, 40.0), (50.0, 40.0)]
        original = list(source)
        changed = _intervene(source, dict(intervention="normal", value=3.0), scale=1.5)
        self.assertEqual(source, original)
        self.assertEqual(changed[0], source[0])
        self.assertAlmostEqual(
            np.linalg.norm(np.array(changed[-1]) - source[-1]) * 1.5, 3.0
        )
        coarse = _intervene(source, dict(intervention="coarse", value=2), scale=1.5)
        self.assertEqual(coarse[0], source[0])
        self.assertEqual(coarse[-1], source[-1])


if __name__ == "__main__":
    unittest.main()
