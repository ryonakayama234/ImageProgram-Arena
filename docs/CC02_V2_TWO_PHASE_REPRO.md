> **2026-10-16 execution update:** SHA-verified source-derived reproduction, complete Model/Arena test matrix and separate anchored prediction/grade have now run. Independent annotation remains pending; #99 stays OPEN. See [executed System/ER/Experiment/Decision](CC02_V2_EXECUTION_20261016.md). The NOT_RUN statements below describe the earlier authoring checkpoint.

# CC-02-V2: paired-checkout reproduction and two-phase DEV evaluation

Date: 2026-10-15 JST. Status: IMPLEMENTED IN DRAFT, **not executed end-to-end**.
Parent: [ImageProgram #99](https://github.com/ryonakayama234/ImageProgram/issues/99).
Model design companion: [CC02_V2_REPRO_DECISION](https://github.com/ryonakayama234/ImageProgram/blob/research/cc02-v1-arc-audit-20261015/docs/CC02_V2_REPRO_DECISION.md).
Source head: Model parent `c388db96a31a7ded3ae868e897fafad9521f7518`, Arena parent `c5235332cf2d3747189d4c21ae5886726e18239f`; use PR HEAD SHAs at execution time, NOT these pre-V2 sources.

## System: implementation boundaries

~~~mermaid
flowchart TD
  G["DEV generator: public+private same-source, not blind"] --> U["PUBLIC view only: L8/focus/anchor/budget"]
  U --> P["Frozen Model v2 observe_graph + A1/B/B-shuffle"]
  P --> S["Persist serialized graph/decisions + 40-char Git SHA + receipt digest"]
  S --> X["External digest timestamp/commit BEFORE grading"]
  X --> R["Separate GRADE process, no imageprogram imported"]
  G --> O["Arena-private DEV only: target arcs/STOP exclusions/control actions"]
  S --> R
  O --> R
  R --> L["39 action reviews; six positive target arcs; STOP exclusions; control metrics"]
  L --> D["Research Decision Gate V2"]
  G -. "NO confirmation factory invocation" .-> H["sealed confirmation"]
~~~

Implemented:
- `adapters/imageprogram_reference/cc02_v2_ledger.py`, CLI `--predict` or `--grade`; never both.
- `tests/test_cc02_v2_ledger.py`: canonical digest, missing/duplicate/tampered receipt, frozen candidate graph SHA, STOP/ambiguous negative annotation plus **conditional true paired-checkout integration test** (skip when ImageProgram unavailable).
- `scripts/cc02_v2_reproduce.sh`: paired immutable git checkouts; Python3.12+uv locked Model sync; Model check.py, Ruff, doctor, Model unit tests, Arena full suite and new-file Ruff, then *prediction only*. Script stops and explicitly prints receipt digest for independent archiving before private grading. It does not start paid CI/confirmation.

The split is operational, not cryptographic: the source generator remains readable and `create_development_pair` internally constructs private labels while the PREDICT stage discards them; receipt digest alone cannot prove prior chronology unless independently timestamped/committed. The scoring process never runs Model; Model input receives only public arrays.

## ER/data contract

~~~mermaid
erDiagram
  IMMUTABLE_CHECKOUT ||--o{ PREDICTION_RUN : identifies
  PUBLIC_DEV_MEMBER ||--o{ CANDIDATE_GRAPH_SNAPSHOT : observes
  CANDIDATE_GRAPH_SNAPSHOT ||--o{ ARM_DECISION_RECEIPT : selects
  PREDICTION_RUN ||--|{ ARM_DECISION_RECEIPT : persists
  PREDICTION_RUN ||--|| EXTERNALLY_ANCHORED_HASH : seals_before_review
  PRIVATE_DEV_ORACLE ||--o{ POST_HOC_REVIEW : adjudicates
  ARM_DECISION_RECEIPT ||--|| POST_HOC_REVIEW : grades_after
  POST_HOC_REVIEW ||--o{ STAGE_DIAGNOSTIC : classifies
  POST_HOC_REVIEW ||--|| RESEARCH_DECISION : informs
~~~

39 rows expected: DEV 12 public inputs × (A1/B/B-shuffle) plus 3 controls × B. Exactly 15 unique public inputs. `receipt_sha256` is SHA-256 of canonical JSON excluding itself; graph SHA is independently recomputed with frozen `nodes,edges,version,threshold,max_gap` before private review. Predict and grade both check Arena git commit identity, while the Model commit is recorded during prediction. Incomplete, unclean, unverifiable or SHA-mismatching local runs fail closed. Output paths are create-exclusive (no overwrite).

Arena SOURCE-DERIVED negative labels: STOP distal/peripheral strokes (all 6 negative members), positive-branch side arms where present (dev-01/04/05), neutral-context control. Shared branch junction pixels are not counted as forbidden. Ambiguous control has two possible context alternatives but neither is a privately forbidden target. Judge:
- action correctness and non-CONTINUE controls; controls expected HOLD/STOP/STOP;
- positive-target `ArcCoverage` and diagnostic P/G/path-unobservable;
- context candidate contamination via forbidden source pixels and exact-pixel target purity; candidate metric is diagnostic, not thresholded score;
- suspicious focus-context `possible_continuation` links touching private forbidden pixels, distinguished from *actual* false committed CONTINUE action;
- graph/node counts and work-budget data, with no selected Edge/path claim in frozen v2.

**Known limitations:** excluded ink coordinates are synthetic source transcriptions, not blinded labels; no independent human adjudicator. The same source template underlies DEV pairs. False-edge count is a *suspected* relation fault, not a path execution event. Path ownership, curves in real artwork, any model improvement or held-out correctness remain unverified.

## Experiment: records as of code authoring

- Existing V1 local reconstruction: source-derived DEV positives P absent 3, G absent 2, action-correct-path-unobserved 1, baseline B 7/12, A1 6/12, B-shuffle 6/12. **Historical, NOT rerun by V2**.
- V2 code was written on GitHub Draft branch; no exact checkout from GitHub or Python 3.12 lock/reproduction script executed here due DNS/network limitation. **Full Model tests / full Arena tests / Ruff / Model doctor / prediction output / grade / honest stage counts from V2 = NOT RUN**.
- Neither confirmation prediction nor training nor real art was run.
- Wolfram independent-risks illustration: even 0 bad joins in 6 independent trials gives one-sided 95% upper population risk bound ≈0.393; 0 in 15 would give ≈0.181. These i.i.d. assumptions do not describe our paired hand-authored DEV tasks. Zero observed false joins is a local engineering gate only.
- WSL2/bash sequence (requires user's authenticated git and uv access):
~~~bash
# 1) Supply current immutable 40-char HEADs of BOTH Draft PRs
bash scripts/cc02_v2_reproduce.sh MODEL_40_SHA ARENA_40_SHA \
  /tmp/cc02-v2-$(date +%Y%m%d-%H%M%S)
# 2) Stop: anchor receipt-sha256.txt in trusted out-of-band log/Git commit
# 3) In a separate execution, after anchoring the digest:
cd /tmp/cc02-v2-.../Arena
PYTHONPATH=/tmp/cc02-v2-.../Arena /tmp/cc02-v2-.../Model/.venv/bin/python \
  -m adapters.imageprogram_reference.cc02_v2_ledger --grade \
  --receipts /tmp/cc02-v2-.../pre_review_receipts.json \
  --receipt-sha EXACT_EXTERNALLY_ANCHORED_SHA \
  --out /tmp/cc02-v2-.../private_development_grade.json
~~~

## Decision

- **SELECT:** full authenticated GitHub checkout and full suites as the next operational action; do not assume stub tests validate runner. Maintain dual-stage persistent evidence with private grading only AFTER independent SHA anchoring.
- **KEEP #99 OPEN** until two-stage run passes complete gates and a human-/source-independent adjudication of target vs distractor/ambiguous cases exists; maintain UNKNOWN rather than force into P/G/R.
- **DEFER #100 / #101** code modifications until reproducible V2 baseline with false joins, negative controls and costs. Model frozen.
- **DO NOT:** execute confirmation, merge either Draft PR, launch paid workflows, transfer user Drive images to public GitHub, or claim the 39 scored receipts were produced before actual execution.
