"""Synthetic-only ART-1 E1 G2 paired experiment (no original artwork required).

Run with ImageProgram's pinned render environment; no network, model training,
user-supplied images, Drive download or paid CI is performed by this command.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from adapters.imageprogram_reference.drawing_review import create_review_pack
from adapters.imageprogram_reference.public_reference_roi_v1 import export_permitted_roi_v1
from adapters.imageprogram_reference.score_feedback_e1_v1 import score_paired_e1_v1
from adapters.imageprogram_reference.source_artwork import ingest_local_source

FORMAT = "art1-e1-g2-synthetic-evidence-v1"
MODES = ("noop", "feedback_off", "feedback_on")


def _git_sha(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


def run_synthetic_g2_v1(output: Path) -> dict:
    """Produce real paired P1 Episodes and independently scored synthetic results."""
    try:
        import imageprogram
        from imageprogram.experiments.art1_feedback_session_v1 import (
            run_feedback_session_v1,
        )
    except ImportError as exc:
        raise RuntimeError(
            "ImageProgram must be installed in this Python interpreter; "
            "use the Model repository's uv-created .venv/bin/python"
        ) from exc

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    model_root = Path(imageprogram.__file__).resolve().parents[2]
    arena_root = Path(__file__).resolve().parents[2]
    model_sha = _git_sha(model_root)
    arena_sha = _git_sha(arena_root)
    if model_sha != "6d8e6399a2b0a44d08054a08b71b4a68d4d9e374":
        raise RuntimeError("synthetic experiment requires pinned Model PR #81 SHA")

    management = output / "management"
    management.mkdir()
    source = management / "synthetic-reference.png"
    image = Image.new("RGB", (128, 160), (255, 255, 255))
    ImageDraw.Draw(image).line([(20, 70), (99, 70)], fill=(0, 0, 0), width=1)
    image.save(source, format="PNG")
    source_manifest = ingest_local_source(
        source,
        editable_bbox=(0, 0, 128, 160),
        source_family="generated-art1-e1-g2",
        rights="generated-test-fixture",
    )
    record = management / "source_manifest.json"
    record.write_text(json.dumps(source_manifest, indent=2) + "\n", encoding="utf-8")
    public = output / "public_roi"
    export_permitted_roi_v1(source, record, public)

    cases = {}
    checks = {}
    for case, fraction in (("underdraw", 0.55), ("complete", 1.0)):
        case_root = output / case
        case_root.mkdir()
        sessions = case_root / "sessions"
        model_summary = run_feedback_session_v1(
            public, sessions, seed=17, initial_fraction=fraction,
        )
        score = score_paired_e1_v1(
            public, sessions, case_root / "arena_independent_score.json"
        )
        for mode in MODES:
            if mode not in score["replay_verified_arms"]:
                raise RuntimeError("an actual P1 arm was not source-replay verified")
        receipt = model_summary["episodes"]["feedback_on"]["decision_receipt"]
        decision = receipt["decision"]["kind"]
        extra_motor = receipt["actual_correction_action_count"]
        outside_zero = all(
            score["scores"][m]["drawn_ink_outside_editable_px"] == 0 for m in MODES
        )
        if case == "underdraw":
            passed = (
                decision == "execute"
                and extra_motor > 0
                and score["delta_f1_on_minus_off"] > 0
                and score["initial_actions_identical"]
                and score["intermediate_replay_raster_bound"]
                and outside_zero
                and score["scores"]["noop"]["drawn_ink_px"] == 0
            )
            # This case has three different physical trajectories: the original
            # Review Pack's anti-duplicate policy remains unmodified.
            if passed:
                create_review_pack(
                    [
                        (
                            mode, sessions / (mode + "_episode"),
                            sessions / (mode + "_replay.json"),
                        )
                        for mode in MODES
                    ],
                    case_root / "review",
                )
        else:
            # Under a fully drawn prefix, Stop must not append a second stroke.
            # An identical on/off physical trace is legitimate, not three
            # independent improved drawings. Preserve the v0 duplicate guard.
            passed = decision == "stop" and extra_motor == 0 and outside_zero
        checks[case] = bool(passed)
        cases[case] = {
            "initial_fraction": fraction,
            "decision_kind": decision,
            "correction_motor_commands": extra_motor,
            "delta_f1_on_minus_off": score["delta_f1_on_minus_off"],
            "protected_ink_zero": outside_zero,
            "physical_equivalence_is_not_independent_improvement":
                case == "complete" and decision == "stop",
            "source_replay_modes": score["replay_verified_arms"],
            "costs": {
                m: {
                    "motor_commands": score["scores"][m]["motor_commands"],
                    "strokes": score["scores"][m]["strokes"],
                    "sim_time_s": score["scores"][m]["sim_time_s"],
                    "wall_time_s": score["scores"][m]["wall_time_s"],
                    "eye_sensor_acquisitions": score["scores"][m]["eye_sensor_acquisitions"],
                    "eye_query_evaluations": score["scores"][m]["eye_query_evaluations"],
                }
                for m in MODES
            },
            "status": "PASS" if passed else "FAIL",
        }

    evidence = {
        "format": FORMAT,
        "model_git_sha": model_sha,
        "arena_git_sha": arena_sha,
        "evidence_is": "real_p1_episodes_scored_on_generated_synthetic_roi",
        "independent_physics_engine": False,
        "learned_eye": False,
        "learned_skill": False,
        "human_accepted": False,
        "local_quality_gates_attested": False,
        "checks": checks,
        "cases": cases,
        "status": "SYNTHETIC_CASES_PASS" if all(checks.values()) else "SYNTHETIC_CASES_FAIL",
        "warning": "G2 PASS also requires full Arena+Model local lint/tests, no skipped paired tests, and tamper suite",
    }
    (output / "provenance.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not all(checks.values()):
        raise RuntimeError("synthetic G2 case failed; examine local provenance.json")
    return evidence


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    summary = run_synthetic_g2_v1(args.out)
    print(json.dumps({
        "status": summary["status"],
        "model_sha": summary["model_git_sha"],
        "arena_sha": summary["arena_git_sha"],
        "cases": summary["checks"],
        "report": str(args.out / "provenance.json"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
