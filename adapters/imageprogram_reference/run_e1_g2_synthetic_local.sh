#!/usr/bin/env bash
# ART-1 E1 G2 synthetic-only local gate. NO original images, network or paid CI.
# Usage: bash adapters/imageprogram_reference/run_e1_g2_synthetic_local.sh
set -euo pipefail
arena_root="$(cd "$(dirname "$0")/../.." && pwd -P)"
model_root="$(cd "$arena_root/../ImageProgram" && pwd -P)"
model_branch="feat/art1-e1-live-p1-session-v1"
arena_branch="feat/art1-e1-causal-continuity-review-v0"
model_sha="6d8e6399a2b0a44d08054a08b71b4a68d4d9e374"

[[ "$(git -C "$model_root" rev-parse HEAD)" == "$model_sha" ]] || {
  echo "Wrong Model SHA. Check out the pinned Model PR #81 revision." >&2; exit 2;
}
[[ "$(git -C "$model_root" branch --show-current)" == "$model_branch" ]] || {
  echo "Wrong Model branch" >&2; exit 2;
}
[[ "$(git -C "$arena_root" branch --show-current)" == "$arena_branch" ]] || {
  echo "Wrong Arena branch" >&2; exit 2;
}
for folder in "$model_root" "$arena_root"; do
  [[ -z "$(git -C "$folder" status --porcelain --untracked-files=normal)" ]] || {
    echo "Dirty source checkout: $folder" >&2; exit 2;
  }
done
py="$model_root/.venv/bin/python"
ruff="$model_root/.venv/bin/ruff"
[[ -x "$py" && -x "$ruff" ]] || {
  echo "Run 'uv sync --locked --extra render' in ImageProgram first" >&2; exit 2;
}
mkdir -p "$arena_root/runs"
work="$(mktemp -d "$arena_root/runs/art1-e1-g2-synthetic-XXXXXXXX")"
exec > >(tee -a "$work/run.log") 2>&1
printf 'G2 MODEL_SHA=%s\n' "$(git -C "$model_root" rev-parse HEAD)"
printf 'G2 ARENA_SHA=%s\n' "$(git -C "$arena_root" rev-parse HEAD)"
printf 'G2 EVIDENCE_DIR=%s\n' "$work"
printf 'G2 PYTHON=%s\n' "$("$py" --version)"
printf 'G2 UV=%s\n' "$(uv --version)"
# Explicitly prevent @skipUnless from hiding a missing paired installation.
(
  cd "$arena_root"
  "$py" -c "from imageprogram.experiments.art1_feedback_session_v1 import run_feedback_session_v1; print('PAIRED_MODEL_IMPORT_OK')"
)
(
  cd "$model_root"
  uv run --locked python scripts/check.py
  uv run --locked ruff check .
)
(
  cd "$arena_root"
  "$ruff" check \
    adapters/imageprogram_reference/verified_e1_snapshot_v1.py \
    adapters/imageprogram_reference/score_feedback_e1_v1.py \
    adapters/imageprogram_reference/run_e1_synthetic_v1.py \
    adapters/imageprogram_reference/continuity_v0.py \
    adapters/imageprogram_reference/e1_review_v1.py \
    tests/test_verified_e1_snapshot_v1.py \
    tests/test_e1_paired_synthetic_v1.py \
    tests/test_continuity_v0.py \
    tests/test_e1_review_v1.py
  "$py" -m unittest discover -s tests -p 'test_*.py' -v 2>&1 | tee "$work/arena-full-tests.log"
  "$py" -m unittest discover -s tests -p 'test_verified_e1_snapshot_v1.py' -v 2>&1 | tee "$work/snapshot-tests.log"
  "$py" -m unittest discover -s tests -p 'test_score_feedback_e1_v1.py' -v 2>&1 | tee "$work/paired-score-tests.log"
  "$py" -m unittest discover -s tests -p 'test_e1_paired_synthetic_v1.py' -v 2>&1 | tee "$work/paired-g2-tests.log"
  "$py" -m unittest discover -s tests -p 'test_continuity_v0.py' -v 2>&1 | tee "$work/continuity-tests.log"
  "$py" -m unittest discover -s tests -p 'test_e1_review_v1.py' -v 2>&1 | tee "$work/review-v1-tests.log"
)
for logfile in "$work/paired-score-tests.log" "$work/paired-g2-tests.log" "$work/review-v1-tests.log"; do
  grep -Eq '^Ran [1-9][0-9]* tests? in ' "$logfile" || {
    echo "Paired test count missing: $logfile" >&2; exit 3;
  }
  if grep -Eq 'skipped=[1-9]|\.\.\. skipped|^SKIP' "$logfile"; then
    echo "Critical paired test skipped: $logfile" >&2; exit 3;
  fi
done
(
  cd "$arena_root"
  "$py" -m adapters.imageprogram_reference.run_e1_synthetic_v1 \
    --out "$work/experiment"
)
printf '\nG2_SYNTHETIC_GATE_COMPLETE_HUMAN_REVIEW_PENDING\n'
printf 'Synthetic evidence: %s\n' "$work/experiment/provenance.json"
printf 'Underdraw human review: %s\n' "$work/experiment/underdraw/review/index.html"

printf 'Causal review: %s\n' "$work/experiment/underdraw/review_e1_v1/index.html"
