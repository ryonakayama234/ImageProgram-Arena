#!/usr/bin/env bash
# ART-1 E1 local-only v1, paired Model/Arena branches, full gates before scoring.
# Example:
# bash adapters/imageprogram_reference/run_e1_v1_local.sh \
#   /private/artwork.png 12 20 140 180 local-source-family authorized-local 1.0
set -euo pipefail
if [[ $# -ne 8 ]]; then
  echo "Usage: $0 SOURCE.png X0 Y0 X1 Y1 SOURCE_FAMILY RIGHTS INITIAL_FRACTION" >&2
  exit 2
fi
source_image="$(realpath -s -- "$1")"
x0="$2"; y0="$3"; x1="$4"; y1="$5"
source_family="$6"; rights="$7"; initial_fraction="$8"
arena_root="$(cd "$(dirname "$0")/../.." && pwd -P)"
model_root="$(cd "$arena_root/../ImageProgram" && pwd -P)"
model_branch="feat/art1-e1-live-p1-session-v1"
model_sha="6d8e6399a2b0a44d08054a08b71b4a68d4d9e374"
arena_branch="feat/art1-e1-g2-paired-synthetic-v1"
[[ "$(git -C "$model_root" rev-parse HEAD)" == "$model_sha" ]] || {
  echo "ImageProgram must be pinned to tested Model PR #81 SHA" >&2; exit 2;
}
[[ -f "$model_root/scripts/art1_feedback_session_v1.py" ]] || {
  echo "Missing local ImageProgram E1 v1 branch" >&2; exit 2;
}
[[ "$(git -C "$model_root" branch --show-current)" == "$model_branch" ]] || {
  echo "ImageProgram must be checked out to $model_branch" >&2; exit 2;
}
[[ "$(git -C "$arena_root" branch --show-current)" == "$arena_branch" ]] || {
  echo "Arena must be checked out to $arena_branch" >&2; exit 2;
}
for folder in "$model_root" "$arena_root"; do
  [[ -z "$(git -C "$folder" status --porcelain --untracked-files=normal)" ]] || {
    echo "Refusing dirty source checkout: $folder" >&2; exit 2;
  }
done
python_exec="$model_root/.venv/bin/python"
[[ -x "$python_exec" ]] || {
  echo "Use uv sync --locked --extra render in ImageProgram first" >&2; exit 2;
}
(
  cd "$arena_root"
  "$python_exec" -c "from imageprogram.experiments.art1_feedback_session_v1 import run_feedback_session_v1; print('PAIRED_MODEL_IMPORT_OK')"
)
mkdir -p "$arena_root/runs"
work="$(mktemp -d "$arena_root/runs/art1-e1-v1-XXXXXXXX")"
exec > >(tee -a "$work/run.log") 2>&1
printf 'Model SHA %s\nArena SHA %s\nRun folder %s\n' \
  "$(git -C "$model_root" rev-parse HEAD)" \
  "$(git -C "$arena_root" rev-parse HEAD)" "$work"
(
  cd "$model_root"
  uv run python scripts/check.py
  uv run ruff check .
)
(
  cd "$arena_root"
  "$python_exec" -m unittest discover -s tests -p 'test_*.py' -v
)
cd "$arena_root"
"$python_exec" -m adapters.imageprogram_reference.source_artwork "$source_image" \
  --roi "$x0" "$y0" "$x1" "$y1" \
  --source-family "$source_family" --rights "$rights" \
  --out "$work/source_manifest.json"
"$python_exec" -m adapters.imageprogram_reference.public_reference_roi_v1 \
  --source "$source_image" --manifest "$work/source_manifest.json" \
  --out "$work/public_roi"
(
  cd "$model_root"
  uv run python scripts/art1_feedback_session_v1.py \
    --public-roi "$work/public_roi" --out "$work/sessions" \
    --initial-fraction "$initial_fraction"
)
"$python_exec" -m adapters.imageprogram_reference.score_feedback_e1_v1 \
  --public-roi "$work/public_roi" --sessions "$work/sessions" \
  --out "$work/arena_independent_score.json"
"$python_exec" "$arena_root/adapters/imageprogram_reference/drawing_review.py" \
  --session noop "$work/sessions/noop_episode" "$work/sessions/noop_replay.json" \
  --session feedback_off "$work/sessions/feedback_off_episode" "$work/sessions/feedback_off_replay.json" \
  --session feedback_on "$work/sessions/feedback_on_episode" "$work/sessions/feedback_on_replay.json" \
  --out "$work/review"
printf '\nAUTOMATED_E1_REPLAY_AND_SCORE_COMPLETE_HUMAN_REVIEW_PENDING\n'
printf 'Scoring: %s\nReview: %s\n' "$work/arena_independent_score.json" "$work/review/index.html"
