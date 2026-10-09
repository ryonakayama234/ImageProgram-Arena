#!/usr/bin/env bash
# Gate 0: genuine C2 pair -> freshly replayed Arena Review Pack, no fake images.
set -euo pipefail

arena_root="$(cd "$(dirname "$0")/../.." && pwd -P)"
if [[ $# -gt 0 ]]; then
  model_root="$(cd "$1" && pwd -P)"
else
  model_root="$(cd "$arena_root/../ImageProgram" && pwd -P)"
fi
[[ -f "$model_root/scripts/girl_hair_completion.py" ]] || { echo 'Missing ImageProgram sibling checkout' >&2; exit 2; }
[[ -f "$arena_root/adapters/imageprogram_reference/drawing_review.py" ]] || { echo 'Missing Arena Review Pack consumer' >&2; exit 2; }

# Do not silently benchmark modified working copies. No automatic git checkout/pull.
for root in "$arena_root" "$model_root"; do
  branch_name="$(git -C "$root" branch --show-current)"
  if [[ "$root" == "$model_root" && "$branch_name" != main ]]; then
    echo "ImageProgram must be on main: $root" >&2; exit 2
  fi
  if [[ "$root" == "$arena_root" && "$branch_name" != main && "$branch_name" != feat/art1-gate0-c2-a0-verified-run ]]; then
    echo "Arena must be on main or the Gate 0 review branch: $root" >&2; exit 2
  fi
  [[ -z "$(git -C "$root" status --porcelain --untracked-files=normal)" ]] || { echo "Working tree is dirty: $root" >&2; exit 2; }
done
arena_sha="$(git -C "$arena_root" rev-parse HEAD)"
model_sha="$(git -C "$model_root" rev-parse HEAD)"
mkdir -p "$arena_root/runs"
work="$(mktemp -d "$arena_root/runs/art1-gate0-XXXXXXXX")"
exec > >(tee -a "$work/run.log") 2>&1
printf 'Gate 0 directory: %s\nImageProgram: %s\nArena: %s\n' "$work" "$model_sha" "$arena_sha"

# Run source tests and Arena regression before any research claim.
cd "$model_root"
uv sync --locked --extra render
uv run python scripts/check.py
uv run ruff check .
(cd "$arena_root" && "$model_root/.venv/bin/python" -m unittest discover -s tests -p 'test_*.py' -v)

uv run python scripts/girl_hair_completion.py --out "$work/c2"
uv run python "$arena_root/adapters/imageprogram_reference/drawing_review.py" \
  --session analytic "$work/c2/private/analytic_episode" "$work/c2/private/analytic_replay.json" \
  --session manual "$work/c2/private/manual_episode" "$work/c2/private/manual_replay.json" \
  --out "$work/review"
python3 "$arena_root/adapters/imageprogram_reference/validate_gate0.py" \
  --c2 "$work/c2" --review "$work/review" \
  --model-sha "$model_sha" --arena-sha "$arena_sha" \
  --out "$work/gate0_report.json"
printf '\nAutomated checks completed. OPEN this local HTML and visually inspect BOTH drawings:\n%s\n' "$work/review/index.html"
printf 'Gate 0 is not fully PASS until human visual inspection is recorded.\n'
