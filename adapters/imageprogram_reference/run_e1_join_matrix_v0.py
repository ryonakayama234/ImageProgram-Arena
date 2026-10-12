"""Development-only real P1 endpoint-join matrix with separate producer environments.

The frozen baseline and candidate are launched and replayed with their own Python
interpreters. Only permitted ROI bytes enter their policies. This orchestrator
owns posthoc labels and never feeds its independent diagnostics back to producers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from adapters.imageprogram_reference.continuity_v0 import diagnose_continuity_v0
from adapters.imageprogram_reference.public_reference_roi_v1 import (
    export_permitted_roi_v1,
)
from adapters.imageprogram_reference.reference_target_v1 import target_and_masks_v1
from adapters.imageprogram_reference.source_artwork import ingest_local_source

BASELINE_SHA = "6d8e6399a2b0a44d08054a08b71b4a68d4d9e374"
CANDIDATE_SHA = "ceb9c55f647d81cb5a14fa6934f2d45b09741d0c"
FORMAT = "arena-e1-join-development-matrix-v0"
MODES = ("noop", "feedback_off", "feedback_on")


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _checked_model(root: Path, expected: str) -> Path:
    if _git(root, "rev-parse", "HEAD") != expected or _git(
        root, "status", "--porcelain"
    ):
        raise ValueError("producer must be clean at its exact frozen commit")
    python = root / ".venv/bin/python"
    if not python.is_file():
        raise ValueError("producer requires its own locked render environment")
    return python


def _cases() -> list[dict]:
    result = []
    for axis in ("horizontal", "vertical"):
        for location in (40, 85):
            for fraction in (0.35, 0.45, 0.55, 0.65):
                result.append(
                    {
                        "id": f"{axis}-{location}-f{round(fraction * 100)}",
                        "shape": axis,
                        "location": location,
                        "fraction": fraction,
                        "expectation": "execute",
                        "role": "development",
                        "family": f"{axis}-{location}",
                    }
                )
            result.append(
                {
                    "id": f"{axis}-{location}-complete",
                    "shape": axis,
                    "location": location,
                    "fraction": 1.0,
                    "expectation": "complete_stop",
                    "role": "negative_control",
                    "family": f"{axis}-{location}",
                }
            )
    for shape in ("horizontal", "vertical"):
        result.append(
            {
                "id": f"{shape}-near-boundary",
                "shape": shape,
                "location": 1,
                "fraction": 0.55,
                "expectation": "execute",
                "role": "boundary_probe",
                "family": shape + "-edge",
            }
        )
    for shape in ("diagonal", "curve"):
        result.append(
            {
                "id": shape + "-unsupported",
                "shape": shape,
                "location": 0,
                "fraction": 0.55,
                "expectation": "unsupported_stop",
                "role": "negative_control",
                "family": shape,
            }
        )
    for shape in ("crossing", "touch_boundary"):
        result.append(
            {
                "id": shape + "-reject",
                "shape": shape,
                "location": 0,
                "fraction": 0.55,
                "expectation": "input_reject",
                "role": "negative_control",
                "family": shape,
            }
        )
    return result


def _draw_case(case: dict, path: Path) -> None:
    image = Image.new("RGB", (128, 160), "white")
    draw = ImageDraw.Draw(image)
    location = case["location"]
    paths = {
        "horizontal": [(20, location), (99, location)],
        "vertical": [(location, 20), (location, 130)],
        "diagonal": [(20, 20), (99, 130)],
        "curve": [(20, 30), (24, 50), (35, 70), (50, 85), (70, 94), (99, 98)],
        "touch_boundary": [(0, 70), (99, 70)],
        "crossing": [(20, 70), (99, 70)],
    }
    draw.line(paths[case["shape"]], fill="black", width=1)
    if case["shape"] == "crossing":
        draw.line([(60, 30), (60, 120)], fill="black", width=1)
    image.save(path, format="PNG")


def _command(args: list[str], cwd: Path, log: Path) -> int:
    with log.open("x") as stream:
        return subprocess.run(
            args,
            cwd=cwd,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=300,
            check=False,
        ).returncode


def run_matrix(output: Path, baseline: Path, candidate: Path) -> dict:
    arena = Path(__file__).resolve().parents[2]
    baseline, candidate, output = (
        baseline.resolve(),
        candidate.resolve(),
        output.resolve(),
    )
    producers = {
        "baseline": (baseline, _checked_model(baseline, BASELINE_SHA)),
        "endpoint_join_v0": (candidate, _checked_model(candidate, CANDIDATE_SHA)),
    }
    if _git(arena, "status", "--porcelain"):
        raise ValueError("evaluator checkout must be clean")
    output.mkdir(parents=True, exist_ok=False)
    configuration = {
        "format": FORMAT,
        "seed": 17,
        "cases": _cases(),
        "baseline_sha": BASELINE_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "arena_sha": _git(arena, "rev-parse", "HEAD"),
        "independent_test": False,
        "learned_eye": False,
        "learned_skill": False,
        "human_accepted": False,
        "intervention": "actual_world_prefix_fraction_not_handmade_pixel_gap",
        "acceptance": "positive: candidate execute, strict connection, F1 >= baseline; complete: zero correction; unsupported: typed stop; malformed: explicit geometry reject",
    }
    config_bytes = (json.dumps(configuration, indent=2, sort_keys=True) + "\n").encode()
    (output / "configuration.json").write_bytes(config_bytes)
    configuration_hash = "sha256:" + hashlib.sha256(config_bytes).hexdigest()
    rows = []
    for case in configuration["cases"]:
        root = output / case["id"]
        management = root / "management"
        management.mkdir(parents=True)
        source = management / "source.png"
        _draw_case(case, source)
        manifest = ingest_local_source(
            source,
            editable_bbox=(0, 0, 128, 160),
            source_family="generated-join-" + case["family"],
            rights="generated-test-fixture",
        )
        record = management / "source_manifest.json"
        record.write_text(json.dumps(manifest, indent=2) + "\n")
        public = root / "public_roi"
        export_permitted_roi_v1(source, record, public)
        task = json.loads((public / "task.json").read_text())
        crop = (public / "reference_roi.png").read_bytes()
        target, editable, _ = target_and_masks_v1(task, crop)
        row = {"case": case, "strategies": {}, "errors": []}
        summaries = {}
        for strategy, (model, python) in producers.items():
            strategy_root = root / strategy
            strategy_root.mkdir()
            sessions = strategy_root / "sessions"
            args = [
                str(python),
                "scripts/art1_feedback_session_v1.py",
                "--public-roi",
                str(public),
                "--out",
                str(sessions),
                "--seed",
                "17",
                "--initial-fraction",
                str(case["fraction"]),
            ]
            if strategy != "baseline":
                args += ["--repair-strategy", strategy]
            try:
                code = _command(args, model, strategy_root / "producer.log")
                if code:
                    text = (strategy_root / "producer.log").read_text()
                    expected = (
                        case["expectation"] == "input_reject"
                        and "ReferenceGeometryUnsupported:" in text
                        and (
                            "branch/junction/cycle" in text
                            or "selected line touches ROI boundary" in text
                        )
                    )
                    row["strategies"][strategy] = {
                        "input_rejected": True,
                        "expected_geometry_rejection": expected,
                    }
                    if not expected:
                        row["errors"].append(strategy + ": producer failure")
                    continue
                summaries[strategy] = json.loads(
                    (sessions / "summary.json").read_text()
                )
                score_path = strategy_root / "independent_score.json"
                code = _command(
                    [
                        str(python),
                        "-m",
                        "adapters.imageprogram_reference.score_feedback_e1_v1",
                        "--public-roi",
                        str(public),
                        "--sessions",
                        str(sessions),
                        "--out",
                        str(score_path),
                    ],
                    arena,
                    strategy_root / "scorer.log",
                )
                if code:
                    row["errors"].append(
                        strategy + ": independent score/replay failure"
                    )
                    continue
                scored = json.loads(score_path.read_text())
                on = summaries[strategy]["episodes"]["feedback_on"]
                receipt = on["decision_receipt"]
                split = on["first_action_count"]
                with Image.open(
                    sessions / "feedback_on_episode" / "frames" / f"{split:06d}.png"
                ) as image:
                    before = np.array(image)
                with Image.open(
                    sessions / "feedback_on_episode" / "final.png"
                ) as image:
                    after = np.array(image)
                continuity = diagnose_continuity_v0(
                    target_mask=target,
                    editable_mask=editable,
                    poststroke_world_l8=before,
                    terminal_world_l8=after,
                )
                row["strategies"][strategy] = {
                    "decision": receipt["decision"],
                    "correction_motor": receipt["actual_correction_action_count"],
                    "continuity": continuity,
                    "f1": scored["scores"]["feedback_on"]["f1_2px"],
                    "all_arms_replay": scored["replay_verified_arms"],
                    "all_arms_protected_zero": all(
                        scored["scores"][m]["drawn_ink_outside_editable_px"] == 0
                        for m in MODES
                    ),
                    "noop_blank": scored["scores"]["noop"]["drawn_ink_px"] == 0,
                    "costs": {
                        m: {
                            k: scored["scores"][m][k]
                            for k in (
                                "motor_commands",
                                "strokes",
                                "sim_time_s",
                                "wall_time_s",
                                "eye_sensor_acquisitions",
                                "eye_query_evaluations",
                            )
                        }
                        for m in MODES
                    },
                }
            except (OSError, ValueError, subprocess.TimeoutExpired, KeyError) as exc:
                row["errors"].append(strategy + ": " + str(exc))
        if len(summaries) == 2:
            initial = [s["episodes"]["feedback_off"] for s in summaries.values()]
            row["initial_pair_matches"] = all(
                initial[0][k] == initial[1][k]
                for k in (
                    "initial_action_sha256",
                    "post_initial_state_hash",
                    "first_action_count",
                )
            )
        elif case["expectation"] != "input_reject":
            row["initial_pair_matches"] = False
        candidate_result = row["strategies"].get("endpoint_join_v0", {})
        base = row["strategies"].get("baseline", {})
        common = not row["errors"] and len(row["strategies"]) == 2
        if case["expectation"] == "input_reject":
            passed = common and all(
                r.get("expected_geometry_rejection") for r in row["strategies"].values()
            )
        else:
            common = (
                common
                and row.get("initial_pair_matches", False)
                and all(
                    set(r.get("all_arms_replay", [])) == set(MODES)
                    and r.get("all_arms_protected_zero")
                    and r.get("noop_blank")
                    for r in row["strategies"].values()
                )
            )
            decision = candidate_result.get("decision", {})
            if case["expectation"] == "execute":
                passed = (
                    common
                    and decision.get("kind") == "execute"
                    and candidate_result["continuity"]["strict_connected"]
                    and candidate_result["f1"] >= base["f1"] - 1e-12
                )
            elif case["expectation"] == "complete_stop":
                passed = (
                    common
                    and decision.get("kind") == "stop"
                    and candidate_result.get("correction_motor") == 0
                    and decision.get("reason") == "reference-already-covered"
                )
            else:
                passed = (
                    common
                    and decision.get("kind") == "stop"
                    and candidate_result.get("correction_motor") == 0
                    and "unsupported" in decision.get("reason", "")
                )
        row["development_check"] = "PASS" if passed else "FAIL"
        rows.append(row)
        with (output / "results.jsonl").open("a") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
        print(case["id"], row["development_check"], flush=True)
    report = {
        "configuration_hash": configuration_hash,
        "configuration": configuration,
        "results": rows,
        "passed": sum(r["development_check"] == "PASS" for r in rows),
        "total": len(rows),
        "status": "DEVELOPMENT_CHECKS_PASS"
        if all(r["development_check"] == "PASS" for r in rows)
        else "DEVELOPMENT_FAILURES_RETAINED",
        "human_accepted": False,
        "learned_skill": False,
        "held_out_generalization": False,
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    report = run_matrix(args.out, args.baseline, args.candidate)
    print(json.dumps({k: report[k] for k in ("status", "passed", "total")}))


if __name__ == "__main__":
    main()
