# ART-1.0 実行計画 v0 — Real Reference Observe→Draw→Measure

**Status:** proposal / not yet implemented. 2026-10-09.
**Primary issue:** [Arena #16](https://github.com/ryonakayama234/ImageProgram-Arena/issues/16).
**Cross-repo issue:** [ImageProgram #63](https://github.com/ryonakayama234/ImageProgram/issues/63).
**Estimated effort:** 10–15 engineer-days (not a deadline; revise using actual run evidence).
**Scope:** local WSL2/Linux, CPU, no services or GPU dependency, real user image retained outside Git.

## 1. One testable milestone

A real locally supplied PNG/JPEG and a user-designated image ROI must become a versioned `restore_reference` task. ImageProgram must *observe only permitted reference information*, derive at least two distinct legal programs with identified scripted/analytic provenance, execute them through existing Skill→Hand→World (no raster blitting), re-observe actual canvas state, and use public evidence at least once to decide another legal stroke **or explicitly stop**. Arena must independently score and compare two distinct actual episodes, retain replay evidence and classify the failure. Completion **does not** mean learned painting skill or out-of-distribution generalization.

Acceptance has two separately reported layers:
1. **ART-1.0 baseline**: real reference→ROI→legal World program→replay→objective metrics and Review Pack.
2. **ART-1.0 feedback extension** (part of this proposed milestone): at least one additional observe→candidate/stop decision that causally depends on observed actual canvas rather than evaluator-private oracle or predetermined two-stroke script.

If feedback extension does not pass, report ART-1.0 baseline PASS / closed-loop FAIL, rather than silently redefining the milestone.

## 2. Existing assets, no forks

- ImageProgram P1 `experiments.runner.execute/replay`, `World.step/observe/pixels`, `construction.lowering.geometry_to_trace_calls`, `TracePolylineCall`, `regions`, protection preflight.
- ImageProgram C2 `experiments/girl_hair_completion`: independent same-checkpoint legal episode pair; this is analytic hand-scaffolded, not image perception.
- Arena A0 `adapters/imageprogram_reference/drawing_review.py`: verifies a fresh source replay and byte-checked public frames; does not independently simulate physics.
- Arena H5 branch isolation/public-private boundary and fixed evaluator principles; maintain H5a frozen benchmark untouched.
- Canonical schema owners are ImageProgram; Arena consumes versioned contracts and owns task/evaluator/orchestration/UI, never duplicates model logic.

## 3. Six gates: sequential acceptance, small PRs

### Gate 0 — Real A0×C2 integration proof (0.5–1.5 d)
1. Pin both `main` commit SHAs and environment version in evidence, without assuming historical successful runs apply to the current heads.
2. From sibling WSL2 checkouts: `uv sync --locked --extra render`; `uv run python scripts/check.py`; `uv run ruff check .`; `uv run python scripts/girl_hair_completion.py --out runs/<fresh-id>`.
3. Run `../ImageProgram-Arena/adapters/imageprogram_reference/drawing_review.py` from ImageProgram environment with two distinct C2 episodes and their replay attestation JSON.
4. Verify fresh replay, two different realized end states, safe JSON/PNG provenance, no protected new ink, HTML preview. Resolve failures in the smallest existing owning module before Gate 1.
**Evidence:** independent episode paths, replay verification, tests/Ruff, review.json and visual sign-off. The GitHub merge alone is insufficient.

### Gate 1 — Local source ingestion and ROI Task (2–3 d; Arena owning PR)
1. PNG/JPEG load through Pillow (no own decoder); bound bytes/pixels; EXIF orientation normalization, color/alpha conventions, source-byte SHA-256 + normalized-pixel SHA-256 and metadata. Never upload source or raw crops by default.
2. One **bbox** selected by local drag UI or deterministic CLI coordinates; canonical half-open pixel coordinates `[x0,x1) × [y0,y1)` on oriented image, explicit pixel-center→physical Body coordinates. Freeze y-axis convention in unit and visual tests.
3. Distinguish `editable`, `scored`, `protected` regions and `policy_visible` reference vs evaluator-private target; validate empty/out-of-bounds/overlap/inversion; keep annotation author/semantic/parent-source lineage.
4. Local `reference_task.json` and preview. Preserve source image only under user-local ignored `runs/` or chosen input directory. Synthetic fixtures (non-artist/copyrighted originals) only in Git.
**Gate:** round-trip pixel→Body m→pixel (within stated resolution tolerance), ROI hash tamper rejection, EXIF and malformed-image tests, public/private leak tests.

### Gate 2 — Real image→legal drawing Program (2–3 d; ImageProgram owning PR)
1. New *adapter* for `restore_reference` public ROI, not alteration of frozen P1/P2 schema. Input only public normalized image ROI + Body/Tool/Budget/Goal. If a canonical contract change is unavoidable, version it with ADR/schema/test.
2. Baseline `algorithmic_reference_baseline`: simple grayscale/edge candidate extraction → contour segment selection → deterministic polyline simplification → normalized Construction geometry → existing TracePolylineCall / legal Hand & World. Keep segmentation parameters/budget reproducible.
3. Generate at least two genuinely different proposals/parameterizations. Preflight margins accounting for tip width; tool/speed/motor/time budget, no erase/undo/blit, no hidden oracle/witness. No extra renderer primitive.
4. Execute separate actual episodes from exactly the same initial canvas and conditions; every action must be replayable and carry provenance `analytic`, not `learned`.
**Gate:** nonzero intentional ink; distinct verified final hashes; no illegal action/protection ink; reproducible output and honest unsupported cases (color fill/soft smudge).

### Gate 3 — Arena independent multi-metric evaluator (1–2 d; Arena PR)
Use only an evaluator-private view of the reference for scoring; do not expose its precomputed mask/score-derived action proposals to the painter. Version task/evaluator, record `tau`, rendering scale and masks *before* candidate comparison.

For target/reference boundary sets `E_r`, produced strokes boundary set `E_p` within scored ROI and a normalized tolerance `tau`:
- `precision = fraction of E_p within tau of E_r`; `recall = fraction of E_r within tau of E_p`; `boundary_F1 = 2PR/(P+R)`.
- `symmetric_mean_distance` between boundary sets as a secondary diagnostic; guard empty sets explicitly.
- optional foreground IoU **only** when foreground segmentation is meaningful, low-pass gray-value difference, physical stroke distance/count, motor/sim/wall cost and safety/protection.
- keep all metrics as a vector; not a fitted total 'beauty score'. Show source/composite overlay **locally only** by default.

Negatives: no-op, unlimited dense scribble, off-ROI strokes, exact source raster copied as result, forged ROI digest, evaluator-private witness leakage, frame/replay mismatch, duplicate episodes. For nonempty reference, no-op boundary_F1=0; tests must show no-op cannot win by mostly-white background; overscribbling cannot win just by recall.
**Gate:** fixed synthetic references with exact expected metrics and anti-cheat tests; all independent error/permission gates pass.

### Gate 4 — True re-observation and a constrained second decision (2–3 d; ImageProgram PR)
1. After an initial legal stroke/program, read **actual** `World.observe()/pixels()` through the permitted sensor. Distinguish image state from true subpixel occupancy/privileged checkpoint; policy never gets World private data.
2. Independently calculate public `reference vs current public canvas` residual features (not evaluator-private oracle); deterministically choose a legal follow-up contour candidate or `stop` under remaining budget.
3. Dry-ink cannot erase; suppress strokes predicted to corrupt correct regions. Re-observe after follow-up and record both predicted and measured effect plus improvement or deterioration.
4. Counterfactual test: two distinct legal public initial ink states with same reference, Body, candidate set, and budget must cause a justified different next action or stop. State-name/seed/IDs may not be used as hidden selector. Restore same checkpoint for each compared branch.
**Gate:** observable causal difference, logged actual actions and residual before/after, legal replay. A planned fixed second stroke without state evidence does NOT satisfy feedback.

### Gate 5 — Real reference E2E & limitation report (1.5–2.5 d; both PRs in ownership order)
1. Run at least one real, non-synthetic original reference ROI: choose an isolated monochrome geometric line motif first. Compare no-op diagnostic + two legal World-executed distinct candidates under same Body/budget.
2. Run an additional real ROI to document generalization limit/failure (e.g. red-hair silhouette where only contour is supported), not to claim statistical transfer.
3. Produce a local hash-bound Review Pack with reference/ROI/initial/intermediate/final/overlay if opted in, per-step transitions, objective metric vector, cost, provenance, failure taxonomy, stop reason, Replay/source digests.
4. Engineer-independent pass/fail audit, root-cause/actionable next issues. Re-run targeted + full regression + Ruff + fresh WSL2 run on final commits and record exact commands/SHAs.
**Milestone PASS:** all Gates 0–5, real legal drawing and feedback, private/public and protection violations 0, replay correct, at least one meaningful non-no-op improvement over blank in predeclared structure metric, negative tests pass. Otherwise record partial/FAIL with reproducible diagnosis, not a relabeled demo.

## 4. Privacy / epistemic boundaries

- Never commit real artist/user source images, hidden evaluator mask, private checkpoints, large episodes. Arena public repository must contain only code, synthetic fixtures, contracts, aggregate sanitized reports and reproduction guidance.
- Restrict raw reference display to local authorized user; mode=`restore_reference` exposes permitted reference crop to painter but mode=`complete_infer` must not. Do not use reference 'source program' as ground truth; finished images do not identify true drawing order.
- Keep evidence kind: `scripted/analytic/learned`; show `unsupported` rather than silently adding fill/smudge/color to dry ink.
- If labels/splits are added, source family and parent lineage—not crops/augmentations—define independent units. This pilot does not infer statistical significance or learned transfer.

## 5. Git ownership and change strategy

| Slice | Owning repo | Scope | Exit evidence |
|---|---|---|---|
| 0 | both (docs/evidence, code fix only if necessary) | cross-repo C2→A0 authentic E2E | 2 verified actual episodes + Review Pack |
| 1 | Arena | ingestion, ROI UI/CLI, local Task + isolated source | hash/coordinates/privacy tests |
| 2 | ImageProgram | reference-to-polyline proposer, motor/program execution | two real replayable episodes |
| 3 | Arena | scorer/negative controls/Review Pack compare | fixed evaluator tests |
| 4 | ImageProgram | observe/residual/next action-or-stop loop | paired state-dependent branch |
| 5 | both | real-image runs, evidence and limits | WSL2 commands, visual review, clear PASS/FAIL |

Small branch → PR → exact tests/CI → independent audit → merge; do not modify unrelated H5a baselines or frozen Character. New feature gates must not claim victory based on only mock/synthetic images; keep program/reviewer and evaluator separate. Gate 1 and Gate 2 interface may be specified in parallel, while acceptance stays gated.

## 6. Exit artifacts and the next experiment

Minimum run folder (names proposed, not existing CLI):
- `reference_task.json` (no original pixels), `reference_provenance.json` (local private)
- `<candidate>/episode/{frames, transitions, request, program, result}`, fresh `replay_report.json`
- `evaluation.json`, `review.json`, `index.html`, `limitations.json`, `decision_log.md`
- `run_environment.json`: both commit SHAs, software lock, task hash, Body/tool, seed, candidate/evaluator version, budget and commands.

ART-1.0 does **not** validate improvement through learning. **ART-2** will compare fixed vs revised Skill/Model on *held-out source families* under equal budgets, reporting reconstruction, transfer, action/search cost and regression with proper paired independent units. This is deliberately a separate research gate.
