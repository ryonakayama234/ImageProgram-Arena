"""Run each Arena test exactly once with its declared Model dependency.

The four legacy E1 tests retain their real PR81 checkout; all other tests use
current Model. No SHA monkeypatch, skip, exclusion from discovery or paid CI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

HISTORICAL_MODULES = {"test_e1_paired_synthetic_v1", "test_e1_review_v1"}
PR81_SHA = "6d8e6399a2b0a44d08054a08b71b4a68d4d9e374"
WORKER = r'''
import json,sys,unittest
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "tests"))
ids=json.load(sys.stdin)
class Result(unittest.TextTestResult):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw); self.executed=[]
    def startTest(self,test):
        self.executed.append(test.id()); super().startTest(test)
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(i) for i in ids)
r=unittest.TextTestRunner(verbosity=1,resultclass=Result).run(suite)
Path(sys.argv[1]).write_text(json.dumps({"executed":r.executed,"tests_run":r.testsRun,
 "success":r.wasSuccessful(),"skips":[(t.id(),why) for t,why in r.skipped],
 "failures":[(t.id(),tb) for t,tb in r.failures],"errors":[(t.id(),tb) for t,tb in r.errors]},indent=2)+"\n")
raise SystemExit(0 if r.wasSuccessful() and not r.skipped else 1)
'''


def flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test.id()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--historical-model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    arena = Path(__file__).resolve().parents[1]
    model, historical, out = args.model.resolve(), args.historical_model.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    historical_sha = subprocess.check_output(
        ["git", "-C", str(historical), "rev-parse", "HEAD"], text=True).strip()
    if historical_sha != PR81_SHA:
        raise ValueError("historical-model-must-be-real-pr81-checkout")
    sys.path.insert(0, str(arena))
    sys.path.insert(0, str(model / "src"))
    inventory = list(flatten(unittest.defaultTestLoader.discover(str(arena / "tests"))))
    if len(inventory) != len(set(inventory)) or any("_FailedTest" in i for i in inventory):
        raise RuntimeError("invalid-test-discovery")
    legacy = [i for i in inventory if i.split(".")[0] in HISTORICAL_MODULES]
    if len(legacy) != 4:
        raise RuntimeError("historical-test-contract-changed")
    current = [i for i in inventory if i not in legacy]
    reports = {}
    for name, root, ids in (("current", model, current), ("historical_pr81", historical, legacy)):
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(arena), str(root / "src"))))
        path = out / (name + ".json")
        with (out / (name + ".log")).open("x") as log:
            process = subprocess.run([str(root / ".venv/bin/python"), "-c", WORKER, str(path)],
                                     cwd=arena, env=env, input=json.dumps(ids), text=True,
                                     stdout=log, stderr=subprocess.STDOUT)
        report = json.loads(path.read_text())
        report["process_returncode"] = process.returncode
        if report["executed"] != ids:
            raise RuntimeError("test-execution-coverage-mismatch")
        reports[name] = report
    executed = [i for report in reports.values() for i in report["executed"]]
    complete = sorted(executed) == sorted(inventory) and len(executed) == len(set(executed))
    passed = complete and all(r["success"] and not r["skips"] and r["process_returncode"] == 0
                              for r in reports.values())
    summary = {"discovered": len(inventory), "current": len(current), "historical_pr81": len(legacy),
               "exact_id_coverage": complete, "zero_skips": all(not r["skips"] for r in reports.values()),
               "inventory_sha256": hashlib.sha256(json.dumps(sorted(inventory)).encode()).hexdigest(),
               "passed": passed, "reports": reports}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print({k: v for k, v in summary.items() if k != "reports"})
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
