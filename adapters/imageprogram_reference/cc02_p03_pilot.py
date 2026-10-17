"""P03 synthetic DEV/confirmation task author and public-only predictor.

PREPARE -> pin public/private SHA externally -> PREDICT -> pin prediction SHA
externally -> separate cc02_p03_review GRADE. No Model imports here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import subprocess
from pathlib import Path

from adapters.imageprogram_reference.cc02_p03_review import VERSION, digest
from adapters.imageprogram_reference.cc02_r2_dev_pilot import task as r2_legacy_task


def new_task(shape, level, phase=0):
    size = 64
    pixels = [[255] * size for _ in range(size)]
    xs = range(12, 49)
    targets = []
    for x in xs:
        t = x - 12
        if shape == "flat":
            y = 20 + phase % 4
        elif shape == "incline":
            y = 14 + round((t + phase % 3) / 4)
        elif shape == "arc":
            y = 20 + round(5 * ((t - 18) / 18) ** 2) + phase % 3
        elif shape == "sine":
            y = 22 + round(4 * math.sin((t + phase % 4) * math.pi / 20))
        else:
            raise ValueError("invalid-geometry-family")
        pixels[y][x] = level
        targets.append([x + 0.5, y + 0.5])
    # Fully separated strong distractor: wrong to follow, but clearly visible.
    for x in range(10, 54):
        pixels[46][x] = 0
    excluded = [[x + 0.5, 46.5] for x in range(10, 54)]
    return _public(pixels, targets[0]), targets, [excluded]


def heldout_task(seed, level):
    """Distinct confirmation-only step-slope grammar; never tune on its output."""
    rng = random.Random(seed)
    pixels = [[255] * 64 for _ in range(64)]
    y = rng.randrange(16, 28)
    slope = rng.choice((-1, 0, 1))
    target = []
    for t, x in enumerate(range(12, 49)):
        if t % 6 == 0:
            slope = rng.choice((-1, 0, 1))
        if rng.random() < 0.65:
            y = max(13, min(36, y + slope))
        pixels[y][x] = level
        target.append([x + 0.5, y + 0.5])
    for x in range(10, 54):
        pixels[46][x] = 0
    excluded = [[x + 0.5, 46.5] for x in range(10, 54)]
    return _public(pixels, target[0]), target, [excluded]


def _public(pixels, anchor):
    data = bytes(v for row in pixels for v in row)
    return {
        "pixels_l8": pixels,
        "raster_sha256": hashlib.sha256(data).hexdigest(),
        "focus_box": [8, 8, 56, 56],
        "anchor_px": anchor,
        "threshold": 145,
        "dominance_ratio": 1.35,
        "max_candidates": 128,
    }


def control(kind):
    pixels = [[255] * 64 for _ in range(64)]
    if kind == "four-noise-dots":
        for x, y in ((11, 11), (22, 35), (41, 14), (48, 50)):
            pixels[y][x] = 180
    elif kind == "near-white":
        for x in range(12, 49):
            pixels[23][x] = 230
    elif kind == "weak-distractor":
        for x in range(12, 49):
            pixels[23][x] = 180
    elif kind == "candidate-overflow":
        for y in (11, 17, 23, 29, 35, 41, 49):
            for x in range(12, 49):
                pixels[y][x] = 180
    elif kind != "blank":
        raise ValueError("unknown-control")
    return _public(pixels, [12.5, 23.5]), [], []


def prepare(out, split):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    tasks = out / "public_tasks"
    tasks.mkdir()
    manifest = {"protocol": VERSION, "split": split, "cases": []}
    priv = {"protocol": VERSION, "public_sha256": "", "cases": []}

    def add(case_id, family_id, kind, public, accepted, excluded):
        i = len(manifest["cases"])
        if case_id in {case["case_id"] for case in manifest["cases"]}:
            raise ValueError("duplicate-case-id")
        with (tasks / f"task-{i:03d}.json").open("x", encoding="utf-8") as f:
            json.dump(public, f, sort_keys=True, indent=2)
            f.write("\n")
        manifest["cases"].append({
            "case_id": case_id, "raster_sha256": public["raster_sha256"],
            "public_task_sha256": digest(public)})
        priv["cases"].append({
            "case_id": case_id, "family_id": family_id, "kind": kind,
            "accepted_paths_xy": accepted, "excluded_paths_xy": excluded,
        })

    if split == "development":
        # Historical R2 visual cases are re-run from source as a regression;
        # never reuse their old predictions as new evidence.
        for family in ("single-line", "longer-neighbor", "equal-neighbor",
                       "faint-target"):
            for transposed in (False, True):
                p, t = r2_legacy_task(family, transposed)
                add("r2-" + family + ("-t" if transposed else "-n"),
                    "r2-" + family, "unique_path", p, [t], [])
        for shape in ("flat", "incline", "arc", "sine"):
            for l8 in (140, 160, 180, 195):
                p, t, excluded = new_task(shape, l8)
                add(f"dev-{shape}-l8-{l8}", f"dev-{shape}",
                    "unique_path", p, [t], excluded)
    else:
        # Confirmation uses a DIFFERENT stochastic step-slope generator
        # with independent seeded draws, not the four DEV analytic templates.
        # Do not preview, tune or grade these until the DEV settings freeze.
        for i in range(12):
            l8 = (160, 180, 195)[i // 4]
            p, t, excluded = heldout_task(2026101703 + i * 10007, l8)
            add(f"confirm-lineage-{i:02d}", f"lineage-{i:02d}",
                "unique_path", p, [t], excluded)
    for kind in ("blank", "four-noise-dots", "near-white",
                 "weak-distractor", "candidate-overflow"):
        p, accepted, excluded = control(kind)
        add("control-" + kind, "control-" + kind,
            "observation_insufficient", p, accepted, excluded)

    public_sha = digest(manifest)
    priv["public_sha256"] = public_sha
    with (out / "public.json").open("x", encoding="utf-8") as f:
        json.dump(manifest, f, sort_keys=True, indent=2)
        f.write("\n")
    with (out / "private.json").open("x", encoding="utf-8") as f:
        json.dump(priv, f, sort_keys=True, indent=2)
        f.write("\n")
    print(json.dumps({"split": split, "public_sha256": public_sha,
                      "private_sha256": digest(priv),
                      "cases": len(manifest["cases"])}, sort_keys=True))
    return manifest, priv


def predict(out, model_checkout, model_python, public_sha):
    out = Path(out).resolve()
    manifest = json.loads((out / "public.json").read_text(encoding="utf-8"))
    if digest(manifest) != public_sha:
        raise ValueError("unanchored-public-sha")
    model_checkout = Path(model_checkout).resolve()
    outputs = out / "model_outputs"
    outputs.mkdir(exist_ok=False)
    rows = []
    for i, case in enumerate(manifest["cases"]):
        public_file = out / "public_tasks" / f"task-{i:03d}.json"
        data = json.loads(public_file.read_text(encoding="utf-8"))
        if digest(data) != case["public_task_sha256"]:
            raise ValueError("changed-public-task")
        destination = outputs / f"bank-{i:03d}.json"
        subprocess.run([
            str(model_python),
            str(model_checkout / "scripts" / "cc02_p03_export_bank.py"),
            "--public", str(public_file),
            "--public-sha256", case["public_task_sha256"],
            "--out", str(destination),
        ], cwd=model_checkout, check=True)
        model = json.loads(destination.read_text(encoding="utf-8"))
        if (model["public_canonical_sha256"] != case["public_task_sha256"]
                or model["observation"]["raster_sha256"] != case["raster_sha256"]
                or digest({k: v for k, v in model.items()
                           if k != "canonical_sha256"}) != model["canonical_sha256"]):
            raise ValueError("model-receipt-drift")
        rows.append({
            "case_id": case["case_id"],
            "public_task_sha256": case["public_task_sha256"],
            "model_git_commit": model["model_git_commit"],
            "observation": model["observation"],
        })
    result = {"protocol": VERSION, "public_sha256": public_sha, "cases": rows}
    with (out / "prediction.json").open("x", encoding="utf-8") as f:
        json.dump(result, f, sort_keys=True, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"prediction_sha256": digest(result),
                      "predicted": len(rows)}, sort_keys=True))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase", required=True, choices=("prepare", "predict"))
    p.add_argument("--split", choices=("development", "confirmation"),
                   default="development")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--public-sha256")
    p.add_argument("--model-checkout", type=Path)
    p.add_argument("--model-python", default="python3.12")
    args = p.parse_args()
    if args.phase == "prepare":
        prepare(args.out, args.split)
    elif args.public_sha256 and args.model_checkout:
        predict(args.out, args.model_checkout, args.model_python, args.public_sha256)
    else:
        p.error("predict requires --model-checkout and externally anchored public SHA")


if __name__ == "__main__":
    main()
