# ADR-CC02-001 — Arenaの独立診断をP(知覚)・G(関係仮説)・R(推論)に分離
**Date:** 2026-10-15 JST
**Status:** ACCEPTED RESEARCH DIRECTION; implementation pending / confirmation NOT SCORED
**Parent:** [ImageProgram #96](https://github.com/ryonakayama234/ImageProgram/issues/96), [Model ADR](https://github.com/ryonakayama234/ImageProgram/blob/research/contextual-contour-cc02/docs/ADR_CC02_001_PERCEPTION_REASONING.md)
**Supersedes:** the next-step interpretation in [CC-02c protocol](CONTEXTUAL_CONTOUR_CC02_PROTOCOL.md) that might be read as immediate bundled graph-v3 implementation; does not change recorded results/labels/hashes.
**Owner:** ImageProgram-Arena independent reviewer; do not silently turn evaluator annotations into public Model inputs.

## 1. Why this decision

Six hard synthetic development intended-continue cases in the prior **local mirror only**: 3 missing an admitted distal Node by target-region-center proxy, 2 retained a Node but no accepted continuation Edge, 1 succeeded. Overall Model B correct action 7/12. Neither semantic art segmentation nor drawing has been tested. The proxy class is uncertain: a candidate center outside the region is not necessarily an absent correct target arc. Need arc-based annotation and independent stage review before interpreting the breakdown as fact about perception.

User review 2026-10-15: CC-02d bundled improvements to perception, relational reasoning and path selection, risking optimization of drawing despite weak upstream stages and no causal experiment. Choice: perception-first DIAGNOSTIC, independently probe relation reasoning, controlled co-evolution, defer drawing policy/learning. Other options and revisit triggers are in Model ADR; both documents are normative for the respective repository.

## 2. System and ER: independent oracle does not leak

~~~mermaid
flowchart LR
 A["PRIVATE annotated art/scene and oracle target"] --> E["Arena: stage-wise evaluation after receipt"]
 A --> U["Public allowed L8 + focus/anchor/budget"]
 U --> P["Model P fragments / support and missingness"]
 P --> G["Model G relation candidates"]
 G --> R["Model R chosen edge path or stop/hold"]
 R --> D["sealed decision receipt"]
 D --> E
 P --> X["candidate coverage review"]
 G --> Y["edge admissibility review"]
 X --> E
 Y --> E
 R -. "D deferred" .-> Z["fit/Motor/Canvas/Replay"]
 A -. "only DEV diagnostic arms" .-> O["Oracle-P/Oracle-R"]
 O --> E
~~~

~~~mermaid
erDiagram
  SOURCE_FAMILY ||--o{ PRIVATE_TASK : groups
  PRIVATE_TASK ||--|| PUBLIC_TASK : releases_allowed_view
  PRIVATE_TASK ||--|| PRIVATE_ANNOTATION : grades
  PUBLIC_TASK ||--o{ CANDIDATE_RECEIPT : observed_with
  CANDIDATE_RECEIPT ||--o{ RELATION_RECEIPT : edge_hypotheses
  RELATION_RECEIPT ||--o{ PATH_DECISION_RECEIPT : selected_from
  PRIVATE_ANNOTATION ||--o{ STAGE_REVIEW : independent_oracle
  PATH_DECISION_RECEIPT ||--o{ STAGE_REVIEW : reviewed_after
  MANIFEST ||--o{ STAGE_REVIEW : tracks
~~~

### Target audit schema, additive (not yet implemented)
- PrivateAnnotation: verified ROI target ARC pixels/polyline, excluded arc IDs, true visible endpoints, ambiguity evidence/status, family provenance and license suitability, version; all PRIVATE.
- PublicTask: same existing allowlisted raster/focus/anchor/budget; never hidden label, target coordinates, author/source ID, or any code that encodes class as a filename.
- StageReview: P target-arc candidate recall, fragmentation/duplication and spurious candidates, G target-edge presence/forbidden edge false-support, R path/selected edge ID and action, stop evidence vs unjustified stop, hold on answerable vs ambiguous cases, cost, status/unknown and source hashes.
- ExperimentManifest: immutable Model/Arena commit SHA, public/private split digest, target annotation SHA, configs/seeds, versioned data contracts, pre-grade receipt hash and diagnostic oracle flag. Full private art/labels/reviews stay local, safe metrics/aggregate hashes may be committed.

## 3. Experiments, comparability, and exact boundaries

| Experiment label | Graph from | Selector from | Question | Belongs to true production-arm score? |
|---|---|---|---|---|
| P0-R0 | frozen Model v2 | frozen Model v2 | reference | Yes (development) |
| P1-R0 | revised P with schema adapter | fixed R0 | does more candidate evidence alone help? | Yes if adapter valid |
| P0-R1 | frozen P0 | revised R1 | does reasoning alone help? | Yes |
| P1-R1 | revised P1 | revised R1 | interaction and combined outcome | Yes |
| Oracle-P / R0 or R1 | Arena injected true candidate graph, dev ONLY | real R | isolated reasoning opportunity | **NO**, diagnostic only |
| P0/P1 / Oracle-R | actual Model candidate graph | Arena oracle choice of already-available candidates, dev ONLY | upper bound on candidate adequacy | **NO**, diagnostic only |

Do not compare arms unless input pixels/focus/anchor/budgets and common candidate-set hash per model selector trial are preserved. Alternative graphs P0 vs P1 are DIFFERENT and must not be called same-candidate; only selectors on a given graph share hash. Report CPU work, number of observed nodes/edges, misses and false positives rather than counting a massive candidate flood as progress.

A1, strong collinearity C, B and B-shuffle must share the same graph **within each P version**. Oracle-P and Oracle-R use private truth in an explicitly tagged OFFLINE DEVELOPMENT DIAGNOSTIC only; no hidden annotation in ordinary inference and NO oracle-arm confirmation scoring.

**Unidentifiable truth guard:** Entire public observation identical plus same anchor/goal/budget yet opposite private correct label means deterministic selector cannot solve both; mark as unidentifiable and score legitimate HOLD under versioned policy where appropriate. The synthetic finite-visible rule is not natural-art termination evidence. Do not quietly relabel the existing sealed confirmation: new label contract requires new split/version/fresh confirmation.

## 4. Gated sequencing

1. CC-02-V: authoritative pinned Model+Arena checkout execution of existing v2 with full suites/Ruff; ARC-based independent annotation audit of 3 candidate_missing proxies and original pair validity. If results differ, report discrepancy, retain previous history. **BLOCKS claiming verified progress.**
2. CC-02-P (priority): bounded candidate preservation experiments on development synthetic; T/Y, thin grayscale, curves, distractor density. Candidate target-arc coverage plus false positive/candidate flood and latency, not just overall action score. Proposed minimum necessary fragment recall 5/6 on six intended-continue dev cases; revise target only before untouched confirmation.
3. CC-02-R (parallel distinct): freeze P0, compare R0/C/B on same graph; test Oracle-P on DEV-only to isolate R and P0/P1 with Oracle-R to bound recoverability. Real task/semantic target annotations NOT used as model features. Evaluate correct edge/path and false join, not merely continue/stop; zero forbidden joins.
4. CC-02-PAIR: only after P and R diagnostics are interpretable, 2×2 integrated trial, version freeze, first-time untouched six-pair confirmation. Always report unknown/hold. Five-of-six is an engineering gate and insufficient for real-art generalization.
5. CC-03 drawing: defer appearance/Motor/Skill optimisation; allow only explicitly labelled minimal legal interface smoke tests. Separate 3 representative real-art annotated ROI target quality and Replay gate after P/R, subject to rights/provenance.

## 5. Governance and selected-vs-deferred

- **SELECTED** P diagnostic before v3 rewrite, independent reasoning probes in parallel; revise P/G/R with one controlled change per experiment. Primary rationale: 3 suspected P-stage failures, 2 G-stage failures, 1 success; v2 Stop conflates no accepted successor with real terminal.
- **REJECTED now** monolithic v3 rewrite then drawing: cannot attribute gains or false joins.
- **REJECTED** waiting for “perfect perception” and never testing reasoning: candidate semantics depend on relation target.
- **DEFERRED** learning end-to-end, skill mining, creative synthesis: no sufficiently independently annotated real-art family, episode regime or proven P/R abstraction yet.
- **DEFERRED** full Motor/Canvas style optimization: can draw beautiful wrong contours and conceal target-selection failures.
- **REOPEN drawing** once selected path has explicit ordered Node+Edge IDs, independent P/R tests pass, real ROI review is prepared, and legal Motor/Replay smoke test passes.
- **REOPEN training** only after provenance-cleared corpus + frozen independent family + robust success/failure episode records, with baseline and contamination controls.

Record search keys: ADR-CC02-001, user-design-review-20261015, perception-first, Oracle-P, Oracle-R, stage-review, candidate-arc-recall, drawing-deferred, CC-02-V, CC-02-P, CC-02-R, CC-02-PAIR, CC-03-DRAW. On EACH work unit update System/ER/Experiment/Decision as one evidence-linked package. CC-01/CC-02c negative results, original labels and confirmation hash remain historic. No merge, paid CI, original/private art commit.
