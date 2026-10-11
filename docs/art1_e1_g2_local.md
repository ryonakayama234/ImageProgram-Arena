# ART-1 E1 G2: local WSL2 test guide

## 1. Synthetic evaluation (no personal image required)

Keep both repositories as siblings. Neither Draft PR is merged.

```bash
cd ~/ImageProgram
git fetch origin
git switch feat/art1-e1-live-p1-session-v1
git pull --ff-only
git rev-parse HEAD  # must be 6d8e6399a2b0a44d08054a08b71b4a68d4d9e374
uv sync --locked --extra render

cd ~/ImageProgram-Arena
git fetch origin
git switch feat/art1-e1-g2-paired-synthetic-v1
git pull --ff-only
bash adapters/imageprogram_reference/run_e1_g2_synthetic_local.sh
```

The shell runs Model full unit tests+Ruff, Arena full suite, security
snapshot unit tests, paired tests **without skips**, then two generated-image
comparisons. It prints a per-run ignored `runs/art1-e1-g2-synthetic-*/`
directory. Look at:
- `run.log`, `paired-g2-tests.log`, `snapshot-tests.log`
- `experiment/provenance.json`
- `experiment/underdraw/arena_independent_score.json`
- `experiment/underdraw/review/index.html`
- `experiment/complete/arena_independent_score.json`
- 6 actual P1 Episodes under `experiment/*/sessions/*_episode/`

**Interpretation:** `SYNTHETIC_CASES_PASS` requires the underdraw case to
perform an observed correction and have `F1_on - F1_off > 0`; the complete
case must produce a typed Stop with no new correction. Every Episode must
pass the *ImageProgram* canonical source replay on Arena's private immutable
snapshot. Arena independently computes target/mask/F1, **not** physics.
Final G2 sign-off also requires checking the local tests/logs, failed/negative
cases, SHA and image/score review. This is not evidence of learned skills.

If tests report failures, report the failing SHA, test names and error stack
without changing the target, scoring tolerance or expected threshold after
seeing the score. Do not share private checkpoint data.

## 2. Your own PNG/JPEG drawing (you run this locally)

Only after the synthetic gate, choose a high-contrast **open curve or simple
single line** in your image. Dense filled regions, crossings and loops are
explicitly unsupported by the current reference-geometry baseline.
Provide an editable rectangular crop in **EXIF-transposed pixel coordinates**.
A 128 by 160 crop is known to be a compatible test fixture; other dimensions
may be legal but must satisfy v1 placement and pixel budgets. Example
coordinates below require the source image to extend beyond (140,180).

```bash
cd ~/ImageProgram-Arena
bash adapters/imageprogram_reference/run_e1_v1_local.sh \
  "/mnt/c/Users/YOUR_WINDOWS_LOGIN/Pictures/your-picture.png" \
  12 20 140 180 "local-image-001" "local-test" 0.55
```

The arguments are: `SOURCE.png X0 Y0 X1 Y1 SOURCE_FAMILY RIGHTS
INITIAL_FRACTION`. The `RIGHTS` field is management provenance; the
script does not independently authorize or publish the source image.

All source images and the management manifest stay under a local ignored
`runs/art1-e1-v1-*/` directory; the public Model task contains only
`reference_roi.png` and `task.json`. The run prints locations for
`arena_independent_score.json` and `review/index.html`.
Do **not** post the original image, raw local paths, user family identifiers,
private checkpoint files or any private run directory to GitHub.
If the geometry is unsupported or the scorer rejects the result, treat it
as a documented experimental FAIL/unsupported case, not a general-art PASS.

For a complete-line Stop diagnostic, repeat with initial fraction `1.0`.
The generic Review Pack can legitimately reject identical physical episodes
because it forbids duplicate evidence. That does **not** mean the typed Stop
or independent score is invalid; review the canonical Episodes and score,
and keep physical equivalence distinct from independent improvement.

## Constraints

- Model revision: `6d8e6399a2b0a44d08054a08b71b4a68d4d9e374` (#81).
- Arena: Draft #24 -> snapshot Draft #26 -> paired experiment Draft #27.
- Do not merge/auto-run paid Actions without explicit approval.
- Report `G2 PENDING` until user local receipts confirm full no-skip tests,
  negative controls and independent synthetic improvement.
