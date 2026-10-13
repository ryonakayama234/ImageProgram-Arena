"""Paired boundary experiment: frozen v0 versus observation-only progress v1.

Task preparation/labels are management-private. Measurements receive only the
permitted crop, placement, broker frame and frozen configuration. Every state
comes from legal P1 Motor and is canonically executed/replayed after measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from adapters.imageprogram_reference.curve_progress_benchmark_v0 import (
    _bezier,
    _prefix,
    _project_arc,
)
from adapters.imageprogram_reference.curve_progress_benchmark_v0 import (
    _cases as _v0_cases,
)
from adapters.imageprogram_reference.public_reference_roi_v1 import (
    export_permitted_roi_v1,
)
from adapters.imageprogram_reference.source_artwork import ingest_local_source

FORMAT = "arena-curve-progress-boundary-v1"


def _cases(split: str) -> list[dict]:
    # Old reserved examples are now KNOWN regression, never fresh held-out.
    if split == "regression":
        return _v0_cases("development") + _v0_cases("reserved")
    if split == "development":
        families = {
            "bend_dev": [(20.5, 20.5), (25.5, 75.5), (55.5, 120.5), (104.5, 130.5)],
            "hair_dev": [(30.5, 15.5), (10.5, 70.5), (20.5, 110.5), (85.5, 142.5)],
        }
    else:
        # Explicit fresh families; fixed before any reserved run.
        families = {
            "bend_new": [(21.5, 24.5), (32.5, 88.5), (72.5, 123.5), (105.5, 136.5)],
            "hair_new": [(35.5, 19.5), (14.5, 57.5), (29.5, 122.5), (94.5, 138.5)],
            "s_new": [(23.5, 29.5), (96.5, 40.5), (30.5, 114.5), (101.5, 132.5)],
            "arc_new": [(24.5, 27.5), (26.5, 91.5), (79.5, 130.5), (107.5, 86.5)],
        }
    result = []
    conditions = (("normal", 1.0), ("normal", 2.0), ("normal", 3.0), ("coarse", 16))
    for family, control in families.items():
        for fraction in (0.4, 0.6, 0.8):
            for intervention, value in conditions:
                result.append(
                    dict(
                        id=f"{family}-{fraction}-{intervention}-{value}",
                        family=family,
                        points=_bezier(control),
                        fraction=fraction,
                        expected="measured",
                        kind="supported_boundary",
                        intervention=intervention,
                        value=value,
                    )
                )
    if split == "development":
        for displacement in (4.0, 6.0):
            result.append(
                dict(
                    id=f"large-offset-{displacement}",
                    family="large_offset",
                    points=_bezier(families["bend_dev"]),
                    fraction=0.6,
                    expected="diagnostic",
                    kind="boundary_diagnostic",
                    intervention="normal",
                    value=displacement,
                )
            )
        # Preserve existing negatives and near-self ordering probe.
        result.extend(
            c
            for c in _v0_cases("development")
            if c["kind"] in ("negative", "order_probe")
        )
    return result


def _intervene(prefix, case, scale):
    if len(prefix) < 2 or "intervention" not in case:
        return prefix
    if case["intervention"] == "coarse":
        stride = case["value"]
        result = prefix[::stride]
        if result[-1] != prefix[-1]:
            result.append(prefix[-1])
        return result
    # Offset normal to the prepared source tangent; first point pinned.
    points = np.asarray(prefix)
    tangent = np.gradient(points, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    normal = np.column_stack([-tangent[:, 1], tangent[:, 0]])
    arc = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    offset = case["value"] / scale * np.minimum(1.0, arc * scale / 15.0)
    return [tuple(map(float, p)) for p in points + normal * offset[:, None]]


def _validate_reserved_report(report, model_sha, arena_sha, fingerprints):
    config = report.get("configuration", {})
    payload = (json.dumps(config, indent=2, sort_keys=True) + "\n").encode()
    rows = report.get("results", [])
    expected_ids = {case["id"] for case in _cases("development")}
    expected_roles = {case["id"]: case["expected"] for case in _cases("development")}
    if (
        config.get("split") != "development"
        or config.get("model_sha") != model_sha
        or config.get("arena_sha") != arena_sha
        or config.get("source_fingerprints") != fingerprints
        or report.get("configuration_hash")
        != "sha256:" + hashlib.sha256(payload).hexdigest()
        or {row.get("id") for row in rows} != expected_ids
        or len(rows) != len(expected_ids)
        or any(r.get("expected") != expected_roles.get(r.get("id")) for r in rows)
        or not _acceptance(rows)
    ):
        raise ValueError(
            "reserved requires matching complete passing frozen development evidence"
        )


def _correct(row):
    error = row.get("source_arc_error_world_px")
    return (
        row.get("measurement", {}).get("status") == "measured"
        and not isinstance(error, bool)
        and isinstance(error, (int, float))
        and math.isfinite(error)
        and 0 <= error <= 2.0
    )


def _acceptance(rows):
    supported = [r for r in rows if r.get("expected") == "measured"]
    return bool(supported) and (
        sum(_correct(r) for r in supported) / len(supported) >= 0.9
        and all(r.get("source_replay_verified") is True for r in rows)
        and all(r.get("protected_ink_px") == 0 for r in rows)
        and all(r.get("measurement_motor_actions") == 0 for r in rows)
        and all(
            r["measurement"]["coverage"] == r["measurement"]["baseline"]["coverage"]
            for r in rows
        )
        and not any(
            r["measurement"]["status"] == "measured" and not _correct(r) for r in rows
        )
        and all(
            r["measurement"]["status"] == r["expected"]
            for r in rows
            if r["expected"] in ("blank", "unknown", "unsupported")
        )
    )


def run(output: Path, split: str, development_report: Path | None = None) -> dict:
    if split not in ("development", "reserved", "regression"):
        raise ValueError("unknown benchmark split")
    if split == "reserved" and development_report is None:
        raise ValueError(
            "reserved evaluation requires development report before creating output"
        )
    import imageprogram
    from imageprogram.construction.protection import preflight_trace_protection
    from imageprogram.contracts import (
        BodySpec,
        Budget,
        GoalSpec,
        MotorProgram,
        RunRequest,
        WaitAction,
    )
    from imageprogram.contracts_p2 import (
        ObservationRequest,
        TracePolylineArgs,
        TracePolylineCall,
    )
    from imageprogram.experiments.art1_feedback_session_v1 import (
        _compile_trace,
        _GuardedMotor,
        _protection_goal,
        dict_to_vec,
        load_v1_public_task,
    )
    from imageprogram.experiments.curve_progress_v1 import (
        CurveProgressConfigV1,
        measure_curve_progress_v1,
    )
    from imageprogram.experiments.reference_canvas_difference_v1 import (
        PermittedReferenceObservationV1,
    )
    from imageprogram.experiments.runner import execute, replay
    from imageprogram.eye.broker import ObservationBroker
    from imageprogram.world.engine import World

    model_root = Path(imageprogram.__file__).resolve().parents[2]
    arena_root = Path(__file__).resolve().parents[2]

    def sha(path):
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
        ).strip()

    for checkout in (model_root, arena_root):
        dirty = subprocess.check_output(
            ["git", "-C", str(checkout), "status", "--porcelain"],
            text=True,
        ).strip()
        if dirty:
            raise ValueError("official benchmark requires clean source checkouts")
    fingerprints = {
        "model_observer": hashlib.sha256(
            (
                model_root / "src/imageprogram/experiments/curve_progress_v1.py"
            ).read_bytes()
        ).hexdigest(),
        "arena_benchmark": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    model_sha, arena_sha = sha(model_root), sha(arena_root)
    if split == "reserved":
        _validate_reserved_report(
            json.loads(development_report.read_text()),
            model_sha,
            arena_sha,
            fingerprints,
        )

    config = CurveProgressConfigV1()
    cases = _cases(split)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        format=FORMAT,
        split=split,
        config=asdict(config),
        cases=cases,
        model_sha=model_sha,
        arena_sha=arena_sha,
        source_fingerprints=fingerprints,
        source_family_split="known_regression_vs_development_vs_four_fresh_families",
        labels_policy_visible=False,
        learned=False,
        human_accepted=False,
        acceptance="supported measured >=90%; all measured source arc errors <=2px; preserve frozen v0 coverage; no false confident measurements; candidate improvement over v0",
        note="Axial endpoint assumption is explicit. Large offsets are diagnostics. No learned Skill, repair or generalization claim. Reserved requires clean fixed code and same development evidence.",
    )
    raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    (output / "private_configuration.json").write_bytes(raw)
    rows = []
    for case in cases:
        root = output / case["id"]
        management = root / "management"
        management.mkdir(parents=True)
        source = management / "source.png"
        image = Image.new("RGB", (128, 160), "white")
        ImageDraw.Draw(image).line(
            [(round(x - 0.5), round(y - 0.5)) for x, y in case["points"]],
            fill="black",
            width=1,
        )
        image.save(source)
        intake = ingest_local_source(
            source,
            editable_bbox=(0, 0, 128, 160),
            source_family="generated-progress-" + case["family"],
            rights="generated-test-fixture",
        )
        record = management / "source_manifest.json"
        record.write_text(json.dumps(intake) + "\n")
        public = root / "public_roi"
        export_permitted_roi_v1(source, record, public)
        _, crop, placement = load_v1_public_task(public)
        reference = PermittedReferenceObservationV1.from_permitted_crop(
            crop, roi_id="art1.curve.progress", placement=placement
        )
        body = BodySpec()
        world = World(body, seed=17)
        budget = Budget(
            max_sim_time_s=70.0,
            max_wall_time_s=70.0,
            max_strokes=12,
            max_motor_commands=512,
            max_observations=513,
        )
        motor = _GuardedMotor(world, placement, budget)
        goal = _protection_goal(placement, body, world.observe().observation_id)
        prefix, truth_arc = _prefix(case["points"], case["fraction"])
        paths = [_intervene(prefix, case, placement.scale)] if prefix else []
        if case["id"] == "hole":
            paths = [[(20.5, 40.5), (40.5, 40.5)], [(50.5, 40.5), (75.5, 40.5)]]
        if case["id"] == "far_terminal_patch":
            paths = [[(85.5, 40.5), (99.5, 40.5)]]
        if case["id"] == "branch":
            paths = [[(20.5, 40.5), (75.5, 40.5)], [(45.5, 30.5), (45.5, 55.5)]]
        if "observed_paths" in case:
            paths = case["observed_paths"]
            truth_arc = case["truth_arc_local_px"]
        for i, path in enumerate(paths):
            call = TracePolylineCall(
                call_id=f"prepare.{i}",
                parent_decision_id="management.prepare",
                goal_version=goal.goal_version,
                args=TracePolylineArgs(
                    points_m=[
                        dict_to_vec(placement.local_to_canvas_m(x, y, body))
                        for x, y in path
                    ],
                    tool="pen",
                    pressure=0.5,
                    speed_m_s=0.05,
                ),
            )
            preflight_trace_protection([call], goal=goal, body=body).require_safe()
            pose = world.observe()
            actions = _compile_trace(
                call,
                body=body,
                tip=pose.tip_position_m,
                tool=pose.tool,
                contact=world.metadata()["contact"],
            )
            motor.apply(actions)
        if not paths:
            motor.apply([WaitAction(kind="wait", duration_s=0.01)])
        broker = ObservationBroker()
        frame = broker.acquire(
            world,
            ObservationRequest(request_id="progress.observe", reason="poststroke"),
            [],
        )
        before_hash = world.state_hash()
        started = time.monotonic()
        measured = measure_curve_progress_v1(
            reference, placement=placement, broker=broker, frame=frame, config=config
        )
        measurement_wall = time.monotonic() - started
        if world.state_hash() != before_hash:
            raise RuntimeError("measurement changed World")
        request = RunRequest(
            request_id="curve.progress",
            seed=17,
            body=body,
            budget=budget,
            goal=GoalSpec(
                prompt="Synthetic prefix observation task",
                desired_changes=["Measure progress only"],
                invariants=["No measurement-time Motor"],
                success_criteria=["Independent source geometry evaluation"],
            ),
        )
        episode = root / "episode"
        result = execute(
            request, MotorProgram(body=body, actions=motor.actions), episode
        )
        verified = replay(episode)
        if (
            result.status != "program_exhausted"
            or not verified.get("verified")
            or result.final_state_hash != before_hash
        ):
            raise RuntimeError("source execution/replay mismatch")
        with Image.open(episode / "final.png") as image:
            if not np.array_equal(
                np.array(image), broker.pixels_for_measurement(frame.frame_id)
            ):
                raise RuntimeError("measurement frame is not canonical terminal raster")
        protected = int(
            np.count_nonzero(
                (broker.pixels_for_measurement(frame.frame_id) < 250)
                & ~placement.editable_world_mask()
            )
        )
        truth_world = truth_arc * placement.scale
        canonical_world = [placement.local_to_world_px(x, y) for x, y in case["points"]]
        projected_arc = arc_error = None
        if measured.matched_reference_point_world_px is not None:
            projected_arc, _ = _project_arc(
                measured.matched_reference_point_world_px, canonical_world
            )
            arc_error = abs(projected_arc - truth_world)
        raw_arc_error = (
            abs(measured.arc_estimate_world_px - truth_world)
            if measured.arc_estimate_world_px is not None
            else None
        )
        nearest_error = (
            abs(measured.baseline.nearest_endpoint_arc_world_px - truth_world)
            if measured.baseline.nearest_endpoint_arc_world_px is not None
            else None
        )
        baseline = measured.baseline
        baseline_error = None
        if baseline.matched_reference_point_world_px is not None:
            baseline_arc, _ = _project_arc(
                baseline.matched_reference_point_world_px, canonical_world
            )
            baseline_error = abs(baseline_arc - truth_world)
        baseline_correct = (
            baseline.status == "measured"
            and baseline_error is not None
            and baseline_error <= 2.0
        )
        candidate_correct = (
            measured.status == "measured" and arc_error is not None and arc_error <= 2.0
        )
        expected = case["expected"]
        passed = (
            measured.status == expected or expected == "diagnostic"
        ) and protected == 0
        passed = passed and measured.coverage == baseline.coverage
        passed = passed and not (
            measured.status == "measured" and not candidate_correct
        )
        if expected == "measured":
            passed = passed and arc_error is not None and arc_error <= 2.0
            if split == "regression" and case["fraction"] == 1.0:
                passed = passed and measured.coverage == "covered_within_tolerance"
            elif split == "regression":
                passed = passed and measured.coverage == "partial"
        row = dict(
            id=case["id"],
            family=case["family"],
            kind=case["kind"],
            expected=expected,
            measurement=asdict(measured),
            truth_arc_world_px=truth_world,
            projected_source_arc_world_px=projected_arc,
            source_arc_error_world_px=arc_error,
            raw_inferred_arc_error_world_px=raw_arc_error,
            nearest_raw_arc_error_world_px=nearest_error,
            baseline_source_arc_error_world_px=baseline_error,
            baseline_correct=bool(baseline_correct),
            candidate_correct=bool(candidate_correct),
            source_replay_verified=True,
            protected_ink_px=protected,
            measurement_motor_actions=0,
            measurement_wall_time_s=measurement_wall,
            passed=bool(passed),
            actual_costs=result.costs.model_dump(),
            frame_is_canonical_final=True,
        )
        rows.append(row)
        (root / "measurement_and_private_evaluation.json").write_text(
            json.dumps(row, indent=2, sort_keys=True) + "\n"
        )
        with (output / "results.jsonl").open("a") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
        print(
            case["id"],
            measured.status,
            measured.reason,
            arc_error,
            "PASS" if passed else "FAIL",
            flush=True,
        )
    supported = [r for r in rows if r["expected"] == "measured"]
    report = dict(
        format=FORMAT,
        configuration_hash="sha256:" + hashlib.sha256(raw).hexdigest(),
        configuration=manifest,
        results=rows,
        total=len(rows),
        passed=sum(r["passed"] for r in rows),
        measured_supported=sum(
            r["measurement"]["status"] == "measured" for r in supported
        ),
        supported=len(supported),
        baseline_correct_supported=sum(r["baseline_correct"] for r in supported),
        candidate_correct_supported=sum(r["candidate_correct"] for r in supported),
        false_confident_measurements=sum(
            r["measurement"]["status"] == "measured" and not r["candidate_correct"]
            for r in rows
        ),
        coverage_verdict_changed=sum(
            r["measurement"]["coverage"] != r["measurement"]["baseline"]["coverage"]
            for r in rows
        ),
        acceptance_pass=_acceptance(rows),
        status="EXPERIMENT_RECORDED_NOT_PROMOTED",
        held_out_generalization=False,
        learned_skill=False,
        human_accepted=False,
    )
    (output / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--split",
        choices=("development", "reserved", "regression"),
        default="development",
    )
    parser.add_argument("--development-report", type=Path)
    args = parser.parse_args()
    report = run(args.out, args.split, args.development_report)
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("total", "passed", "measured_supported", "supported")
            }
        )
    )


if __name__ == "__main__":
    main()
