"""Create bounded NEW CC-02-R2 DEV rasters; run Model with no private imports.

Phases: prepare -> externally anchor public/private -> predict ->
externally anchor prediction -> separate Arena grade CLI. NEVER confirmation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from adapters.imageprogram_reference.cc02_r2_candidate_review import VERSION, digest


def task(kind, transpose):
    size = 64
    pixels = [[255] * size for _ in range(size)]
    def line(y, x0, x1, value=0):
        for x in range(x0, x1 + 1):
            pixels[y][x] = value
    line(23, 13, 39, 180 if kind == "faint-target" else 0)
    if kind == "longer-neighbor" or kind == "faint-target":
        line(41, 10, 52)
    if kind == "equal-neighbor":
        line(41, 10, 36)
    if kind == "no-target":
        pixels = [[255] * size for _ in range(size)]
    if transpose:
        pixels = [list(row) for row in zip(*pixels)]
    def point(x, y):
        return [y + 0.5, x + 0.5] if transpose else [x + 0.5, y + 0.5]
    target = [point(x, 23) for x in range(13, 40)]
    raster_sha = hashlib.sha256(bytes(b for row in pixels for b in row)).hexdigest()
    public = {"pixels_l8": pixels, "raster_sha256": raster_sha,
              "focus_box": [8, 8, 56, 56], "anchor_px": point(13, 23),
              "threshold": 145, "dominance_ratio": 1.35, "max_candidates": 128}
    return public, target


def prepare(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    taskdir = out / "public_tasks"
    taskdir.mkdir()
    manifest = {"protocol": VERSION, "split": "development", "cases": []}
    private_cases = []
    families = ("single-line", "longer-neighbor", "equal-neighbor", "faint-target")
    for kind in families:
        for transpose in (False, True):
            case_id = kind + ("-transpose" if transpose else "-normal")
            public, target = task(kind, transpose)
            task_sha = digest(public)
            task_number = len(manifest["cases"])
            path = taskdir / f"task-{task_number:02d}.json"
            path.write_text(json.dumps(public, sort_keys=True, indent=2) + "\n",
                            encoding="utf-8")
            manifest["cases"].append({
                "case_id": case_id, "raster_sha256": public["raster_sha256"],
                "public_task_sha256": task_sha,
            })
            private_cases.append({
                "case_id": case_id, "family_id": kind,
                "kind": "unique_path", "accepted_paths_xy": [target],
            })
    # No-ink control: preserve in denominator but not an exact positive path.
    pub, _ = task("no-target", False)
    i = len(manifest["cases"])
    (taskdir / f"task-{i:02d}.json").write_text(
        json.dumps(pub, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    manifest["cases"].append({
        "case_id": "no-ink-control", "raster_sha256": pub["raster_sha256"],
        "public_task_sha256": digest(pub),
    })
    private_cases.append({"case_id": "no-ink-control", "family_id": "control",
                          "kind": "observation_insufficient", "accepted_paths_xy": []})
    manifest_sha = digest(manifest)
    private = {"protocol": VERSION, "public_sha256": manifest_sha, "cases": private_cases}
    (out / "public.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "private.json").write_text(
        json.dumps(private, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"public_sha256": manifest_sha, "private_sha256": digest(private),
                      "cases": len(manifest["cases"]), "unique_families": 4},
                     sort_keys=True))
    return manifest, private


def predict(out, model_checkout, model_python, public_sha):
    out = Path(out).resolve()
    manifest = json.loads((out / "public.json").read_text(encoding="utf-8"))
    if digest(manifest) != public_sha:
        raise ValueError("unanchored-public-manifest")
    model_checkout = Path(model_checkout).resolve()
    root = out / "model_outputs"
    root.mkdir(exist_ok=False)
    rows = []
    for i, case in enumerate(manifest["cases"]):
        public_file = out / "public_tasks" / f"task-{i:02d}.json"
        if digest(json.loads(public_file.read_text(encoding="utf-8"))) != case[
                "public_task_sha256"]:
            raise ValueError("unanchored-task")
        outfile = root / f"bank-{i:02d}.json"
        subprocess.run([
            str(model_python), str(model_checkout / "scripts" / "cc02_r2_export_bank.py"),
            "--public", str(public_file),
            "--public-sha256", case["public_task_sha256"],
            "--out", str(outfile),
        ], cwd=model_checkout, check=True)
        result = json.loads(outfile.read_text(encoding="utf-8"))
        if (result["public_canonical_sha256"] != case["public_task_sha256"]
                or result["observation"]["raster_sha256"] != case["raster_sha256"]
                or digest({k: v for k, v in result.items() if k != "canonical_sha256"})
                != result["canonical_sha256"]):
            raise ValueError("model-output-evidence-drift")
        rows.append({
            "case_id": case["case_id"],
            "public_task_sha256": case["public_task_sha256"],
            "model_git_commit": result["model_git_commit"],
            "observation": result["observation"],
        })
    prediction = {"protocol": VERSION, "public_sha256": public_sha, "cases": rows}
    (out / "prediction.json").open("x", encoding="utf-8").write(
        json.dumps(prediction, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"prediction_sha256": digest(prediction), "predicted": len(rows)},
                     sort_keys=True))
    return prediction


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase", choices=("prepare", "predict"), required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--public-sha256")
    p.add_argument("--model-checkout", type=Path)
    p.add_argument("--model-python", default="python3.12")
    a = p.parse_args()
    if a.phase == "prepare":
        prepare(a.out)
    elif a.public_sha256 and a.model_checkout:
        predict(a.out, a.model_checkout, a.model_python, a.public_sha256)
    else:
        p.error("predict requires externally anchored --public-sha256 and --model-checkout")


if __name__ == "__main__":
    main()
