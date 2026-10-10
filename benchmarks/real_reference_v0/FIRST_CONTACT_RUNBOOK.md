# ART-1 First Contact — real reference to legal Motor Episode

**Status: experimental code on stacked Draft PRs. This is not evidence of learned Skill or of real-art task completion.** Raw artworks, local ROI crops, source-family provenance and private checkpoints stay only in local ignored runs/.

## Target

Choose a self-controlled PNG/JPEG high-contrast black open curve on a light background, for example **one isolated hair strand**. For this first pilot the curve must be inside the ROI with margin, not intersect another line, not be a loop, and not be a large filled region. ROI width/height must be 12..256 px, max 65,536 px total. Dense, textured, colored, branched and cycle paths will fail explicitly; do not quietly claim support.

## Branches

- ImageProgram branch: feat/art1-first-contact-motor-v0 (new implementation)
- Arena branch: feat/art1-first-contact-e2e-v0, stacked on feat/art1-local-source-roi-ingest-v0 (Arena PR #19)
- Have clean sibling checkouts ~/src/ImageProgram and ~/src/ImageProgram-Arena
- Install ImageProgram environment: cd ~/src/ImageProgram && uv sync --locked --extra render

From Arena checkout:

    bash adapters/imageprogram_reference/run_first_contact.sh \
      /absolute/path/to/local/line-art.png 30 40 150 160 source-A local-study-only

Example only: replace file/coordinates with **your own** normalized post-EXIF source image size and ROI. Half-open bounding box x0 y0 x1 y1; choose a patch containing one line, no touching ROI boundary. Do not commit the source, ROI export, private episodes or logs.

## What runs

1. Arena SourceArtwork management intake validates bytes, EXIF normalization, source metadata, rights label, ROI integrity.
2. Arena checks the same source again and exports exactly a **permitted L8 ROI** and a minimal policy task; private source file path, family, rights and hidden target are not forwarded. This is explicitly a reference-visible task (restore_reference), NOT blind completion.
3. ImageProgram's deterministic threshold + thinning extracts a supported open-line skeleton. RDP fine and coarse curves become actual existing P2 TracePolylineCalls, lowered to P1 World Motor.
4. Preflight checks real swept-ink protection for the complementary area outside the editable ROI. Three independent real World episodes start from the same blank state: fine, coarse, noop.
5. Real P1 source replay and Arena's independent geometric tolerance-2px F1 plus actual ink-outside-ROI/command counts. Arena Review Pack freshly calls source replay on all three episodes. Human review remains necessary.

## Artifacts

Only local ignored directory runs/art1-first-contact-* containing run.log, private source_manifest.json, public_roi, episodes, arena_scoring.json and review/index.html. The no-op expected F1 is zero. If scoring/preflight/World/replay fails, retain failure for research diagnostics instead of asserting success.

## Claims

This pilot ONLY probes isolated permitted artwork → deterministic Program proposals → real World legal drawing. Learned Eye, Learned Skill, general hair understanding, true historical author pen order, color/erase support, visual beauty, and cross-artwork transfer are **not** established.

## Next gate

Record first successful WSL2 local run and inspect the actual two line drawings. If source succeeds, ART-2 can begin finding reusable cross-task parameters and evaluate on source-family-disjoint held-outs.

Related: ImageProgram #63, Arena #16, ImageProgram #64.
