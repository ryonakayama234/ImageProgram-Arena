# CC-02-R2 Arena: independent candidate presence experiment (development only)

Date: 2026-10-17 JST. Parent [Model Issue #110](https://github.com/ryonakayama234/ImageProgram/issues/110). Based on [Arena Draft #46](https://github.com/ryonakayama234/ImageProgram-Arena/pull/46). Coordinate-based **NEW 9-case developmental pilot**, not the recovered 17 historical tasks.

## Objective and separation

Check whether real Model PartialContour P's full candidate bank contains the intended visible synthetic contour. Distinguish **candidate missing** from **candidate present but old policy chose different / held**. Candidate correctness is checked ONLY after the model has saved its complete public-path bank; Model must not import this Arena grader or its private target definitions.

~~~mermaid
flowchart TB
 S["Arena new DEV generator / private analytic target"]
 P["Separate public JSON raster and SHA"]
 M["ImageProgram actual PartialContour -> all observed paths"]
 L["Model saved bank / commit / observation source hashes"]
 A["External SHA anchor before grade"]
 G["Independent Arena post-hoc scorer"]
 R["Per-case candidate recall / old selection / hold"]
 S --> P --> M --> L --> A --> G --> R
 S -->|"private geometry; never to Model"| G
~~~

~~~mermaid
erDiagram
 PUBLIC_MANIFEST ||--o{ PUBLIC_TASK : contains
 PUBLIC_MANIFEST ||--|| PRIVATE_MANIFEST : hash_binds
 PUBLIC_MANIFEST ||--|| PREDICTION_MANIFEST : hash_binds
 PUBLIC_TASK ||--|| OBSERVED_BANK : produces
 OBSERVED_BANK ||--o{ CANDIDATE_PATH : includes
 CANDIDATE_PATH ||--o{ PIXEL_CENTRE : orders
 PRIVATE_MANIFEST ||--o{ ACCEPTED_PATH : defines
 OBSERVED_BANK ||--|| CASE_GRADE : reviewed
 ACCEPTED_PATH ||--|| CASE_GRADE : compared
~~~

## New fixture / independence scope

Four distinct geometry/source families: single-line, longer-neighbor, equal-neighbor and faint-target. Each has normal and transposed rendition; family ID remains private Arena metadata, not part of Model input. One no-ink control. Total 8 positive synthetic tasks in **four source families** + one negative control. No old 17-case output is re-used as a new performance sample. No genuine artwork, Drive upload, or old sealed confirmation.

A chosen line can be physically plausible but wrong. For positive tasks, candidate availability requires a complete contiguous observed open path to match the independently specified full target geometry: both endpoints within 0.76px and full bidirectional pixel-centre coverage. No target-only recall: a candidate continuing into a distractor fails precision. Targets may be reversed to allow unoriented observation. A matching candidate is not by itself proof of intended selection or a verified end condition.

## Contracts and anti-leak

PREDICT consumes only per-case public task JSON, which excludes case_id, family name and target. Source-only predictor is invoked by subprocess through the pinned Model checkout, is forbidden to read private.json and refuses dirty/gitless Model environments. The pilot runner itself has two distinct phases, PREPARE and PREDICT; grade must be invoked later in its own process after a separate external prediction-SHA anchor. All paths include full coordinate arrays and original observer source SHAs.

Independent grader:
- Refuses missing/extra/duplicate case IDs, version mismatch, invalid canonical SHA, source public task mismatch, modified candidate receipt or forged geometry hash, nonfinite path points, gaps and duplicate vertices, wrong selected ID and claimed verified completion.
- Rejects private target leakage or positive targets on control rows. Uses no ImageProgram imports and no model inference.
- Keeps all case denominators and distinguishes candidate_available, legacy_selected_correct, legacy_wrong_selected_candidate and legacy_hold. Selection accuracy is conditional on candidate availability; reports null rather than zero when no positive candidate exists.
- Never treats no candidate as finished and never promotes the old endpoint-only record to verified completion.

## Execute

Requires both repository checkouts and Python3.12 render environment installed from exact Model branch.

~~~bash
cd ImageProgram-Arena
python3.12 -m adapters.imageprogram_reference.cc02_r2_dev_pilot --phase prepare \
  --out /tmp/cc02-r2-dev
~~~

Record public and private canonical SHA in append-only external GitHub issue BEFORE predicting.

~~~bash
python3.12 -m adapters.imageprogram_reference.cc02_r2_dev_pilot --phase predict \
  --out /tmp/cc02-r2-dev --model-checkout /path/to/ImageProgram \
  --model-python /path/to/model-venv/bin/python3.12 \
  --public-sha256 PUBLIC_SHA
~~~

Pin newly produced prediction canonical SHA BEFORE GRADE. Run a fresh process:

~~~bash
python3.12 -m adapters.imageprogram_reference.cc02_r2_candidate_review \
  --public /tmp/cc02-r2-dev/public.json --public-sha256 PUBLIC_SHA \
  --private /tmp/cc02-r2-dev/private.json --private-sha256 PRIVATE_SHA \
  --prediction /tmp/cc02-r2-dev/prediction.json --prediction-sha256 PRED_SHA \
  --out /tmp/cc02-r2-dev/grade.json
python3.12 -m unittest discover -s tests -p "test_cc02_r2_*.py" -v
~~~

The independent grader does not import a hidden task factory; it reads and validates ONLY saved blobs. Grade output is exclusive-create and reports family-grouped rows (not a misleading single 9-trial independent accuracy claim).

## Experiment / failure ledger

**Implemented, source-published**: 9-case new public/private generator, public-only two-phase predictor runner, standalone coordinate-based candidate scorer, 12 adversarial scorer tests and 4 DEV-fixture tests, Model-side eight candidate-observation tests, full System/ER and runbook.

**NOT RUN / NOT CLAIMED:** real GitHub branch Python3.12 Model/Arena tests, Ruff, actual 9-case paired Model PREDICT followed by independent grade, experimental candidate recall, R1 optimization, confirmation geometry, Motor, Skill, old sealed confirmation, human L1 review, merging or paid CI. The older Arena #46 Python3.12 104/104 result is NOT a substitute for this PR's test status.

### Stage-gate decision

If correct path absent: P/generator support or geometry decomposition is the bottleneck; do not assert R failure. If path present but old selection wrong or holds: freeze bank SHA and test one anchor-conditioned selection intervention with identical bank. Separate weak line / false completion from R1 to avoid mixing two interventions.

Wolfram exact one-sided 95% zero-error upper bound (assuming independent families): four families -> 52.71%, six -> 39.30%, twelve -> 22.09%, sixty -> 4.87%. These illustrative values are NOT valid statistical confidence intervals for correlated transposition cases. No global ability promotion based on this small development group.
