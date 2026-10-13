"""Legal World fixed-candidate line-integrity experiment, with independent scoring.

Policy choices are made on a blank authenticated Canvas BEFORE any candidate
is executed. Private source paths, case labels and outcomes stay in Arena.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from adapters.imageprogram_reference.curve_progress_benchmark_v0 import _bezier
from adapters.imageprogram_reference.line_integrity_v0 import (
    IntegrityThresholdsV0,
    evaluate_line_integrity_v0,
)
from adapters.imageprogram_reference.public_reference_roi_v1 import (
    export_permitted_roi_v1,
)
from adapters.imageprogram_reference.reference_target_v1 import score_terminal_v1
from adapters.imageprogram_reference.source_artwork import ingest_local_source

FORMAT = "arena-line-integrity-benchmark-v0"


def _cases(split):
    if split == "development":
        families = {
            "arc": [(20.5, 20.5), (25.5, 75.5), (55.5, 120.5), (104.5, 130.5)],
            "hair": [(30.5, 15.5), (10.5, 70.5), (20.5, 110.5), (85.5, 142.5)],
            "bend": [(20.5, 30.5), (100.5, 30.5), (20.5, 125.5), (105.5, 125.5)],
            "s": [(20.5, 20.5), (105.5, 30.5), (10.5, 125.5), (100.5, 140.5)],
        }
        pairs = [(f, i) for f in families for i in range(5)]
    elif split == "reserved":
        families = {
            "fresh_a": [(18.5, 28.5), (31.5, 80.5), (60.5, 112.5), (110.5, 139.5)],
            "fresh_b": [(32.5, 18.5), (19.5, 59.5), (30.5, 107.5), (91.5, 138.5)],
            "fresh_c": [(22.5, 25.5), (90.5, 34.5), (29.5, 111.5), (105.5, 134.5)],
            "fresh_d": [(25.5, 32.5), (30.5, 104.5), (79.5, 130.5), (109.5, 90.5)],
            "fresh_e": [(23.5, 19.5), (69.5, 49.5), (45.5, 101.5), (102.5, 141.5)],
        }
        pairs = [(f, (2 * j + k) % 5) for j, f in enumerate(families) for k in (0, 1)]
    else:
        raise ValueError("unknown line-integrity split")
    kinds = ("kink", "jitter", "thick", "parallel", "gap")
    return [
        dict(
            id=f"{f}-{kinds[i]}",
            family=f,
            damage=kinds[i],
            good_mode=i % 3,
            source_points=_bezier(families[f]),
        )
        for f, i in pairs
    ]


def _make_paths(public_reference_path, damage, good_mode):
    # All candidate geometry is derived from the POLICY-PERMITTED path, not the
    # analytic source used by the private evaluator.
    points = np.asarray(public_reference_path)
    arc = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    s = np.linspace(0.0, arc[-1], int(np.ceil(arc[-1])) + 1)
    sampled = np.column_stack([np.interp(s, arc, points[:, k]) for k in (0, 1)])
    smooth = np.column_stack(
        [
            np.convolve(np.pad(sampled[:, k], 3, mode="edge"), np.ones(7) / 7, "valid")
            for k in (0, 1)
        ]
    )
    smooth[0], smooth[-1] = sampled[0], sampled[-1]
    tangent = np.gradient(smooth, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    normal = np.column_stack([-tangent[:, 1], tangent[:, 0]])
    taper = np.minimum(1.0, np.minimum(s, arc[-1] - s) / 8.0)
    clean = smooth + normal * (0.8 * taper)[:, None]
    middle = len(s) // 2
    good = [clean]
    if good_mode == 1:
        good = [clean[: middle + 2], clean[middle:]]
    elif good_mode == 2:
        good = [clean, clean.copy()]
    bad = [smooth.copy()]
    x = s - s[middle]
    if damage == "kink":
        offset = 2.2 * np.maximum(0.0, 1.0 - np.abs(x) / 8.0)
        bad = [smooth + normal * offset[:, None]]
    elif damage == "jitter":
        offset = 1.7 * np.sin(x * np.pi / 3.0) * np.maximum(0.0, 1.0 - np.abs(x) / 16.0)
        bad = [smooth + normal * offset[:, None]]
    elif damage == "thick":
        region = np.flatnonzero(np.abs(x) < 10.0)
        bad += [(smooth + normal * v)[region] for v in (-0.8, 0.8)]
    elif damage == "parallel":
        region = np.flatnonzero(np.abs(x) < 15.0)
        bad += [(smooth + normal * 2.3)[region]]
    elif damage == "gap":
        left = int(np.searchsorted(s, s[middle] - 3.0))
        right = int(np.searchsorted(s, s[middle] + 3.0))
        bad = [smooth[: left + 1], smooth[right:]]
    return good, bad


def _row_gate(row):
    arms = row["arms"]
    good, bad = arms[row["good_id"]], arms[row["bad_id"]]
    return (
        good["integrity"]["line_integrity_pass"]
        and good["shape"]["f1_2px"] >= 0.95
        and not bad["integrity"]["line_integrity_pass"]
        and row["quality_choice"]["selected_candidate_id"] == row["good_id"]
        and row["quality_selected_actual_pass"]
        and all(
            a["source_replay_verified"] and a["protected_ink_px"] == 0
            for a in arms.values()
        )
        and row["decisions_before_execution"]
        and row["no_measurement_motor"]
    )


def _check_development(report, model_sha, arena_sha, fingerprints):
    config = report.get("configuration", {})
    rows = report.get("results", [])
    payload = (json.dumps(config, indent=2, sort_keys=True) + "\n").encode()
    cases = _cases("development")
    ids = {c["id"] for c in cases}
    if (
        config.get("split") != "development"
        or config.get("model_sha") != model_sha
        or config.get("arena_sha") != arena_sha
        or config.get("source_fingerprints") != fingerprints
        or report.get("configuration_hash")
        != "sha256:" + hashlib.sha256(payload).hexdigest()
        or len(rows) != len(ids)
        or {r.get("id") for r in rows} != ids
        or not all(_row_gate(r) for r in rows)
    ):
        raise ValueError(
            "reserved requires passing complete frozen development evidence"
        )


def run(output, split, development_report=None, pilot=False):
    if split not in ("development", "reserved"):
        raise ValueError("unknown split")
    if split == "reserved" and (pilot or development_report is None):
        raise ValueError("reserved requires non-pilot development report")
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
    from imageprogram.experiments.line_integrity_choice_v0 import (
        PublicLineCandidateV0,
        choose_line_candidate_v0,
        public_reference_path_v0,
    )
    from imageprogram.experiments.reference_canvas_difference_v1 import (
        PermittedReferenceObservationV1,
    )
    from imageprogram.experiments.runner import execute, replay
    from imageprogram.eye.broker import ObservationBroker
    from imageprogram.world.engine import World

    model_root = Path(imageprogram.__file__).resolve().parents[2]
    arena_root = Path(__file__).resolve().parents[2]

    def sha(p):
        return subprocess.check_output(
            ["git", "-C", str(p), "rev-parse", "HEAD"], text=True
        ).strip()

    model_sha, arena_sha = sha(model_root), sha(arena_root)
    if not pilot:
        for checkout in (model_root, arena_root):
            if subprocess.check_output(
                ["git", "-C", str(checkout), "status", "--porcelain"], text=True
            ).strip():
                raise ValueError("official benchmark requires clean sources")
    fingerprints = {
        "model_choice": hashlib.sha256(
            (
                model_root / "src/imageprogram/experiments/line_integrity_choice_v0.py"
            ).read_bytes()
        ).hexdigest(),
        "arena_evaluator": hashlib.sha256(
            Path(__file__).with_name("line_integrity_v0.py").read_bytes()
        ).hexdigest(),
        "arena_benchmark": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    if split == "reserved":
        _check_development(
            json.loads(development_report.read_text()),
            model_sha,
            arena_sha,
            fingerprints,
        )
    thresholds = IntegrityThresholdsV0()
    cases = _cases(split)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    config = dict(
        format=FORMAT,
        split=split,
        pilot=pilot,
        cases=cases,
        model_sha=model_sha,
        arena_sha=arena_sha,
        source_fingerprints=fingerprints,
        thresholds=asdict(thresholds),
        labels_policy_visible=False,
        selection_scope="blank-canvas-fixed-public-candidates",
        learned=False,
        human_accepted=False,
        acceptance="all unambiguous damaged arms rejected; >=90% good choices; actual quality+F1>=.95; replay and protection",
    )
    raw = (json.dumps(config, indent=2, sort_keys=True) + "\n").encode()
    (output / "private_configuration.json").write_bytes(raw)
    rows = []
    for case in cases:
        root = output / case["id"]
        management = root / "management"
        management.mkdir(parents=True)
        source = management / "source.png"
        image = Image.new("RGB", (128, 160), "white")
        ImageDraw.Draw(image).line(
            [(round(x - 0.5), round(y - 0.5)) for x, y in case["source_points"]],
            fill="black",
            width=1,
        )
        image.save(source)
        intake = ingest_local_source(
            source,
            editable_bbox=(0, 0, 128, 160),
            source_family="line-integrity-" + case["family"],
            rights="generated-test-fixture",
        )
        record = management / "source_manifest.json"
        record.write_text(json.dumps(intake) + "\n")
        public = root / "public_roi"
        export_permitted_roi_v1(source, record, public)
        task, crop, placement = load_v1_public_task(public)
        reference = PermittedReferenceObservationV1.from_permitted_crop(
            crop, roi_id="art1.line.integrity", placement=placement
        )
        permitted_path = public_reference_path_v0(reference, placement)
        good, bad = _make_paths(permitted_path, case["damage"], case["good_mode"])

        def candidate(paths, label):
            identity = (
                "candidate-"
                + hashlib.sha256((case["id"] + "|" + label).encode()).hexdigest()[:12]
            )
            return PublicLineCandidateV0(
                identity,
                tuple(tuple(tuple(map(float, p)) for p in path) for path in paths),
            )

        good_candidate, bad_candidate = candidate(good, "one"), candidate(bad, "two")
        noop = candidate([], "three")
        candidates = tuple(
            sorted([good_candidate, bad_candidate, noop], key=lambda c: c.candidate_id)
        )
        body = BodySpec()
        world = World(body, seed=17)
        broker = ObservationBroker()
        frame = broker.acquire(
            world, ObservationRequest(request_id="choose.observe", reason="initial"), []
        )
        before = world.state_hash()
        decision_start = time.monotonic()
        baseline_choice = choose_line_candidate_v0(
            reference,
            placement=placement,
            broker=broker,
            frame=frame,
            candidates=candidates,
            quality_gate=False,
        )
        quality_choice = choose_line_candidate_v0(
            reference,
            placement=placement,
            broker=broker,
            frame=frame,
            candidates=candidates,
            quality_gate=True,
        )
        decision_wall = time.monotonic() - decision_start
        assert world.state_hash() == before
        decision = dict(
            baseline_choice=baseline_choice,
            quality_choice=quality_choice,
            public_candidates=[asdict(c) for c in candidates],
            canvas_hash=frame.image_sha256,
            choice_before_any_execution=True,
        )
        (root / "public_decision.json").write_text(
            json.dumps(decision, indent=2) + "\n"
        )
        arms = {}
        for cand in candidates:
            body = BodySpec()
            world = World(body, seed=17)
            budget = Budget(
                max_sim_time_s=70.0,
                max_wall_time_s=70.0,
                max_strokes=12,
                max_motor_commands=2048,
                max_observations=2049,
            )
            motor = _GuardedMotor(world, placement, budget)
            goal = _protection_goal(placement, body, world.observe().observation_id)
            for i, path in enumerate(cand.paths_world_px):
                points_m = [dict_to_vec((x * 0.001, y * 0.001)) for x, y in path]
                call = TracePolylineCall(
                    call_id=f"candidate.{i}",
                    parent_decision_id="public.choice",
                    goal_version=goal.goal_version,
                    args=TracePolylineArgs(
                        points_m=points_m, tool="pen", pressure=0.5, speed_m_s=0.05
                    ),
                )
                preflight_trace_protection([call], goal=goal, body=body).require_safe()
                pose = world.observe()
                motor.apply(
                    _compile_trace(
                        call,
                        body=body,
                        tip=pose.tip_position_m,
                        tool=pose.tool,
                        contact=world.metadata()["contact"],
                    )
                )
            if not cand.paths_world_px:
                motor.apply([WaitAction(kind="wait", duration_s=0.01)])
            final = world.pixels()
            before_measurement = world.state_hash()
            analytic = [placement.local_to_world_px(*p) for p in case["source_points"]]
            integrity = evaluate_line_integrity_v0(
                final,
                source_path_world_px=analytic,
                editable_mask=placement.editable_world_mask(),
                thresholds=thresholds,
            )
            shape = score_terminal_v1(
                task, (public / "reference_roi.png").read_bytes(), final
            )
            assert world.state_hash() == before_measurement
            request = RunRequest(
                request_id="line.integrity",
                seed=17,
                body=body,
                budget=budget,
                goal=GoalSpec(
                    prompt="One thin smooth contour",
                    desired_changes=["Preserve form and line integrity"],
                    invariants=[
                        "Public-only choice",
                        "No damage compensation by position",
                    ],
                    success_criteria=["Independent actual-raster assessment"],
                ),
            )
            episode = root / cand.candidate_id / "episode"
            result = execute(
                request, MotorProgram(body=body, actions=motor.actions), episode
            )
            verified = replay(episode)
            with Image.open(episode / "final.png") as im:
                assert np.array_equal(np.array(im), final)
            assert (
                verified["verified"] and result.final_state_hash == before_measurement
            )
            actual_pass = integrity["line_integrity_pass"] and shape["f1_2px"] >= 0.95
            arms[cand.candidate_id] = dict(
                integrity=integrity,
                shape=shape,
                actual_pass=bool(actual_pass),
                source_replay_verified=True,
                protected_ink_px=shape["drawn_ink_outside_editable_px"],
                actual_costs=result.costs.model_dump(),
                frame_is_canonical_final=True,
            )
        selected = quality_choice["selected_candidate_id"]
        baseline = baseline_choice["selected_candidate_id"]
        row = dict(
            id=case["id"],
            family=case["family"],
            damage=case["damage"],
            good_mode=case["good_mode"],
            good_id=good_candidate.candidate_id,
            bad_id=bad_candidate.candidate_id,
            noop_id=noop.candidate_id,
            quality_choice=quality_choice,
            baseline_choice=baseline_choice,
            arms=arms,
            quality_selected_actual_pass=selected is not None
            and arms[selected]["actual_pass"],
            baseline_selected_actual_pass=baseline is not None
            and arms[baseline]["actual_pass"],
            quality_selected_damaged=selected == bad_candidate.candidate_id,
            decisions_before_execution=True,
            no_measurement_motor=True,
            decision_wall_time_s=decision_wall,
            shape_f1_difference=abs(
                arms[good_candidate.candidate_id]["shape"]["f1_2px"]
                - arms[bad_candidate.candidate_id]["shape"]["f1_2px"]
            ),
        )
        row["passed"] = bool(_row_gate(row))
        rows.append(row)
        (root / "private_evaluation.json").write_text(
            json.dumps(row, indent=2, sort_keys=True) + "\n"
        )
        print(
            case["id"],
            row["passed"],
            integrity.get("reason"),
            arms[good_candidate.candidate_id]["integrity"]["reason"],
            arms[bad_candidate.candidate_id]["integrity"]["reason"],
            "chosen",
            selected,
            flush=True,
        )
    report = dict(
        format=FORMAT,
        configuration=config,
        configuration_hash="sha256:" + hashlib.sha256(raw).hexdigest(),
        results=rows,
        total=len(rows),
        passed=sum(r["passed"] for r in rows),
        baseline_success=sum(r["baseline_selected_actual_pass"] for r in rows),
        quality_success=sum(r["quality_selected_actual_pass"] for r in rows),
        damaged_selected=sum(r["quality_selected_damaged"] for r in rows),
        good_accepted=sum(
            r["quality_choice"]["selected_candidate_id"] == r["good_id"] for r in rows
        ),
        held_out_generalization=False,
        learned_skill=False,
        human_accepted=False,
        scope="Fixed-candidate public-geometry choice, not adaptive repair or general painting",
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
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    report = run(args.out, args.split, args.development_report, args.pilot)
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "total",
                    "passed",
                    "baseline_success",
                    "quality_success",
                    "damaged_selected",
                    "good_accepted",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
