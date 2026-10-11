"""ART-1 E1 independent scoring of replay-verified actual P1 comparative episodes.

The scorer consumes only policy-public ROI + canonical output artifacts. It
does not use the policy's estimated target/difference/mask, or original source.
A summary without three successful real P1 replays is never a scored result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from adapters.imageprogram_reference.drawing_review import source_replay
from adapters.imageprogram_reference.reference_target_v1 import (
    FirstContactScoreError, score_terminal_v1, target_and_masks_v1,
)

FORMAT = "art1-e1-independent-episode-score-v1"
MODES = ("noop", "feedback_off", "feedback_on")


def _regular(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise FirstContactScoreError("missing or symlinked Episode/task artifact")
    return path


def _json(path: Path) -> dict:
    try:
        value = json.loads(_regular(path).read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise FirstContactScoreError("invalid Episode/task JSON") from exc
    if not isinstance(value, dict):
        raise FirstContactScoreError("expected JSON object")
    return value


def _frame(path: Path) -> np.ndarray:
    with Image.open(_regular(path)) as image:
        if image.mode != "L" or image.size != (256, 256) or image.format != "PNG":
            raise FirstContactScoreError("P1 frame is not PNG L8 256x256")
        return np.asarray(image).copy()


def _world_hash(pixels: np.ndarray) -> str:
    header = b"imageprogram-L8:256:256:"
    return "sha256:" + hashlib.sha256(header + pixels.tobytes(order="C")).hexdigest()


def _transitions(path: Path) -> list[dict]:
    values = []
    with _regular(path).open(encoding="utf-8") as stream:
        for row in stream:
            event = json.loads(row)
            if not isinstance(event, dict):
                raise FirstContactScoreError("non-object P1 transition")
            values.append(event)
    return values


def score_paired_e1_v1(
    public_dir: Path, run_dir: Path, output_file: Path
) -> dict:
    public_dir, run_dir = Path(public_dir), Path(run_dir)
    task = _json(public_dir / "task.json")
    png = _regular(public_dir / "reference_roi.png").read_bytes()
    # Independently recompute, validate task version/geometry/crop hash, E and P.
    target, editable, protected = target_and_masks_v1(task, png)
    if not target.any() or not protected.any() or not editable.any():
        raise FirstContactScoreError("unscorable v1 ROI target")
    session = _json(run_dir / "summary.json")
    if (session.get("format") != "art1-e1-live-p1-session-v1"
            or session.get("task_format") != task["format"]
            or session.get("transform_version") != task["placement"]["transform_version"]
            or session.get("learned_eye") is not False
            or session.get("learned_skill") is not False
            or session.get("independent_arena_scored") is not False
            or not isinstance(session.get("episodes"), dict)
            or set(session["episodes"]) != set(MODES)):
        raise FirstContactScoreError("invalid or falsely claimed E1 Model run")
    verified, scores = {}, {}
    initial_states, seeds, bodies, budgets = [], [], [], []
    for mode in MODES:
        episode = run_dir / (mode + "_episode")
        if episode.is_symlink() or not episode.is_dir():
            raise FirstContactScoreError("missing or symlinked P1 Episode directory")
        replay_report = source_replay(episode)
        if replay_report.get("verified") is not True or replay_report.get("status") != "program_exhausted":
            raise FirstContactScoreError("canonical source P1 replay failed")
        request = _json(episode / "request.json")
        program = _json(episode / "program.json")
        result = _json(episode / "result.json")
        if result.get("status") != "program_exhausted":
            raise FirstContactScoreError("P1 execution incomplete")
        if program.get("body") != request.get("body") or not isinstance(
            program.get("actions"), list
        ):
            raise FirstContactScoreError("incompatible World Body/Motor program")
        costs = result.get("costs")
        if not isinstance(costs, dict) or costs.get("motor_commands") != len(
            program["actions"]
        ):
            raise FirstContactScoreError("P1 motor accounting mismatch")
        initial_states.append(result.get("initial_state_hash"))
        seeds.append(request.get("seed"))
        bodies.append(request.get("body"))
        budgets.append(request.get("budget"))
        recorded = session["episodes"][mode]
        if not isinstance(recorded, dict) or recorded.get("replay_verified") is not True:
            raise FirstContactScoreError("missing E1 receipt")
        if (
            recorded.get("final_state_hash") != result.get("final_state_hash")
            or recorded.get("initial_state_hash") != result.get("initial_state_hash")
            or recorded.get("actual_costs") != costs
        ):
            raise FirstContactScoreError("E1 receipt/P1 result divergence")
        original_recorded = _json(run_dir / (mode + "_receipt.json"))
        if original_recorded != recorded:
            raise FirstContactScoreError("sidecar receipt and summary differ")
        sensor = recorded.get("extra_eye_sensor_acquisitions")
        queries = recorded.get("extra_eye_query_evaluations")
        if (type(sensor) is not int or type(queries) is not int
                or not 1 <= sensor <= 4 or not 0 <= queries <= 8):
            raise FirstContactScoreError("invalid bounded Eye usage")
        if mode != "feedback_on" and queries != 0:
            raise FirstContactScoreError("off/noop must not read decision discrepancy")
        raster = _frame(episode / "final.png")
        score = score_terminal_v1(task, png, raster)
        if mode == "noop" and score["drawn_ink_px"] != 0:
            raise FirstContactScoreError("noop must deposit no ink")
        scores[mode] = {
            **score,
            "motor_commands": costs["motor_commands"],
            "strokes": costs["strokes"],
            "sim_time_s": costs["sim_time_s"],
            "wall_time_s": costs["wall_time_s"],
            "eye_sensor_acquisitions": sensor,
            "eye_query_evaluations": queries,
            "source_replay_verified": True,
        }
        verified[mode] = (program, result, recorded, _transitions(episode / "transitions.jsonl"))
    if (len(set(initial_states)) != 1 or len(set(seeds)) != 1
            or bodies[0] != bodies[1] or bodies[1] != bodies[2]
            or budgets[0] != budgets[1] or budgets[1] != budgets[2]):
        raise FirstContactScoreError("comparator initial states/config/budget differ")
    off_prog, _, off_record, _ = verified["feedback_off"]
    on_prog, _, on_record, on_events = verified["feedback_on"]
    off_actions = off_prog["actions"]
    on_actions = on_prog["actions"]
    split = off_record.get("first_action_count")
    if (type(split) is not int or split != len(off_actions)
            or split < 2 or on_record.get("first_action_count") != split
            or on_actions[:split] != off_actions
            or off_record.get("post_initial_state_hash")
            != on_record.get("post_initial_state_hash")
            or off_record.get("initial_action_sha256")
            != on_record.get("initial_action_sha256")):
        raise FirstContactScoreError("feedback on/off initial actions were not identical")
    receipt = on_record.get("decision_receipt")
    if not isinstance(receipt, dict):
        raise FirstContactScoreError("feedback_on has no poststroke evidence")
    if (receipt.get("initial_action_count") != split
            or receipt.get("intermediate_world_state_hash") != on_events[split - 1].get("state_after")
            or receipt.get("intermediate_world_state_hash") != on_record.get("post_initial_state_hash")
            or receipt.get("canvas_sim_time_s") != on_events[split - 1].get("sim_end_ns") / 1e9):
        raise FirstContactScoreError("poststroke decision not tied to actual initial P1 prefix")
    intermediate = _frame(run_dir / "feedback_on_episode" / "frames" / f"{split:06d}.png")
    if receipt.get("canvas_image_sha256") != _world_hash(intermediate):
        raise FirstContactScoreError("decision used forged/nonreplayed World raster")
    difference = receipt.get("difference")
    decision = receipt.get("decision")
    repair_count = len(on_actions) - split
    if (not isinstance(difference, dict) or not isinstance(decision, dict)
            or difference.get("canvas_frame_id") != receipt.get("canvas_frame_id")
            or difference.get("canvas_digest") != receipt.get("canvas_image_sha256")
            or difference.get("reference_digest") != receipt.get("reference_digest")
            or difference.get("status") not in ("measured", "unknown")
            or receipt.get("actual_correction_action_count") != repair_count
            or decision.get("kind") not in ("stop", "execute")
            or (decision["kind"] == "stop" and repair_count != 0)
            or (decision["kind"] == "execute" and repair_count == 0)):
        raise FirstContactScoreError("repair decision is not supported by replayed observation")
    # All three actual P1 episodes, sidecars and independent evaluator agree.
    output_file = Path(output_file)
    if output_file.is_symlink() or output_file.exists():
        raise FirstContactScoreError("independent score output must not pre-exist")
    report = {
        "format": FORMAT,
        "claim": "independently scored real P1 episode rasters; human review pending",
        "transform_version": task["placement"]["transform_version"],
        "reference_sha256": task["reference_roi_sha256"],
        "initial_actions_identical": True,
        "intermediate_replay_raster_bound": True,
        "replay_verified_arms": list(MODES),
        "scores": scores,
        "delta_f1_on_minus_off": (
            scores["feedback_on"]["f1_2px"] - scores["feedback_off"]["f1_2px"]
        ),
        "human_accepted": False,
    }
    output_file.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-roi", required=True, type=Path)
    parser.add_argument("--sessions", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = score_paired_e1_v1(args.public_roi, args.sessions, args.out)
    print(json.dumps({
        "status": "ARENA_V1_INDEPENDENT_SCORE_READY_VISUAL_REVIEW_PENDING",
        "delta_f1_on_minus_off": report["delta_f1_on_minus_off"],
    }))


if __name__ == "__main__":
    main()
