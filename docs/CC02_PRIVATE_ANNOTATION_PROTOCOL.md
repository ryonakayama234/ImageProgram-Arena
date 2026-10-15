# CC-02-V — 独立アノテーション規約と段階別診断
**2026-10-15 JST / Status: PROTOCOL ONLY — new annotation samples 0, new experiments 0**
Decision: [Model ADR-CC02-001](https://github.com/ryonakayama234/ImageProgram/blob/research/contextual-contour-cc02/docs/ADR_CC02_001_PERCEPTION_REASONING.md); [Arena ADR-CC02-001](ADR_CC02_001_PERCEPTION_REASONING.md). Execution: [CC-02-V #99](https://github.com/ryonakayama234/ImageProgram/issues/99), [P #100](https://github.com/ryonakayama234/ImageProgram/issues/100), [R #101](https://github.com/ryonakayama234/ImageProgram/issues/101).

## 1. What was decided — and what was not
SELECT: first validate the provisional 3 absent candidate / 2 rejected relation / 1 success classification by actual target-arc overlap, with full GitHub-checkout reproduction. Next evaluate perception P, relation hypothesis generator G and selector/reasoning R with one factor changed at a time. P is a priority, but G/R receive independent fixed-input diagnostics in parallel; controlled co-evolution follows only observed stage results.

REJECT NOW: monolithic Graph v3 changing P/G/R together, because the cause of improvements and false joins would not be identifiable. REJECT: perfect perception as an absolute precondition for testing R; task-dependent oracle diagnostics can already expose selection weakness. DEFER: Motor/Canvas aesthetic optimization, end-to-end policy learning, reusable Skill induction; tiny Motor legality/Replay interface smoke only, labelled non-artistic. Reconsider only after reproducible evidence-linked target paths, stage-gate evaluations and provenance-checked real-art private ROIs. The earlier CC-02d implementation suggestion is HISTORICAL, not an active command.

## 2. How much annotation is necessary?
Not full semantic segmentation for every source, not a historical drawing program inferred from a finished image.

**Synthetic scene:** obtain exact visible arc geometry, program-generated components, ends and distractors as private annotations BEFORE model output; inspect a representative sample for rasterization/junction mismatch. Procedural source programs are only true for synthetic scenes.

**Real-art small ROI (provenance and right-to-use checked):** the minimum private label is visible target arc support (polyline or pixel mask and uncertain regions), other competing arc support, junction/crossing/occlusion hypotheses, explicit public task anchor/goal, acceptable continuing path(s), permissible termination, and a genuine-ambiguity category. Start with bounded challenging ROI strata: faint strokes, branches, curves, crossing/overlap, varying width, multiple unrelated lines; rights not verified means NOT ADMITTED, NOT tested.

**Finished art is underdetermined:** static raster cannot prove original brushstroke order or intent. Distinguish an observed pixel/arc, a proposed grouping, the intended task goal, and a possible drawing program. A guess about source history is never a ground-truth label.

## 3. Private annotation contract (proposed v1, NOT implemented parser)
| Tier | Required private fields | Why |
|---|---|---|
| Admission | source provenance, right-to-use verification reference and status, source SHA, ROI crop+transform SHA/version, source-family ID, split, public goal/anchor policy | Prevent copyright guesses, task ambiguity and split leak |
| L0 visible evidence | traced arc support/mask, weak/strong grayscale evidence, endpoints, boundary cuts, width band, uncertainty | Test P candidate retention without interpreting identity |
| L1 topology | plausible segments, junctions, crossings, unrelated neighbor arcs, multiple alternatives and evidence refs | Test G edges on the same candidates, including distractors |
| L2 target/task | independently scoped intended target arc IDs, excluded arc IDs, accepted path alternatives, terminal evidence, occlusion/unknown reason | Test R without equating no visible line to natural stop |
| L3 decision review | selected Node+Edge sequence, continue/stop/hold action, reason, forbidden join, unexplained stop, cost/latency, status | Audit final stage and abstention cost |
| Provenance | annotator/reviewer references, agreement/adjudication state, annotation version/SHA, sealed-before-prediction timestamp | Independent evaluation and reproducibility |

Private records remain Arena-only. The public Model sees ONLY allowed raster/focus/anchor/budget (and a task goal solely if publicly versioned); it never receives L0-L3 oracle IDs, split/family, author provenance or private target geometry. No original art or personal annotation identities committed to Git; publish aggregate counts and safe hashes.

## 4. Annotation governance
1. Freeze task definition and admissible paths before inspecting Model predictions. Annotators are blind to model-selected edges, previous answer labels and source-family shortcuts. Never derive target path from a chosen Model path.
2. Cover every plausible line within the small predeclared ROI, not only target pixels, to avoid giving oracle-assisted R the answer by candidate omission.
3. In difficult crossings or ambiguity, use two independent annotation passes if staffing permits; otherwise record single_rater_unreviewed and do not claim adjudicated consensus. Record unresolved disagreements and escalate to independent reviewer; unidentifiable stays unidentifiable rather than fabricated binary truth.
4. Observationally identical FULL public input, goal, anchor and budget with mutually exclusive hidden correct labels is UNIDENTIFIABLE for deterministic policy; score defensible HOLD under a separately versioned rubric or amend the public goal, never secretly relabel the already-frozen confirmation.
5. Oracle-P (DEV ONLY) must include correct, distractor and ambiguous candidates with neutral IDs/order and comparable budgets. Oracle-R (DEV ONLY) is constrained to what P actually offered. Keep oracle-assisted diagnostic tables completely separate from production capability scores and confirmation.
6. Treat Google Drive ownership as access/ownership of file in Drive, NOT proof of underlying artwork copyright, derivative/model-training permission, or authorship. Verify explicit right-to-use before using real ROIs.
7. Report all annotation admissions/rejections, uncertain counts, source-family and difficulty strata, cost and rater disagreement, not just passed examples. Any new annotation contract requires new version plus an ADR.

## 5. Independent-stage experiment specification
| Controlled comparison | Frozen input boundary | Primary measurement | Confound to report |
|---|---|---|---|
| P0 vs P1 | same PUBLIC image, ROI, goal, budget | actual target arc pixel/length candidate recall, false candidates, duplicates, cost | P1 changes downstream G input; this is NOT pure G/R gain |
| G0 vs G1 | exactly the SAME frozen Fragment set | true relation accessibility, forbidden edge proposals, uncertainty and cost | Edge differences attributable to G only if fragments truly fixed |
| R0 vs R1 vs C vs shuffle | exactly the SAME frozen Fragment+Relation graph, goal, budget | ordered target edge/path accuracy, false join, premature stop, hold vs answerability | Continue action without selected edges is insufficient |
| P0/R0, P1/R0, P0/R1, P1/R1 | same public input; graph hashes differ across P | interaction and actual integration gain | P1/R0 is perception-pipeline effect, not pure perception |

Missing accepted target candidate is counted only with actual target-arc geometry overlap and registered tolerance; the previous bounding-region-center proxy cannot establish genuine missed evidence. G0/G1 comparison needs fixed Fragments and R0/R1 needs fixed Relations. If schema adaptation changes meaning or budget, mark adapter_incompatible. Count zero-result, hold, forbidden joins, budget exceeded and unsupported in denominators.

## 6. Work gates and explicit reopen conditions
**CC-02-V:** actual paired checkout SHAs, dependency/config/manifest hash, full tests/Ruff and untouched v2 hard development receipts; independent true arc annotation audit of all 6 continue cases, discrepancy classification and public/private boundary audit. NO v3 or painting before this scientific prerequisite.

**CC-02-P:** development synthetic plus authorized private real-ROI calibration; provisional at least 5/6 intended continuation arc fragments remain accessible, with bounded spurious candidates and nonzero negative controls. Failure or heavy false-positive flooding means candidate detection is not solved.

**CC-02-G/R:** true target edges available on frozen P, correct selected Node+Edge paths and zero confident forbidden joins in declared controls; distinguish positive terminal evidence, missing observation and actual ambiguity. If DEV Oracle-P still fails with unchanged R, prioritize G/R; if Oracle-P works but P0 does not, prioritize P.

**CC-02-PAIR:** only after interpretable stage diagnostics, freeze config/version and score prospective six confirmation pairs ONCE; at least 5/6 both-correct pairs and advantage over simple collinearity C are small-sample engineering gates, not evidence of real-art generalization. Real-art source-family transfer requires independently curated/admitted family.

**CC-03-DRAW:** reopen appearance/Motor/Canvas optimization after explicit evidence-linked path and private art ROI review exist; verify legal Motor/Replay separately. A beautiful wrong path is not artistic competence.

## 7. Handoff checklist for any later AI
Search terms: ADR-CC02-001, CC-02-V, CC-02-P, CC-02-G, CC-02-R, CC-02-PAIR, source-arc-overlap, annotation-blindness, candidate-adequacy, unidentifiable, drawing-deferred. For EACH change package, update System diagram, ER/Data version, full Experiment/negative ledger, and Decision (selected, rejected, deferred, revisit trigger); link exact Model+Arena commit SHAs. Do not overwrite previous v2 scores, prior labels, confirmation manifest or historic decisions.
