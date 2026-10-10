# ART-1 First Contact — real reference to legal Motor Episode

**Status: experimental code on stacked Draft PRs. This is not evidence of learned Skill or of real-art task completion.** Raw artworks, local ROI crops, source-family provenance and private checkpoints stay only in local ignored runs/.

## Target — real character-first; synthetic only for debugging

The **first user-facing artwork experiment must use an authorized real character illustration**, not a succession of arbitrary synthetic marks. Select an artistically meaningful ROI (e.g. a bang/forelock silhouette, hair tip near face, eyelid/face contour) and retain a local-only overview/context thumbnail with the selected ROI; human selection of a coarse ROI is permitted, but supplying the exact contour or author stroke order as hidden ground truth to the Painter is not.

The **current v0 algorithm remains limited** to an isolated high-contrast dark open curve within a cropped ROI, with margins, no intersections, loops or large fill. ROI width/height is 12..256 px (max 65,536 px total). For a real character crop with intersections, shading, or dense hair, record a structured **unsupported/perception/representation failure on that meaningful source** rather than switching the artistic goal to endless arbitrary synthetic squiggles or claiming success. The separate synthetic smoke is only an engineering diagnostic, not an artwork milestone.

## Eye-first next implementation slice (NOT YET IMPLEMENTED)

This Draft currently executes **one-shot** reference ROI -> geometry -> fixed Motor candidates -> terminal Arena scoring. It **does not** yet route real art through ImageProgram's P2 `ObservationBroker`, query-conditioned `Percept` / `QueryEngine`, `BeliefState`, or post-stroke feedback. Thus it must not claim genuine closed-loop Eye or learned vision.

The next ImageProgram-owned implementation must keep the actual visual task and expose one observation-driven correction loop:
1. Acquire an allowed **reference observation** for `restore_reference`; record source/observation identity, spatial ROI, Eye query(s), measured/unknown Percepts and provenance, without giving evaluator-private witness, raw full artwork or known author action history to the Painter.
2. Acquire the **real World canvas observation** through the existing `ObservationBroker` / `QueryEngine` and generate a bounded legal Motor proposal. Keep target-versus-current comparison and any construction hypotheses explicitly typed as inferred, not historical stroke truth.
3. Execute initial legal Motor actions via P1, then **reacquire a fresh World frame**, remeasure relevant percepts and construct a new Belief. Replan **at most one** additional safe ink-only correction from the new observation; fail explicitly if the only correction would require erase/color/unsupported media.
4. Compare a **frozen one-shot** baseline with feedback enabled/disabled on the *same source ROI and budgets*, logging quality delta, additional query/observation/Motor costs, actual replay, protected-ink zero, and no-op. Observation-dependent choice must be auditable (not simply post-hoc scoring). For a first pilot, deterministic measured Percepts are acceptable as *instrumentation*, but do **not** call them a learned Eye or autonomous Skill.

The independent Arena evaluator remains the sole owner of final 2px F1 and failure diagnostics. Later learned query/representation experiments belong to ImageProgram #55. Real-world full observation-based iteration is a new capability and is not passed by the existing smoke script.

## Branches

- ImageProgram branch: feat/art1-first-contact-motor-v0 (new implementation)
- Arena branch: feat/art1-first-contact-e2e-v0, stacked on feat/art1-local-source-roi-ingest-v0 (Arena PR #19)
- Have clean sibling checkouts ~/src/ImageProgram and ~/src/ImageProgram-Arena. The draft runner **checks exact branch names** and records both commit SHAs. It never fetches, checks out, or resets the repositories.
- Install ImageProgram environment: cd ~/src/ImageProgram && uv sync --locked --extra render
- The runner executes **full ImageProgram checks and Ruff**, then **all Arena unittest tests** before processing artwork. These updated heads are not yet WSL2-tested.

From Arena checkout:

    bash adapters/imageprogram_reference/run_first_contact.sh \
      /absolute/path/to/local/line-art.png 30 40 150 160 source-A local-study-only

Example only: replace file/coordinates with **your own** normalized post-EXIF source image size and ROI. Half-open bounding box x0 y0 x1 y1; choose a patch containing one line, no touching ROI boundary. Do not commit the source, ROI export, private episodes or logs.

## Before user artwork arrives: synthetic pipeline smoke

The repository now contains a deterministic **synthetic-only** input generator. On clean paired WSL2 branch checkouts with the render environment installed, run from the Arena checkout:

```bash
bash adapters/imageprogram_reference/run_first_contact_smoke.sh
```

It creates a high-contrast, open sinusoidal line as a local ignored `runs/art1-smoke-fixture-*/synthetic-open-line.png`, then invokes the **same** full-suite ART-1 pipeline as a real source (not a mock scorer). Expected evidence *if it passes*: three actual P1 Episodes (fine/coarse/noop), fresh source replay, independent Arena metrics, and A0 Review Pack. Inspect the printed `review/index.html`. The runner's stdout and files are local; a committed script is **not** execution evidence. The new smoke runner and current heads have not yet passed WSL2 checks.

## Optional local `/Image` inbox

User-provided references may be kept in either `/Image/` (an absolute WSL2 filesystem directory **outside** both Git checkouts) or a checkout-root `Image/` directory. Both Git checkouts now ignore root `Image/` to prevent accidental commits. Do not push files, crops, generated Review Packs, or raw provenance to GitHub. A folder's presence does not make its contents remotely accessible to ChatGPT or GitHub; actual ingestion runs in the local WSL2 process.

Choose one image **explicitly**, record rights and a source-family identifier, and select a half-open pixel bbox containing one isolated dark *open* line with a few pixels of white margin. The filename is illustrative; the bbox must be adjusted for the actual source **after EXIF normalization**.

```bash
cd ~/src/ImageProgram-Arena
bash adapters/imageprogram_reference/run_first_contact.sh \
  /Image/your-permitted-source.png 30 40 150 160 source-family-A local-study-only
```

Allowed source types: PNG/JPEG, at most 16 MiB and 16,777,216 decoded pixels. The editable ROI must be 12–256 pixels wide and high, with area <=65,536 pixels. These are capability bounds, not an assertion that arbitrary artwork will reconstruct. `/Image/` at filesystem root may require local permissions; no directory is automatically created or synced by these scripts.

## What runs

1. Arena SourceArtwork management intake validates bytes, EXIF normalization, source metadata, rights label, ROI integrity. The ROI exporter rechecks a bounded immutable byte snapshot against the recorded SHA-256, then decodes and crops **that same snapshot**, not a re-opened unchecked pathname.
2. Arena checks the same source again and exports exactly a **permitted L8 ROI** and a minimal policy task; private source file path, family, rights and hidden target are not forwarded. This is explicitly a reference-visible task (restore_reference), NOT blind completion.
3. ImageProgram's deterministic threshold + thinning extracts a supported open-line skeleton. RDP fine and coarse curves become actual existing P2 TracePolylineCalls, lowered to P1 World Motor.
4. Preflight checks real swept-ink protection for the complementary area outside the editable ROI. Three independent real World episodes start from the same blank state: fine, coarse, noop. The noop uses **two legal wait actions** (zero ink) because the A0 Review Pack requires at least two accepted actions to show an intermediate frame.
5. Real P1 source replay and Arena's independent geometric tolerance-2px F1 plus actual ink-outside-ROI/command counts. Arena Review Pack freshly calls source replay on all three episodes. Human review remains necessary.

## Artifacts

Only local ignored directory runs/art1-first-contact-* containing run.log, private source_manifest.json, public_roi, episodes, arena_scoring.json and review/index.html. The no-op expected F1 is zero. If scoring/preflight/World/replay fails, retain failure for research diagnostics instead of asserting success.

## Claims

This pilot ONLY probes isolated permitted artwork → deterministic Program proposals → real World legal drawing. Learned Eye, Learned Skill, general hair understanding, true historical author pen order, color/erase support, visual beauty, and cross-artwork transfer are **not** established.

## Next gate

Record first successful WSL2 local run and inspect the actual two line drawings. Log both exact head SHAs, regression test totals, actual replay status, fine/coarse/noop scores, Motor costs, ink outside E, human visual verdict, and unsupported/failure reasons. Keep raw sources, crops and private episodes in ignored runs/ only. **Fresh WSL2 First Contact E2E and human image review are still pending** on these draft heads. If source succeeds, ART-2 can begin finding reusable cross-task parameters and evaluate on source-family-disjoint held-outs.

Related: ImageProgram #63, Arena #16, ImageProgram #64.
