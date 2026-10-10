"""Audit a *real* C2 -> A0 run. Never generates or fabricates episode evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class Gate0Failure(ValueError):
    """Source/review evidence contradicts the Gate 0 contract."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise Gate0Failure(message)


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"not an object: {path.name}")
    return data


def audit(c2: Path, review: Path, model_sha: str, arena_sha: str) -> dict:
    summary = read_json(c2 / "public" / "summary.json")
    pack = read_json(review / "review.json")
    require(summary.get("same_preparation_state") is True, "different C2 preparation")
    require(summary.get("candidate_count", 0) >= 2, "fewer than two candidates")
    require(summary.get("frozen_character_witness_modified") is False,
            "original Character witness changed")
    outcomes = summary.get("episodes")
    require(isinstance(outcomes, dict) and set(outcomes) == {"analytic", "manual"},
            "missing/different C2 outcomes")
    sessions = pack.get("sessions")
    require(isinstance(sessions, list) and len(sessions) == 2,
            "review must contain exactly two sessions")
    by_label = {s.get("label"): s for s in sessions if isinstance(s, dict)}
    require(set(by_label) == {"analytic", "manual"}, "bad review session labels")
    require(pack.get("claims", {}).get("visualized_real_source_episode") is True,
            "review did not claim real source episode")
    require(pack.get("claims", {}).get("learned_policy_or_skill") is False,
            "review incorrectly claims learned skill")
    require(pack.get("claims", {}).get("independent_arena_replay") is False,
            "Arena cannot claim independent physics replay")
    source_initials, source_finals, request_semantics, program_semantics = [], [], [], []
    results = {}
    for label in ("analytic", "manual"):
        outcome, session = outcomes[label], by_label[label]
        attestation = read_json(c2 / "private" / f"{label}_replay.json")
        require(outcome.get("replay_verified") is True and attestation.get("verified") is True,
                f"{label}: unverified source replay")
        require(session.get("fresh_source_replay_verified") is True and
                session.get("replay_attested_by_source") is True,
                f"{label}: Arena did not freshly replay source")
        require(outcome.get("status") == "program_exhausted" and
                session.get("status") == "program_exhausted",
                f"{label}: not a completed Motor program")
        require(attestation.get("final_state_hash") == outcome.get("final_state_hash") ==
                session.get("final_state_hash"), f"{label}: final hash mismatch")
        require(outcome.get("initial_state_hash") == session.get("initial_state_hash"),
                f"{label}: initial state mismatch")
        require(isinstance(outcome.get("newly_darkened_pixels"), int) and
                outcome["newly_darkened_pixels"] > 0,
                f"{label}: no actual ink deposited")
        require(outcome.get("goal_evaluated_by_p1") is False and
                attestation.get("goal_evaluated") is False,
                f"{label}: P1 program completion misrepresented as Goal success")
        require(outcome.get("learned") is False,
                f"{label}: incorrectly claims learned behavior")
        protected = outcome.get("protection_added_ink")
        require(isinstance(protected, dict) and protected and
                all(type(x) in (float, int) and x == 0 for x in protected.values()),
                f"{label}: protection violation/omitted protection check")
        actions = outcome.get("accepted_actions")
        require(type(actions) is int and actions >= 2 and
                actions == session.get("accepted_actions") == attestation.get("transitions"),
                f"{label}: action count mismatch")
        require(outcome.get("costs", {}).get("motor_commands") == actions,
                f"{label}: continuation cost includes preparation or differs from actions")
        require(isinstance(outcome.get("re_observation"), dict),
                f"{label}: missing re-observation")
        pictures = session.get("images")
        require(isinstance(pictures, dict) and
                set(pictures) == {"initial", "intermediate", "final"},
                f"{label}: review frames missing")
        # The Arena consumer verified source frames while constructing the Pack.
        # Independently check the *current* Review Pack bytes against that
        # evidence; file-existence alone also accepts fake/truncated images.
        for kind, item in pictures.items():
            require(isinstance(item, dict) and
                    item.get("file") == f"{label}-{kind}.png",
                    f"{label}: invalid review frame path")
            path = review / item["file"]
            require(path.is_file() and not path.is_symlink(),
                    f"{label}: review frames missing or symlinked")
            data = path.read_bytes()
            digest = "sha256:" + hashlib.sha256(data).hexdigest()
            require(len(data) >= 24 and data[:8] == b"\x5cx89PNG\x5cr\x5cn\x5cx1a\x5cn" and
                    data[12:16] == b"IHDR",
                    f"{label}: invalid PNG review frame")
            require(item.get("sha256") == item.get("source_sha256") == digest,
                    f"{label}: review frame digest mismatch")
        source_initials.append(session.get("initial_state_hash"))
        source_finals.append(session.get("final_state_hash"))
        request_semantics.append(session.get("source_request_semantic_hash"))
        program_semantics.append(session.get("source_program_semantic_hash"))
        results[label] = {
            "accepted_actions": actions,
            "newly_darkened_pixels": outcome["newly_darkened_pixels"],
            "protected_new_ink": protected,
            "replay_verified": True,
            "fresh_source_replay_verified": True,
            "initial_state_hash": session["initial_state_hash"],
            "final_state_hash": session["final_state_hash"],
            "continuation_costs": outcome["costs"],
        }
    require(source_initials[0] == source_initials[1],
            "A/B did not start from same checkpoint")
    require(source_finals[0] != source_finals[1],
            "A/B produced identical final states")
    require(program_semantics[0] != program_semantics[1],
            "A/B programs are semantically identical")
    require(len(set(request_semantics)) == 1,
            "A/B changed task/body/budget rather than only the candidate")
    require(all(isinstance(s, str) and len(s) == 40 for s in (model_sha, arena_sha)),
            "missing pinned Git commit SHAs")
    return {
        "format": "art1-gate0-audit-v0",
        "status": "AUTOMATED_PASS_VISUAL_REVIEW_PENDING",
        "claim": "Two real C2 source episodes, fresh ImageProgram replays and Arena Review Pack were audited; not image learning or visual quality",
        "source_commits": {"ImageProgram": model_sha, "ImageProgram-Arena": arena_sha},
        "results": results,
        "human_visual_review": "pending",
        "next_step": "Open local Review Pack index.html, inspect both final PNGs, record human sign-off before Gate 0 PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c2", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--model-sha", required=True)
    parser.add_argument("--arena-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.c2, args.review, args.model_sha, args.arena_sha)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"{report['status']}: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
