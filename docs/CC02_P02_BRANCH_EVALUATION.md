# CC-02-P02 Arena — source-derived branch technical screen
Date: 2026-10-16 JST | Status: **draft / local study-shim only; independent semantic gate OPEN**

## Contract and safeguards
This research-only Arena screen evaluates a candidate bank of observed arm segments at T/Y/X junctions. Model receives PUBLIC `pixels_l8`, `focus_box`, and budgets only. The private technical target and excluded stroke **indices are in a distinct GRADE-only module** (`branch_contour_p02_private.py`); their source masks are regenerated only in GRADE. The public `CASES` tuples contain geometry only (two fields, with no semantic labels). Existing 6 hard development pairs and 3 controls are consumed from the unchanged `contextual_contour_cc02_tasks.py`. An additional 12 explicitly source-authored technical cases are fixed in `branch_contour_p02_trial.py`, in this order: t-right, t-left, y-up, y-down, x-one, x-two, parallel, near-miss, corner, thick-t, t-distractor, junction-grid.

Original sealed confirmation six pairs are **NEVER IMPORTED / NEVER SCORED** by this script. GRADE requires SHA256 of canonical PREDICT output that must be recorded outside the grading process. The executable checks the receipt hash, schema version, Arena trial source-file hash and public case/input hashes. The GRADE-only label file is versioned in Git history but no prospective external source-hash freeze has yet been executed. PREDICT records code file SHA256 for P02, frozen CC01/v2 and Arena trial, plus fixed candidate budgets. This does not establish author-independent or blinded ground truth; procedural masks come from the same fixture author.

## System
~~~mermaid
flowchart LR
 A["Unchanged Arena DEV 12 + controls 3"] --> U["PUBLIC-only input generator"]
 B["12 separate synthetic technical cases"] --> U
 U --> P["External Model P02; baseline P0+R0 receipt"]
 P --> SHA["Immutable PREDICT JSON + SHA256"]
 SHA --> E["Independent-process source-mask GRADE"]
 T["Arena-private target + excluded source strokes"] --> E
 E --> OUT["Full 27-row coverage/contamination/cost review"]
~~~

## ER / versions
~~~mermaid
erDiagram
 CASE_MANIFEST ||--o{ PUBLIC_CASE : specifies
 CASE_MANIFEST ||--o{ PRIVATE_SOURCE_MASK : source_annotation
 PUBLIC_CASE ||--|| MODEL_PREDICTION : public_only
 MODEL_PREDICTION ||--o{ ARM_SUPPORT : contains
 MODEL_PREDICTION ||--|| SHA_RECEIPT : anchored
 SHA_RECEIPT ||--o{ STAGE_GRADE : authorizes
 PRIVATE_SOURCE_MASK ||--o{ STAGE_GRADE : grades_after
~~~
- Input: `raster_sha256`, `case_id`, `family`, `focus_box`, `anchor_px` (never private target)
- Output: `arm.support_xy` (core pixels only), `junction_xy` (shared, **not** credited as uniquely assigned), `ownership=unknown`, `status`, `junction_pixels`, `work`, `evidence_sha256`
- GRADE: source-pixel target core recall (union and best single arm), excluded core pixel count, actual arm count, status, cost. This is not stroke quality nor selected-edge accuracy.

## Exploratory local-shim results, not official GitHub checkout
Local technical unit tests Model 6/6, Arena 3/3; `compileall` PASS, Ruff **NOT RUN** (executable absent). The Model's CC01 source and Arena original DEV generator were reimplemented in local shims for executable smoke; therefore no true cross-repo historical P0 graph/decision hash preservation or full suite is claimed.

The **pre-grade** 27-row receipt was anchored at [ImageProgram #100 SHA comment](https://github.com/ryonakayama234/ImageProgram/issues/100#issuecomment-6213307852): `a9e06e22a08a4b43a3c5a0788464b9cab6c675224a24923a5cf28212e2a6a7f4`. Grading was then executed in a separate local process with this `--expected-sha256`; this early local receipt does **not** contain the later source-fingerprint fields and is not a production-source record.

### DEV positive results (P02-only arm cores; not a combined baseline comparison)
| Pair index | P02 arms | Procedural target mask covered by arm-core union |
|---|---:|---:|
| 0 slanted | 0 | 0 / 10 |
| 1 T junction | 3 | 20 / 21 |
| 2 curved | 0 | 0 / 11 |
| 3 faint | 0 | 0 / 11 |
| 4 parallel neighbor | 0 | 0 / 11 |
| 5 Y branch | 4 | 16 / 17 |

**Interpretation:** P02 is intentionally additive; isolated nonbranch candidates remain in frozen P0, and faint strokes in P01 (separate Draft). **Do not interpret P02-only nonjunction zeros as a drop in baseline ability or sum the P0 3/6 and P02 2/6 into a verified 5/6.** The original DEV target regions are source-derived bounding-region proxy (known limitation), not independent path labels.

### New synthetic technical cases (P02-only local source-mask screen)
| Case | Arms | Union core recall | Excluded core pixels | Status |
|---|---:|---:|---:|---|
| t-right | 3 | 27/28 | 14 | ok |
| t-left | 3 | 27/28 | 14 | ok |
| y-up | 3 | 28/30 | 14 | ok |
| y-down | 3 | 15/16 | 15 | ok |
| x-one | 4 | 28/30 | 28 | ok |
| x-two | 4 | 27/29 | 30 | ok |
| parallel | 0 | 0/32 | 0 | ok: no junction |
| near-miss | 0 | 0/15 | 0 | ok: no junction |
| corner | 0 | 0/14 | 0 | ok: no junction |
| thick-t | 0 | 0/30 | 0 | junction-budget-exceeded |
| t-distractor | 3 | 28/29 | 0 | ok |
| junction-grid | 0 | 0/34 | 0 | arm-budget-exceeded |

Excluded physical ink **is** deliberately retained as unknown hypotheses when it touches junctions. The excluded-core counts expose ambiguity, not a performed false join. "No confident invalid connection" is trivial in this intervention because G/R and Motor do not consume these arms. Two explicit budget failures are part of the denominator, not favorable exclusions. Above measurements are diagnostic from the standalone study environment, not confirmation.

## Decision, unfinished work and reproduction
**SELECT:** Retain P02 code as a separable Draft and proceed to exact pinned Model+Arena source checkout and full test matrix. Independent blinded semantic annotations #99 are still OPEN. **DO NOT CLAIM:** 5/6 combined candidate pass, false-join=0 in executed drawing, any new correct selected path, neural perception, real-art transfer or artistic quality.

**Next verification:** Execute unchanged original generator with actual paired branch heads; run full repository suites and Ruff with declared interpreters; externally anchor the new source-fingerprinted PREDICT and grade separately; compare P0 vs baseline+P02 candidate adequacy and cost on the same public inputs. Original confirmation stays untouched.

~~~bash
# Run from ImageProgram-Arena clone (sibling ImageProgram clone is required).
export PYTHONPATH="../ImageProgram/src:."
python -m adapters.imageprogram_reference.branch_contour_p02_trial --predict --out /tmp/cc02_p02_predict.json
# Persist the printed canonical SHA outside the grading process, then:
python -m adapters.imageprogram_reference.branch_contour_p02_trial \
  --grade --receipt /tmp/cc02_p02_predict.json \
  --expected-sha256 '<anchored-before-grade-sha256>' \
  --out /tmp/cc02_p02_grade.json
~~~

The standalone study intentionally imports neither Google Drive raw art nor the original private confirmation dataset. Research upstream: [Model #100](https://github.com/ryonakayama234/ImageProgram/issues/100); [ImageProgram code branch](https://github.com/ryonakayama234/ImageProgram/tree/research/cc02-p02-branch-evidence).
