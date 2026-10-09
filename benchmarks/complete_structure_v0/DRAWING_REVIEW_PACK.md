# A0 / Drawing Session Review Pack v0

Arena is a **read-only consumer** of ImageProgram's real deterministic episode frames. It does not synthesize drawing operations, own the Model, modify the painter, or infer autonomous skill.

## First real drawing (WSL2 / Linux)

Use the two repositories as sibling checkouts. Install and execute the already existing hand-authored Character v0 witness:

```bash
cd ../ImageProgram
uv sync --locked --extra render
uv run python scripts/character_witness.py --out runs/a0-character
```

This ImageProgram script writes a real stroke-by-stroke P1 episode with initial and intermediate PNG frames, a final drawing, private checkpoints and an independently executed ImageProgram replay report.

Then package the actual result. **Use the ImageProgram Python environment**:
the Arena exporter imports the existing ImageProgram runner and performs a
**fresh deterministic source replay of the selected episode** rather than
trusting an external JSON replay flag alone.

```bash
# Stay in the ../ImageProgram checkout after the character witness run.
uv run python ../ImageProgram-Arena/adapters/imageprogram_reference/drawing_review.py \
  --session baseline runs/a0-character/episode \
    runs/a0-character/replay_report.json \
  --out ../ImageProgram-Arena/runs/a0-first-review
```

Open `runs/a0-first-review/index.html` locally. It displays real **initial / intermediate / final** captured frames; `review.json` records source request, Body, seed, runtime versions, costs, replay attestation and SHA-256 digests. To compare an actual one-factor change, pass an additional `--session variant EPISODE REPLAY_JSON` for a distinct real ImageProgram run. **Do not present the same episode twice as an experiment.**

## Acceptance and security

- Verify all source **public** file hashes and manifest public/private list before any output is created.
- Block traversal, noncanonical path aliases, symbolic links and multiply linked public input files (including private hard links); never copy a private checkpoint or hidden witness to the review pack.
- Before interpreting provenance metadata, **read request/result/program/transition data through no-follow directory/file descriptors**, size-bound them, verify their bytes against the manifest, and compute semantic identities from precisely those verified snapshots. Never reopen unchecked JSON metadata by pathname after the initial verification.
- After potentially long source replay, **re-open every PNG through no-follow directory/file descriptors**, reject non-regular/multiply-linked files, and verify the actual snapshotted bytes against the earlier manifest digest **before writing them** to the public Review Pack. Limits are 64 MiB per image, 4 MiB per metadata artifact and 128 MiB for ordered transitions. Reject oversized files via `fstat` before bulk reads, and bound the read if the file grows concurrently. This closes the post-replay path-swap TOCTOU leak; path validation alone is not a safe copy primitive.
- Require an ImageProgram `verified=true` replay report **and independently invoke the installed ImageProgram `replay(episode)` on the selected episode**. This reconstructs the recorded request/program and checks the frames/transitions with the source's pinned implementation. This is not a separately implemented Arena physics engine. A report from another episode cannot substitute for direct source replay.
- Never label the scripted Character witness as learned construction, better ranking, or acquired Skill.
- Review Pack files are locally generated, not inserted into Git; store the reproducible source/command/decisions separately.
- Static HTML only. No server, API keys, paid services, or GPU.

## Tests

This Review Pack consumer is **only on Draft PR #14**, not on `main`.
Run from the Arena repository root; fetch its feature branch before testing.

```bash
cd ~/src/ImageProgram-Arena
git status --short                         # Check local changes before switching
git fetch origin
git switch feat/a0-drawing-review-pack-v0 || git switch --track origin/feat/a0-drawing-review-pack-v0
git pull --ff-only origin feat/a0-drawing-review-pack-v0
git branch --show-current
test -f tests/test_drawing_review.py

python3 -m unittest discover -s tests -p 'test_drawing_review.py' -v
```

Using `unittest discover` avoids confusion between module-name imports and
test path discovery. On `main`, `tests/test_drawing_review.py` does **not exist**;
the resulting `ModuleNotFoundError` is not a failing review-pack test.
Never interpret existing older tests passing as validating PR #14.

Tests include success from a mock manifest and fail-closed tampering, replay failure, private exposure, symlink and duplicate names. Adversarial tests also mutate an image or its parent directory after replay / just before descriptor open, and ensure nothing from the private tree is exported. Mock fixtures validate the consumer interface only; the **first real Character v0 episode** must still be generated and inspected before #13 is closed.

## WSL2 Pilot Evidence and Follow-up (2026-10-09)

A real Linux/WSL2 Arena checkout on feature PR #14 ran
`python3 -m unittest discover -s tests -p 'test_drawing_review.py' -v`:
**24 tests passed (0.202 s), including post-replay symlink, parent swap,
frame digest tamper and fd-open race**. These were tests before the next Codex
review; they confirm the earlier mitigation path but are not a cross-repository
P1 source replay.

Subsequent Codex review found **two more P1 concerns**: unchecked provenance
JSON metadata after validation and whole-file hashing before a size limit.
The consumer has been amended to use bounded, no-follow, digest-verified
snapshots for all publication inputs, with four additional negative regressions.
**The new (28-case) suite has not yet been executed on WSL2.** Re-run the test
command above on the latest branch, and separately validate a real C2 Episode
pair in the installed ImageProgram environment before declaring Gate 1 complete.
