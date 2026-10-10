#!/usr/bin/env bash
# ART-1 First Contact: local artwork -> permitted ROI -> P1 episodes -> Arena scoring.
set -euo pipefail
if [[ $# -ne 7 ]]; then
  echo "Usage: $0 /absolute/path/to/source.png X0 Y0 X1 Y1 SOURCE_FAMILY RIGHTS" >&2
  exit 2
fi
source_image="$(realpath -s -- "$1")"
shift
x0="$1"; y0="$2"; x1="$3"; y1="$4"; source_family="$5"; rights="$6"
arena_root="$(cd "$(dirname "$0")/../.." && pwd -P)"
model_root="$(cd "$arena_root/../ImageProgram" && pwd -P)"
[[ -f "$model_root/scripts/first_contact.py" ]] || { echo 'Missing ImageProgram First Contact branch checkout' >&2; exit 2; }
[[ -f "$arena_root/adapters/imageprogram_reference/public_reference_roi.py" ]] || { echo 'Missing Arena source intake branch checkout' >&2; exit 2; }
for root in "$model_root" "$arena_root"; do
  [[ -z "$(git -C "$root" status --porcelain --untracked-files=normal)" ]] || {
    echo "Dirty working copy; refusing unpinned run: $root" >&2; exit 2;
  }
done
model_sha="$(git -C "$model_root" rev-parse HEAD)"
arena_sha="$(git -C "$arena_root" rev-parse HEAD)"
mkdir -p "$arena_root/runs"
work="$(mktemp -d "$arena_root/runs/art1-first-contact-XXXXXXXX")"
exec > >(tee -a "$work/run.log") 2>&1
printf 'ART-1 First Contact run directory: %s\nImageProgram: %s\nArena: %s\n' "$work" "$model_sha" "$arena_sha"
python_exec="$model_root/.venv/bin/python"
[[ -x "$python_exec" ]] || { echo 'Missing ImageProgram .venv; run uv sync --locked --extra render in ImageProgram' >&2; exit 2; }
(
  cd "$model_root"
  uv run python -m unittest discover -s tests -p 'test_reference_geometry_v0.py' -v
  uv run python -m unittest discover -s tests -p 'test_first_contact_v0.py' -v
  uv run ruff check src/imageprogram/experiments/reference_geometry_v0.py \
    src/imageprogram/experiments/first_contact_v0.py scripts/first_contact.py \
    tests/test_reference_geometry_v0.py tests/test_first_contact_v0.py
)
(cd "$arena_root" && "$python_exec" -m unittest discover -s tests -p 'test_public_reference_roi.py' -v)
cd "$arena_root"
"$python_exec" -m adapters.imageprogram_reference.source_artwork "$source_image" \
  --roi "$x0" "$y0" "$x1" "$y1" --source-family "$source_family" \
  --rights "$rights" --out "$work/source_manifest.json"
"$python_exec" -m adapters.imageprogram_reference.public_reference_roi \
  --source "$source_image" --manifest "$work/source_manifest.json" \
  --out "$work/public_roi"
(cd "$model_root" && uv run python scripts/first_contact.py \
    --public-roi "$work/public_roi" --out "$work/episodes")
"$python_exec" -m adapters.imageprogram_reference.score_first_contact \
  --public-roi "$work/public_roi" --episodes "$work/episodes" \
  --out "$work/arena_scoring.json"
"$python_exec" "$arena_root/adapters/imageprogram_reference/drawing_review.py" \
  --session fine "$work/episodes/fine_episode" "$work/episodes/fine_replay.json" \
  --session coarse "$work/episodes/coarse_episode" "$work/episodes/coarse_replay.json" \
  --session noop "$work/episodes/noop_episode" "$work/episodes/noop_replay.json" \
  --out "$work/review"
printf '\nOpen the real drawing review: %s\n' "$work/review/index.html"
printf 'Independent Arena metrics: %s\n' "$work/arena_scoring.json"
printf 'AUTOMATED_E2E_COMPLETE_VISUAL_REVIEW_PENDING (not learned Skill)\n'
