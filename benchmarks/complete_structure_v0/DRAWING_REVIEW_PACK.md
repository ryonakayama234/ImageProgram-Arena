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

Then package the actual result on the Arena side:

```bash
cd ../ImageProgram-Arena
python -m adapters.imageprogram_reference.drawing_review \
  --session baseline ../ImageProgram/runs/a0-character/episode \
    ../ImageProgram/runs/a0-character/replay_report.json \
  --out runs/a0-first-review
```

Open `runs/a0-first-review/index.html` locally. It displays real **initial / intermediate / final** captured frames; `review.json` records source request, Body, seed, runtime versions, costs, replay attestation and SHA-256 digests. To compare an actual one-factor change, pass an additional `--session variant EPISODE REPLAY_JSON` for a distinct real ImageProgram run. **Do not present the same episode twice as an experiment.**

## Acceptance and security

- Verify all source **public** file hashes and manifest public/private list before any output is created.
- Block traversal, symlinks and non-public source paths; never copy a private checkpoint or hidden witness to the review pack.
- Require an ImageProgram `verified=true` replay report. This is a **source-side replay attestation**, *not* independent Arena physics replay. It is recorded with a digest, and should be checked against the version-pinned source run in a trusted execution context.
- Never label the scripted Character witness as learned construction, better ranking, or acquired Skill.
- Review Pack files are locally generated, not inserted into Git; store the reproducible source/command/decisions separately.
- Static HTML only. No server, API keys, paid services, or GPU.

## Tests

```bash
python -m unittest -v tests.test_drawing_review
```

Tests include success from a mock manifest and fail-closed tampering, replay failure, private exposure, symlink and duplicate names. Mock fixtures validate the consumer interface only; the **first real Character v0 episode** must still be generated and inspected before #13 is closed.
