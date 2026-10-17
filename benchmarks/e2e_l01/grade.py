"""Arena-private independent score of real P1 E2E-L01 stored episodes.

No ImageProgram model/trainer import. Reads source-private target only at grading,
after model predictions and episodes are frozen. Never exports it to training.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

THRESHOLD = 180


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path):
    return json.loads(path.read_text())


def grade_image(before: np.ndarray, after: np.ndarray, truth: dict) -> dict:
    if before.shape != (256, 256) or after.shape != before.shape:
        raise ValueError("invalid raster shape")
    cross = truth["cross"]
    b = before[cross, :] if truth["orientation"] == "h" else before[:, cross]
    a = after[cross, :] if truth["orientation"] == "h" else after[:, cross]
    lo, hi = truth["left_end"], truth["right_start"]
    remaining = int(np.count_nonzero(a[lo:hi + 1] >= THRESHOLD))
    if truth["orientation"] == "h":
        outside = np.ones_like(after, dtype=bool)
        outside[max(0, cross - 2):cross + 3, truth["left_start"]:truth["right_end"] + 1] = False
    else:
        outside = np.ones_like(after, dtype=bool)
        outside[truth["left_start"]:truth["right_end"] + 1,
                max(0, cross - 2):cross + 3] = False
    illegal_ink = int(np.count_nonzero((after < THRESHOLD) & (before >= THRESHOLD) & outside))
    newly_darkened = int(np.count_nonzero((after < before) & (before >= THRESHOLD)))
    return {"missing_centerline_px": remaining, "off_corridor_ink_px": illegal_ink,
            "new_ink_px": newly_darkened,
            "quality_pass": remaining == 0 and illegal_ink == 0}


def grade_run(run_dir: Path, output: Path) -> dict:
    """Fail closed when source P1 artifacts or recorded provenance disagree."""
    manifest = _read_json(run_dir / "manifest.json")
    if manifest["format"] != "e2e-l01-experiment-v1" or manifest["status"] != "PENDING_INDEPENDENT_ARENA_GRADE":
        raise ValueError("unsupported/unsealed model run")
    pinned_files = {
        "private_source_sha256": "private/source_tasks.json",
        "episodes_sha256": "episodes.json",
        "train_rows_sha256": "training_public_rows.json",
        "learned_policy_sha256": "learned_policy.json",
    }
    for key, name in pinned_files.items():
        if sha_file(run_dir / name) != manifest[key]:
            raise ValueError(f"run source evidence hash mismatch: {key}")
    truths = _read_json(run_dir / "private" / "source_tasks.json")
    by_task = {r["task_id"]: r for r in truths}
    if len(by_task) != len(truths) or len(truths) != manifest["tasks"]:
        raise ValueError("task lineage identity mismatch")
    records = _read_json(run_dir / "episodes.json")
    if len(records) != manifest["episodes"]:
        raise ValueError("episode count mismatch")
    grades = []
    for record in records:
        task_id = record["task_id"]
        if task_id not in by_task:
            raise ValueError("unrecognized task")
        t = by_task[task_id]
        if t["split"] != record["split"]:
            raise ValueError("split mismatch")
        episode = run_dir / record["path"]
        if not episode.resolve().is_relative_to(run_dir.resolve()):
            raise ValueError("episode escapes run directory")
        source = _read_json(episode / "manifest.json")
        if source["format"] != "imageprogram-episode-1":
            raise ValueError("not a P1 episode")
        for name, expected in source["files"].items():
            file = episode / name
            if not file.resolve().is_relative_to(episode.resolve()) or file.is_symlink():
                raise ValueError("invalid episode artifact path")
            if sha_file(file) != expected:
                raise ValueError("P1 artifact mismatch")
        if sha_file(episode / "final.png") != record["final_png_sha256"]:
            raise ValueError("final raster identity mismatch")
        if sha_file(episode / "result.json") != record["episode_hash"]:
            raise ValueError("episode result identity mismatch")
        result = _read_json(episode / "result.json")
        if (result["status"] != "program_exhausted"
                or result["final_state_hash"] != record["world_state_hash"]
                or record["replay_verified"] is not True):
            raise ValueError("P1 replay/semantic identity mismatch")
        pre = run_dir / "tasks" / task_id / "public" / "initial.png"
        before = np.asarray(Image.open(pre).convert("L"))
        after = np.asarray(Image.open(episode / "final.png").convert("L"))
        grade = grade_image(before, after, t)
        grades.append({"task_id": task_id, "split": t["split"], "arm": record["arm"],
                       "offset": record["offset"], **grade})
    grouped: dict[str, dict[str, dict]] = {}
    for row in grades:
        if row["split"] == "frozen":
            grouped.setdefault(row["task_id"], {})[row["arm"]] = row
    if len(grouped) != 12 or any(set(v) != {"A0_fixed", "A1_analytic", "A2_learned"}
                                  for v in grouped.values()):
        raise ValueError("incomplete frozen arms")
    candidate = [g["A2_learned"] for g in grouped.values()]
    baseline = [g["A1_analytic"] for g in grouped.values()]
    wins = sum(a["quality_pass"] and not b["quality_pass"] for a, b in zip(candidate, baseline))
    losses = sum(b["quality_pass"] and not a["quality_pass"] for a, b in zip(candidate, baseline))
    changed = sum(a["offset"] != b["offset"] for a, b in zip(candidate, baseline))
    pass_count = sum(a["quality_pass"] for a in candidate)
    passed = pass_count >= 9 and wins >= 3 and losses == 0 and changed >= 1
    report = {"format": "e2e-l01-independent-grade-v1", "model_run_manifest_sha": sha_file(run_dir / "manifest.json"),
              "n_graded_episodes": len(grades), "frozen_tasks": 12,
              "learned_pass": pass_count, "a2_pure_wins": wins, "a2_pure_losses": losses,
              "changed_choice_tasks": changed, "accepted": passed,
              "claim": "limited_synthetic_join_improvement" if passed else "NOT_DEMONSTRATED",
              "grades": grades}
    output.mkdir(parents=True, exist_ok=False)
    (output / "independent_grade.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    # Offline Before/After comparison; copy only verified episode PNGs.
    review = output / "review"
    review.mkdir()
    cards = []
    for task_id in sorted(grouped):
        initial = run_dir / "tasks" / task_id / "public" / "initial.png"
        shutil.copyfile(initial, review / f"{task_id}-before.png")
        figures = [f'<figure><img src="{task_id}-before.png"><figcaption>Before</figcaption></figure>']
        for arm in ("A0_fixed", "A1_analytic", "A2_learned"):
            source_png = run_dir / "tasks" / task_id / arm / "final.png"
            target_name = f"{task_id}-{arm}.png"
            shutil.copyfile(source_png, review / target_name)
            verdict = "PASS" if grouped[task_id][arm]["quality_pass"] else "FAIL"
            figures.append(f'<figure><img src="{target_name}"><figcaption>{arm}: {verdict}</figcaption></figure>')
        cards.append(f'<section><h2>{html.escape(task_id)}</h2><div class="row">' + "".join(figures) + '</div></section>')
    page = ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<title>E2E-L01 before/after</title><style>'
            'body{font:15px system-ui;margin:1.5em;max-width:1100px}'
            '.row{display:flex;gap:1em;flex-wrap:wrap}'
            'figure{margin:0;width:220px}img{width:100%;border:1px solid #888}'
            'figcaption{font-size:13px}section{margin-bottom:2em}'
            '</style><h1>E2E-L01 — real P1 Canvas comparison</h1>'
            '<p>Independent synthetic transfer only. No visual acceptance claim.</p>'
            + "".join(cards) + '</html>')
    (review / "index.html").write_text(page, encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = grade_run(args.run, args.out)
    print(json.dumps({k: v for k, v in report.items() if k != "grades"}, indent=2))


if __name__ == "__main__":
    main()
