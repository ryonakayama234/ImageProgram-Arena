#!/usr/bin/env bash
# Reproducible ART-1 smoke on a *synthetic*, locally generated open-curve image.
# This is a real P1/A0 pipeline smoke, not a real-art acceptance or Skill claim.
set -euo pipefail
if [[ $# -ne 0 ]]; then
  echo "Usage: bash adapters/imageprogram_reference/run_first_contact_smoke.sh" >&2
  exit 2
fi

arena_root="$(cd "$(dirname "$0")/../.." && pwd -P)"
model_root="$(cd "$arena_root/../ImageProgram" && pwd -P)"
python_exec="$model_root/.venv/bin/python"
[[ -x "$python_exec" ]] || {
  echo "ImageProgram render venv required: cd ../ImageProgram && uv sync --locked --extra render" >&2
  exit 2
}
mkdir -p "$arena_root/runs"
fixture_root="$(mktemp -d "$arena_root/runs/art1-smoke-fixture-XXXXXXXX")"
image_path="$fixture_root/synthetic-open-line.png"

# Match the source geometry already used by the real-World ImageProgram
# unit fixture, translated into the editable bbox [8, 8, 120, 120).
"$python_exec" - "$image_path" <<'PY'
import math
import sys
from PIL import Image, ImageDraw

im = Image.new("RGB", (128, 128), "white")
points = [
    (8 + 12 + int(t * 0.77), 8 + int(55 + 20 * math.sin(t / 18)))
    for t in range(105)
]
ImageDraw.Draw(im).line(points, fill="black", width=2)
im.save(sys.argv[1], format="PNG")
print("SYNTHETIC_ONLY_ARTWORK: " + sys.argv[1])
PY

# Use exactly the same full-suite, pinned-branch, actual-P1 and fresh-A0 path
# that real artwork will use later. The local source is never committed.
bash "$arena_root/adapters/imageprogram_reference/run_first_contact.sh" \
  "$image_path" 8 8 120 120 synthetic-smoke-v0 self-created-synthetic
