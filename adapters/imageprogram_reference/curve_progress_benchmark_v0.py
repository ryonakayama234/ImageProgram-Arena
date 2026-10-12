"""Independent synthetic observation benchmark for Model curve-progress v0.

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

from adapters.imageprogram_reference.public_reference_roi_v1 import (
    export_permitted_roi_v1,
)
from adapters.imageprogram_reference.source_artwork import ingest_local_source

FORMAT = "arena-curve-progress-benchmark-v0"


def _bezier(control: list[tuple[float, float]]) -> list[tuple[float, float]]:
    points = np.array(control, dtype=float)
    t = np.linspace(0, 1, 101)[:, None]
    xy = (
        (1 - t) ** 3 * points[0]
        + 3 * (1 - t) ** 2 * t * points[1]
        + 3 * (1 - t) * t**2 * points[2]
        + t**3 * points[3]
    )
    return [tuple(map(float, p)) for p in xy]


def _prefix(points: list[tuple[float, float]], fraction: float):
    if fraction == 0:
        return [], 0.0
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    total = sum(lengths)
    distance = fraction * total
    if fraction == 1:
        return points, distance
    remaining = distance
    partial = [points[0]]
    for a, b, length in zip(points, points[1:], lengths):
        if remaining >= length:
            partial.append(b)
            remaining -= length
        else:
            partial.append(
                tuple(a[k] + remaining / length * (b[k] - a[k]) for k in (0, 1))
            )
            break
    return partial, distance


def _cases(split: str) -> list[dict]:
    families = (
        {
            "arc": [(20.5, 20.5), (25.5, 75.5), (55.5, 120.5), (104.5, 130.5)],
            "s_curve": [(20.5, 20.5), (105.5, 30.5), (10.5, 125.5), (100.5, 140.5)],
            "hair_curve": [(30.5, 15.5), (10.5, 70.5), (20.5, 110.5), (85.5, 142.5)],
            "wide_bend": [(20.5, 30.5), (100.5, 30.5), (20.5, 125.5), (105.5, 125.5)],
        }
        if split == "development"
        else {
            "reserved_arc": [(18.5, 32.5), (28.5, 118.5), (87.5, 139.5), (110.5, 74.5)],
            "reserved_s": [(22.5, 22.5), (18.5, 126.5), (103.5, 27.5), (98.5, 137.5)],
        }
    )
    result = []
    fractions = (
        (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        if split == "development"
        else (0.0, 0.25, 0.45, 0.65, 0.85, 1.0)
    )
    for family, control in families.items():
        for fraction in fractions:
            result.append(
                dict(
                    id=f"{family}-{round(fraction * 100)}",
                    family=family,
                    points=_bezier(control),
                    fraction=fraction,
                    expected="blank" if fraction == 0 else "measured",
                    kind="curve",
                )
            )
    if split != "development":
        return result
    # Analytic open U curve, deliberately distinct from the Bezier families.
    u = (
        [(30.5, 20.5), (30.5, 100.5)]
        + [
            (65.5 + 35 * math.cos(t), 100.5 + 35 * math.sin(t))
            for t in np.linspace(math.pi, 0, 61)
        ][1:]
        + [(100.5, 20.5)]
    )
    for f in (0.2, 0.4, 0.6, 0.8, 1.0):
        result.append(
            dict(
                id=f"u_curve-{round(f * 100)}",
                family="u_curve",
                points=u,
                fraction=f,
                expected="measured",
                kind="curve",
            )
        )
    for axis in ("horizontal", "vertical"):
        for location in (40.5, 85.5):
            pts = (
                [(20.5, location), (99.5, location)]
                if axis == "horizontal"
                else [(location, 20.5), (location, 130.5)]
            )
            for f in (0.35, 0.45, 0.55, 0.65, 1.0):
                result.append(
                    dict(
                        id=f"{axis}-{location}-{round(f * 100)}",
                        family=f"{axis}-{location}",
                        points=pts,
                        fraction=f,
                        expected="measured",
                        kind="straight_regression",
                    )
                )
    for negative in ("hole", "far_terminal_patch", "branch", "closed_reference"):
        pts = [(20.5, 40.5), (99.5, 40.5)]
        if negative == "closed_reference":
            pts = [
                (20.5, 40.5),
                (80.5, 40.5),
                (80.5, 100.5),
                (20.5, 100.5),
                (20.5, 40.5),
            ]
        result.append(
            dict(
                id=negative,
                family=negative,
                points=pts,
                fraction=0.6,
                expected="unsupported" if negative == "closed_reference" else "unknown",
                kind="negative",
            )
        )
    # Real World near-self path: nearest endpoint can jump to the late parallel
    # segment; ordered matching must explain the entire observed prefix.
    result.append(
        dict(
            id="near_self_order_probe",
            family="near_self",
            fraction=0.0,
            kind="order_probe",
            points=[
                (20.5, 40.5),
                (65.5, 40.5),
                (65.5, 80.5),
                (20.5, 80.5),
                (20.5, 42.5),
                (55.5, 42.5),
            ],
            observed_paths=[[(20.5, 40.5), (50.5, 41.6)]],
            truth_arc_local_px=30.0,
            expected="measured",
        )
    )
    return result


def _project_arc(point, points):
    """Arena label projection on private source geometry, independent of Model DP."""
    best, best_arc, offset = math.inf, None, 0.0
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        t = max(
            0.0,
            min(
                1.0,
                ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (length * length),
            ),
        )
        distance = math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)
        if distance < best:
            best, best_arc = distance, offset + t * length
        offset += length
    return best_arc, best


def _validate_reserved_report(
    report: dict, model_sha: str, arena_sha: str, fingerprints: dict
):
    config = report.get("configuration", {})
    rows = report.get("results", [])
    payload = (json.dumps(config, indent=2, sort_keys=True) + "\n").encode()
    expected_ids = {case["id"] for case in _cases("development")}
    if (
        config.get("split") != "development"
        or config.get("model_sha") != model_sha
        or config.get("arena_sha") != arena_sha
        or config.get("source_fingerprints") != fingerprints
        or report.get("configuration_hash")
        != "sha256:" + hashlib.sha256(payload).hexdigest()
        or report.get("total") != len(expected_ids)
        or report.get("passed") != len(expected_ids)
        or len(rows) != len(expected_ids)
        or {row.get("id") for row in rows} != expected_ids
        or not all(
            row.get("passed") is True and row.get("source_replay_verified") is True
            for row in rows
        )
    ):
        raise ValueError(
            "reserved evaluation requires complete matching frozen development evidence"
        )


def run(output: Path, split: str, development_report: Path | None = None) -> dict:
    if split not in ("development", "reserved"):
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
    from imageprogram.experiments.curve_progress_v0 import (
        CurveProgressConfigV0,
        measure_curve_progress_v0,
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
                model_root / "src/imageprogram/experiments/curve_progress_v0.py"
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

    config = CurveProgressConfigV0()
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
        source_family_split="development_vs_reserved_new_controls",
        labels_policy_visible=False,
        learned=False,
        human_accepted=False,
        acceptance="measured >=90% and private-source arc error <=2px on all measured supported cases; no false complete negatives",
        note="Development includes negative and legacy diagnostics. Reserved source families must not be run before code/config freeze.",
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
        paths = [prefix] if prefix else []
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
        measured = measure_curve_progress_v0(
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
            abs(measured.nearest_endpoint_arc_world_px - truth_world)
            if measured.nearest_endpoint_arc_world_px is not None
            else None
        )
        expected = case["expected"]
        passed = measured.status == expected and protected == 0
        if expected == "measured":
            passed = passed and arc_error is not None and arc_error <= 2.0
            if case["fraction"] == 1.0:
                passed = passed and measured.coverage == "covered_within_tolerance"
            else:
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
        "--split", choices=("development", "reserved"), default="development"
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
