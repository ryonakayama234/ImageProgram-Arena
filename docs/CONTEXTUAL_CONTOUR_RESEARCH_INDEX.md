## Latest G1 / actual P02 observation — 2026-10-16

[Python3.12 complete validation, fixed actual observations, independent source-stroke grade, System/ER/results/negative evidence](CC02_G1_PYTHON312_OBSERVED_P02_20261016.md). Model301/Arena176/runner6, full Ruff/doctor PASS. G0=G1 TP7/TN20/FP0/FN0, UNKNOWN10; improvement NOT_DEMONSTRATED. #99 blind annotation, R path, drawing, confirmation and merge remain open/deferred.

## Latest P02 execution — 2026-10-16

[W0 full Python3.12 validation / System / ER / fresh anchored PREDICT-GRADE / failures / Decision](CC02_P02_W0_EXECUTED_20261016.md). Model293/293, complete Arena165/165 (current161+historical4), runner6/6 and both full Ruff PASS. All27 source-derived grades retained, including two budget abstentions; no semantic/path/drawing capability claim. W0 is complete; #99 independent blind annotation stays OPEN, confirmation unscored, Draft/unmerged.

## Latest execution — 2026-10-16

[V2 actual source-derived reproduction / System / ER / initial failures / all results / next gate](CC02_V2_EXECUTION_20261016.md). 3P/2G/1action reproduced, not new ability. #99 independent annotation still OPEN; confirmation untouched.

# Contextual Contour — Arena decision / evaluation index
Reviewed 2026-10-15 JST. Keys: H-ContextualContour-01, ADR-CC02-001, CC-02-V, CC-02-P, CC-02-R, Oracle-P, Oracle-R, drawing-deferred.

**ACTIVE EVALUATION DIRECTION:** [ADR-CC02-001 — 分離した知覚/関係/推論評価](ADR_CC02_001_PERCEPTION_REASONING.md); paired [Model ADR](https://github.com/ryonakayama234/ImageProgram/blob/research/contextual-contour-cc02/docs/ADR_CC02_001_PERCEPTION_REASONING.md).

| Record | Where | Why |
|---|---|---|
| Central issue | [ImageProgram #96](https://github.com/ryonakayama234/ImageProgram/issues/96) | master status, updated decision |
| Historic CC-00 | [Evaluation contract](CONTEXTUAL_CONTOUR_CC00_EVALUATION.md) | score boundaries, leakage protection |
| Historic CC-01 | [Simple synthetic decision-only results](CONTEXTUAL_CONTOUR_CC01_RESULTS.md) | 6-pair toy, rotation probe NOT independent confirmation |
| Prior CC-02 | [Hard-pair protocol and negative results](CONTEXTUAL_CONTOUR_CC02_PROTOCOL.md) | public/private records, frozen confirmation hash, provisional failure taxonomy |
| **Current ADR** | [ADR-CC02-001](ADR_CC02_001_PERCEPTION_REASONING.md) | independently isolate perception (P), graph (G), reasoning (R); delay full drawing |

Next sequence: CC-02-V SHA-pinned integration reproduction + arc-level annotation audit → CC-02-P perceptual candidate adequacy and cost → CC-02-R conditional edge/path choice with DEV-ONLY oracle arms → CC-02-PAIR factorized comparison → score STILL-UNUSED confirmation once; genuine artwork/Motor/Canvas/Replay in CC-03.

Do NOT count oracle-P/R injected truth as real Model skill, do NOT leak labels/family IDs, and do NOT silently change old confirmation labels based on mistakes. If source/annotation protocol changes, version it and create a fresh unused confirmation set. Keep original art, private annotations and raw review episodes out of GitHub. All future work packages must update System, ER/Data, Experiment and Decision together; search for ADR-CC02-001 to understand chosen/deferred options and re-open triggers.


## Active implementation trackers (2026-10-15)

[#99 verify and arc-audit](https://github.com/ryonakayama234/ImageProgram/issues/99) → [#100 private P-candidate review](https://github.com/ryonakayama234/ImageProgram/issues/100) and [#101 G/R matched-graph review](https://github.com/ryonakayama234/ImageProgram/issues/101) → eventually factorized integrated test, sealed confirmation, CC-03. The distinction between **pure P**, **G on frozen fragments**, and **R on frozen relations** is now required by Arena ADR-CC02-001. Oracle-P must provide distractors, not an answer-encoded target-only graph. No additional experiments/CI/merge occurred from this index update.


### Annotation admission and blind stage review (2026-10-15)

Before any new P/G/R evidence claim, use the [Arena-private L0/L1/L2 annotated visible-arc protocol](CC02_PRIVATE_ANNOTATION_PROTOCOL.md); human annotation is scoped to uncertain/difficult authorized ROIs, with blinded review and true arc overlap instead of bounding-box-center proxy. **Protocol is written; samples are not yet annotated or evaluated.**
