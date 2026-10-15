#!/usr/bin/env bash
# CC-02-V2: paired full-checkout verification and PUBLIC-only prediction.
# User supplies TWO exact 40-character PR branch HEADs. NO held-out scoring.
# No CI or cloud GPU is launched. Run from WSL2 with git/uv access.
set -Eeuo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: bash scripts/cc02_v2_reproduce.sh MODEL_40_SHA ARENA_40_SHA /absolute/evidence-root" >&2
  exit 64
fi
MODEL_SHA="$1"
ARENA_SHA="$2"
ROOT="$3"
for sha in "$MODEL_SHA" "$ARENA_SHA"; do
  if [[ ! "$sha" =~ ^[a-f0-9]{40}$ ]]; then
    echo "Both sources must be immutable 40-char Git commits" >&2
    exit 64
  fi
done
if [[ "$ROOT" != /* ]] || [[ -e "$ROOT" ]]; then
  echo "Evidence root must be a NEW absolute path (never overwrite)" >&2
  exit 64
fi
for command in git uv; do
  if ! command -v "$command" >/dev/null; then
    echo "Missing: $command" >&2
    exit 69
  fi
done
if ! PY312="$(uv python find 3.12)"; then
  echo 'Install project Python with: uv python install 3.12' >&2
  exit 69
fi
if [[ ! -x "$PY312" ]]; then
  echo "uv Python path not executable: $PY312" >&2
  exit 69
fi
mkdir -m 700 -p "$ROOT"
ROOT="$(realpath "$ROOT")"
exec > >(tee "$ROOT/terminal.log") 2>&1
printf 'MODEL_SHA=%s\nARENA_SHA=%s\n' "$MODEL_SHA" "$ARENA_SHA" |
  tee "$ROOT/checked-input-shas.txt"
echo 'Cloning PRIVATE Model; if denied, use: gh auth login && gh auth setup-git'
git clone https://github.com/ryonakayama234/ImageProgram.git "$ROOT/Model"
git clone https://github.com/ryonakayama234/ImageProgram-Arena.git "$ROOT/Arena"
git clone https://github.com/ryonakayama234/ImageProgram.git "$ROOT/LegacyModel"
git -C "$ROOT/Model" checkout --detach "$MODEL_SHA"
git -C "$ROOT/Arena" checkout --detach "$ARENA_SHA"
git -C "$ROOT/LegacyModel" checkout --detach 6d8e6399a2b0a44d08054a08b71b4a68d4d9e374
test "$(git -C "$ROOT/Model" rev-parse HEAD)" = "$MODEL_SHA"
test "$(git -C "$ROOT/Arena" rev-parse HEAD)" = "$ARENA_SHA"
printf 'Python: '; "$PY312" --version
printf 'uv: '; uv --version

cd "$ROOT/Model"
uv sync --locked --python "$PY312" --extra render
uv run --no-sync python scripts/check.py
uv run --no-sync ruff check .
uv run --no-sync imageprogram doctor
PYTHON="$ROOT/Model/.venv/bin/python"
# scripts/check.py already executes the full Model test suite.
printf 'Frozen Model package in: '
"$PYTHON" -c 'import imageprogram; print(imageprogram.__file__)'

cd "$ROOT/LegacyModel"
uv sync --locked --python "$PY312" --extra render
cd "$ROOT/Arena"
PYTHONPATH="$ROOT/Arena" "$PYTHON" scripts/cc02_test_matrix.py \
  --legacy-model-root "$ROOT/LegacyModel" --out "$ROOT/arena-test-matrix"
"$ROOT/Model/.venv/bin/ruff" check \
  adapters/imageprogram_reference/cc02_arc_review.py \
  adapters/imageprogram_reference/cc02_v2_ledger.py \
  tests/test_cc02_arc_review.py tests/test_cc02_v2_ledger.py \
  scripts/cc02_test_matrix.py

# This is the FIRST process. The model only receives public image/ROI/anchor.
PYTHONPATH="$ROOT/Arena" "$PYTHON" -m adapters.imageprogram_reference.cc02_v2_ledger \
  --predict --out "$ROOT/pre_review_receipts.json"
"$PYTHON" - "$ROOT/pre_review_receipts.json" > "$ROOT/receipt-sha256.txt" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
print(p["receipt_sha256"])
PY
chmod 400 "$ROOT/pre_review_receipts.json" "$ROOT/receipt-sha256.txt"
printf '\nSTOP: phase PREDICT finished; phase GRADE deliberately NOT RUN.\n'
printf 'Commit/publicly timestamp the digest in %s before private grading.\n' "$ROOT/receipt-sha256.txt"
printf 'After separately anchoring digest, execute:\n'
printf '  cd %q && PYTHONPATH=%q %q -m adapters.imageprogram_reference.cc02_v2_ledger --grade --receipts %q --receipt-sha "$(cat %q)" --out %q\n' \
  "$ROOT/Arena" "$ROOT/Arena" "$PYTHON" "$ROOT/pre_review_receipts.json" \
  "$ROOT/receipt-sha256.txt" "$ROOT/private_development_grade.json"
