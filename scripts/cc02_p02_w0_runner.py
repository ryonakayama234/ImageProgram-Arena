"""W0: fail-closed paired-checkout validation and prediction/grading separation.

Research-only. Run in WSL2 from an unmodified ImageProgram-Arena checkout.
This runner never downloads dependencies, merges commits, or reads confirmation tasks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

LEGACY_SHA = "6d8e6399a2b0a44d08054a08b71b4a68d4d9e374"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
P02_MODULE = "adapters.imageprogram_reference.branch_contour_p02_trial"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_new(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def command(args: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(args, cwd=cwd, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode:
        raise RuntimeError(f"preflight-command-failed: {args[0]}: {proc.stderr.strip()[:350]}")
    return proc.stdout.strip()


def repo_head(root: Path) -> str:
    return command(["git", "rev-parse", "HEAD"], cwd=root)


def repo_clean(root: Path) -> bool:
    # Both tracked modifications and untracked files invalidate source identity.
    return not command(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root)


def preflight(model: Path, arena: Path, historical: Path, expected_model: str,
              expected_arena: str) -> dict:
    if not HEX40.fullmatch(expected_model) or not HEX40.fullmatch(expected_arena):
        raise ValueError("expected-checkout-head-must-be-full-40-character-sha")
    roots = {"model": model.resolve(), "arena": arena.resolve(),
             "historical_model": historical.resolve()}
    if len(set(roots.values())) != 3:
        raise ValueError("model-arena-historical-roots-must-be-distinct")
    heads = {name: repo_head(root) for name, root in roots.items()}
    if heads != {"model": expected_model, "arena": expected_arena,
                  "historical_model": LEGACY_SHA}:
        raise RuntimeError("checkout-head-mismatch: " + json.dumps(heads, sort_keys=True))
    if not all(repo_clean(p) for p in roots.values()):
        raise RuntimeError("dirty-checkout-rejected")
    required = {
        "model": ["uv.lock", "pyproject.toml", "scripts/check.py",
                  "src/imageprogram/models/branch_contour_p02.py"],
        "arena": ["scripts/cc02_test_matrix.py",
                  "adapters/imageprogram_reference/branch_contour_p02_trial.py",
                  "adapters/imageprogram_reference/branch_contour_p02_private.py"],
        "historical_model": ["uv.lock"],
    }
    for name, files in required.items():
        for file in files:
            if not (roots[name] / file).is_file():
                raise FileNotFoundError(f"required-tracked-source-not-found: {name}/{file}")
    model_python = model / ".venv/bin/python"
    historical_python = historical / ".venv/bin/python"
    for binary, cwd in [(model_python, model), (historical_python, historical)]:
        if not binary.is_file():
            raise FileNotFoundError(f"locked-venv-not-found: {binary}")
        ver = command([str(binary), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                      cwd=cwd)
        if ver != "3.12":
            raise RuntimeError(f"locked-interpreter-must-be-python-3.12: {binary}={ver}")
    return {"protocol": "cc02-p02-w0-v1", "model_head": heads["model"],
            "arena_head": heads["arena"], "historical_model_head": heads["historical_model"],
            "model_uv_lock_sha256": sha256_file(model / "uv.lock"),
            "historical_uv_lock_sha256": sha256_file(historical / "uv.lock"),
            "p02_model_source_sha256": sha256_file(
                model / "src/imageprogram/models/branch_contour_p02.py"),
            "p02_arena_trial_source_sha256": sha256_file(
                arena / "adapters/imageprogram_reference/branch_contour_p02_trial.py"),
            "original_confirmation": "NOT_RUN"}


def execute(label: str, argv: list[str], cwd: Path, destination: Path,
            *, env: dict[str, str] | None = None) -> dict:
    # Nonzero return codes are kept as evidence; nothing is silently retried.
    proc = subprocess.run(argv, cwd=cwd, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log = destination / (label + ".log")
    with log.open("x", encoding="utf-8") as stream:
        stream.write(proc.stdout or "")
    return {"name": label, "return_code": proc.returncode, "log_sha256": sha256_file(log),
            "passed": proc.returncode == 0}


def run_validation(model: Path, arena: Path, historical: Path, out: Path) -> list[dict]:
    python = str(model / ".venv/bin/python")
    ruff = str(model / ".venv/bin/ruff")
    if not Path(ruff).is_file():
        raise FileNotFoundError("model-ruff-not-installed")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(
        (str(arena), str(model / "src")))}
    return [
        execute("w0_runner_contract_tests", [python, "-m", "unittest", "discover",
                                               "-s", "scripts", "-p",
                                               "test_cc02_p02_w0_runner.py"],
                arena, out, env=env),
        execute("model_tests", [python, "scripts/check.py"], model, out),
        execute("model_ruff", [ruff, "check", "."], model, out),
        execute("arena_complete_matrix", [python, "scripts/cc02_test_matrix.py",
                                         "--legacy-model-root", str(historical),
                                         "--out", str(out / "arena-matrix")], arena, out,
                env=env),
        execute("arena_changed_files_ruff", [ruff, "check", "--config",
                                               str(model / "pyproject.toml"),
             "adapters/imageprogram_reference/branch_contour_p02_trial.py",
             "adapters/imageprogram_reference/branch_contour_p02_private.py",
             "tests/test_branch_contour_p02_trial.py"], arena, out),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--arena", required=True, type=Path)
    ap.add_argument("--historical-model", required=True, type=Path)
    ap.add_argument("--expected-model-head", required=True)
    ap.add_argument("--expected-arena-head", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--phase", choices=("validate", "predict", "grade"), required=True)
    ap.add_argument("--expected-receipt-sha256", help="Externally retained before GRADE")
    ap.add_argument("--receipt", type=Path)
    args = ap.parse_args()
    model, arena, historical = (p.resolve() for p in
                                (args.model, args.arena, args.historical_model))
    out = args.out.resolve()
    # Refuse to put experiment artifacts inside source checkout, even if excluded by Git.
    if any(out == p or p in out.parents for p in (model, arena, historical)):
        raise ValueError("output-must-be-outside-all-repositories")
    if args.phase == "grade":
        if args.receipt is None or not args.expected_receipt_sha256 or not HEX64.fullmatch(
                args.expected_receipt_sha256):
            raise ValueError("grade-requires-external-64hex-anchor-and-saved-receipt")
    else:
        if args.receipt is not None or args.expected_receipt_sha256 is not None:
            raise ValueError("receipt-arguments-only-for-grade")
    # Preflight before writing anything. The original fixture families are never imported here.
    identity = preflight(model, arena, historical,
                         args.expected_model_head, args.expected_arena_head)
    out.mkdir(parents=True, exist_ok=False)
    json_new(out / "checkout_identity.json", {**identity, "phase": args.phase})
    python = str(model / ".venv/bin/python")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(arena), str(model / "src")))}
    if args.phase == "validate":
        results = run_validation(model, arena, historical, out)
        ok = all(x["passed"] for x in results)
        json_new(out / "summary.json", {"phase": "validate", "passed": ok,
                                         "original_confirmation": "NOT_RUN",
                                         "commands": results})
        return 0 if ok else 1
    if args.phase == "predict":
        result = execute("predict", [python, "-m", P02_MODULE, "--predict",
                                     "--out", str(out / "prediction.json")], arena, out, env=env)
        log = (out / "predict.log").read_text(encoding="utf-8")
        anchor = re.search(r"^ANCHOR_BEFORE_GRADE_SHA256 ([0-9a-f]{64})$", log,
                           re.MULTILINE)
        success = result["passed"] and anchor is not None and (out / "prediction.json").is_file()
        json_new(out / "summary.json", {"phase": "predict", "passed": success,
                                         "external_anchor_required": True,
                                         "anchor_to_publish_before_grade":
                                         anchor.group(1) if anchor else None,
                                         "original_confirmation": "NOT_RUN",
                                         "commands": [result]})
        return 0 if success else 1
    # External actor must retain the prediction hash before this separate invocation.
    result = execute("grade", [python, "-m", P02_MODULE, "--grade", "--receipt",
                               str(args.receipt.resolve()), "--expected-sha256",
                               args.expected_receipt_sha256,
                               "--out", str(out / "grade.json")], arena, out, env=env)
    ok = result["passed"] and (out / "grade.json").is_file()
    json_new(out / "summary.json", {"phase": "grade", "passed": ok,
                                     "external_anchor_supplied": args.expected_receipt_sha256,
                                     "original_confirmation": "NOT_RUN", "commands": [result]})
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
