"""Run every Arena test under its declared Model provenance, without skips.

The historical E1 experiment intentionally requires Model PR #81. Keep that
guard intact; do not label the latest-Model monolithic discovery a passing
suite. The partition manifest proves that no discovered test is dropped.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

LEGACY_SHA = "6d8e6399a2b0a44d08054a08b71b4a68d4d9e374"
LEGACY_MODULES = frozenset({"test_e1_paired_synthetic_v1", "test_e1_review_v1"})
ROOT = Path(__file__).resolve().parents[1]


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def discover(partition):
    loader = unittest.TestLoader()
    if partition == "legacy":
        tests = []
        for module in sorted(LEGACY_MODULES):
            tests.extend(flatten(loader.discover(str(ROOT / "tests"),
                                                pattern=module + ".py")))
    else:
        tests = list(flatten(loader.discover(str(ROOT / "tests"), pattern="test*.py")))
    if loader.errors:
        raise RuntimeError("test-collection-failed: " + repr(loader.errors))
    if partition == "current":
        tests = [t for t in tests if t.id().split(".")[0] not in LEGACY_MODULES]
    return tests


def save_new(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def model_identity():
    import imageprogram

    root = Path(imageprogram.__file__).resolve().parents[2]
    sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                  text=True).strip()
    return root, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-model-root", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--worker", choices=("current", "legacy"))
    args = parser.parse_args()
    if args.worker:
        model_root, model_sha = model_identity()
        if args.worker == "legacy" and model_sha != LEGACY_SHA:
            raise RuntimeError("legacy-test-model-sha-mismatch")
        if args.worker == "current":
            from imageprogram.models.contextual_contour_cc01 import VERSION

            if VERSION != "contextual-contour-cc01-v2" or model_sha == LEGACY_SHA:
                raise RuntimeError("current-test-model-version-mismatch")
        tests = discover(args.worker)
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests))
        report = {
            "partition": args.worker, "model_root": str(model_root),
            "model_sha": model_sha, "ids": [t.id() for t in tests],
            "run": result.testsRun, "failures": len(result.failures),
            "errors": len(result.errors), "skips": len(result.skipped),
            "passed": result.wasSuccessful() and not result.skipped,
        }
        save_new(args.out, report)
        raise SystemExit(0 if report["passed"] else 1)
    if args.legacy_model_root is None:
        parser.error("--legacy-model-root required")
    args.out.mkdir(parents=True, exist_ok=False)
    expected = [t.id() for t in discover("all")]
    if len(set(expected)) != len(expected):
        raise RuntimeError("duplicate-test-ids")
    reports = []
    for partition, python in (
        ("current", Path(sys.executable)),
        ("legacy", args.legacy_model_root.resolve() / ".venv/bin/python"),
    ):
        destination = args.out / (partition + ".json")
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        with (args.out / (partition + ".log")).open("x") as log:
            process = subprocess.run(
                [str(python), str(Path(__file__).resolve()), "--worker", partition,
                 "--out", str(destination)], cwd=ROOT, env=env,
                stdout=log, stderr=subprocess.STDOUT, check=False,
            )
        if not destination.exists():
            raise RuntimeError(f"worker-no-report: {partition}, exit={process.returncode}")
        report = json.loads(destination.read_text())
        report["exit_code"] = process.returncode
        reports.append(report)
    assigned = [ident for r in reports for ident in r["ids"]]
    complete = sorted(assigned) == sorted(expected) and len(assigned) == len(set(assigned))
    passed = complete and all(r["passed"] and r["exit_code"] == 0 for r in reports)
    summary = {"protocol": "cc02-arena-complete-test-matrix-v1",
               "expected_ids": expected, "coverage_exact": complete,
               "tests": len(assigned), "partitions": reports, "passed": passed}
    save_new(args.out / "summary.json", summary)
    print(json.dumps({"passed": passed, "tests": len(assigned),
                      "coverage_exact": complete,
                      "partitions": [{k: r[k] for k in ("partition", "run", "errors", "skips")}
                                     for r in reports]}, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
