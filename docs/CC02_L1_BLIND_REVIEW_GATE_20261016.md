# CC-02-L0/L1 blind review gate — 2026-10-16, Draft

**Decision: SELECT an annotation-first diagnostic. IMPLEMENTED infrastructure / NOT YET EXECUTED human annotation. No G1 performance promotion.**

## Why

[Model G1 #108](https://github.com/ryonakayama234/ImageProgram/pull/108) and [Arena G1 #44](https://github.com/ryonakayama234/ImageProgram-Arena/pull/44) established Python 3.12.14 locked regression (Model301/301, Arena176/176, W0 runner6/6, both full Ruff PASS) at their **earlier pinned commits**. Their actual P02-observed synthetic rasters contain 32 arms/37 pairs: known source-stroke labels G0=G1 TP7/TN20/FP0/FN0; **10 UNKNOWN**. G edge kinds differ on zero pairs; previous hand-authored G1 geometry success did not transfer. Input P02 empty in 17/27 scenes. Those findings are historical evidence, not a new PASS for this branch.

The ten UNKNOWN pairs are exactly **obs-02: 3, obs-10: 6, obs-11: 1**, all from the existing DEV family. The frozen scope is [Arena review scope JSON](https://github.com/ryonakayama234/ImageProgram-Arena/blob/research/cc02-l1-blind-annotation-gate/adapters/imageprogram_reference/cc02_l1_review_scope.json), bound to existing P02 observation canonical SHA \`01d4cb52b2cc62f86c06730b9bc00982e03209ad14b2c7b519f0d1d1796b0af0\` and original Git code heads. Selection is **all unknown pairs**; no cherry-picking favorable G edges.

## System

~~~mermaid
flowchart TD
 O["Saved synthetic public P02 observation (anchored SHA)"] --> C["Validate 27 cases, all source heads, 3 fragment SHAs, 10 pair IDs"]
 P["Same frozen public raster generator"] --> V["Verify all 27 raster hashes"]
 V --> B["Public raw PNG and neutral Fragment SVG review packet"]
 C --> B
 B --> A["Reviewer A: L0 support, L1 relation"]
 B --> R["Reviewer B: L0 support, L1 relation"]
 A --> Q["Independent two-reviewer reconciliation"]
 R --> Q
 Q --> U["CONSENSUS / DISPUTED / UNRESOLVED / PENDING"]
 U -. "Not yet!" .-> G["Optional G0/G1 re-score only after label freeze"]
 U --> X["L2 artist intent remains NOT_EVALUABLE"]
~~~

## Data / ER

~~~mermaid
erDiagram
 ANCHORED_OBSERVATION ||--|{ OBSERVED_FRAGMENT : contains
 OBSERVED_FRAGMENT ||--|{ PAIR_FOR_REVIEW : participates
 PUBLIC_RASTER ||--|| REVIEW_PACKET : visualizes
 REVIEW_PACKET ||--o{ REVIEWER_RESPONSE : constrains
 REVIEWER_RESPONSE ||--|{ L0_SUPPORT_RESPONSE : provides
 REVIEWER_RESPONSE ||--|{ L1_PAIR_RESPONSE : provides
 REVIEW_PACKET ||--o{ CONSENSUS_RECORD : binds
 CONSENSUS_RECORD ||--|{ L1_PAIR_RESPONSE : reconciles
~~~

- **L0** question: is the specific observed arm supported by visible image ink? Values: supported / contradicted / uncertain / pending.
- **L1** question: do two fragments lie on the same visibly traceable curve? Values: same_visible_curve / different_visible_curve / ambiguous / not_evaluable / pending. This is **not** source-stroke identity or task-selected path.
- **L2** actual target ownership, artist intention, stop/hold: **NOT_EVALUABLE** from these public raster-only packets. Requires separately documented task/artist-intent protocol; must never be inferred from author-private source stroke index, Model-selected Edge, or old target-region proxy.
- Each reviewer gets the same raw raster image first (L0) and numbered, neutral-color support geometry overlay for L1. Image/observations/Fragment digests are checked. Neither packet nor response templates contain G0/G1 prediction, source labels, confirmation or correct answers. Colors denote fragment IDs only, not class.
- Reviewer identities must differ; the code checks structural identity and agreement, not actual organizational reviewer independence or blindness. Annotators still need a real independent workflow.
- **CONSENSUS** only when both reviewers mark both visible supports as supported and agree on L1 same/different. Disagreements remain DISPUTED; ambiguity/unobserved support stays UNRESOLVED; unanswered PENDING. No majority vote, no silent forced label, no automatic G1 scoring.

## Implementation / locked scope

On the new Arena research-only branch, add:
- \`adapters/imageprogram_reference/contour_l1_review.py\`: \`prepare\` (saved-observation SHA check, all27 public image hash checks, 3 review PNG+SVG pairs, packet SHA, reviewer templates) and \`reconcile\` (separate reviewer answers, rejection of changed/unanchored pair universe and invalid labels; no G inference).
- \`adapters/imageprogram_reference/cc02_l1_review_scope.json\`: exact 3 task/10 pair mapping and frozen prior source SHA/Fragment SHAs.
- \`adapters/imageprogram_reference/test_contour_l1_review.py\`: 7 strict standalone tests including hash mutations, missing pair, label injection, duplicate reviewer identity, actual disagreement, PENDING behavior and no G/source-label content.

**Verified this turn:** standalone Python 3.13.5 \`unittest\` **7/7 PASS**; \`py_compile\` PASS. Three files' exact Git blob SHA match local tested bytes. **NOT VERIFIED this turn:** full locked Python3.12 Model/Arena suites/Ruff for the new branch; real old observation JSON replay; actual PNG generation on the authentic restored source trees; two human reviews; L0/L1 consensus; any G0/G1 delta; real artwork; R paths; original confirmation; merge/paid CI.

## How to execute from the original saved observation

This step requires the **existing saved observation.json artifact** from the previous G1 execution bundle, whose **canonical** JSON SHA is pinned above. A summary-only evidence JSON cannot substitute for that full artifact. Do not fabricate or reconstruct P02 predictions from documentation.

~~~bash
cd /path/to/ImageProgram-Arena
export PYTHONPATH="$PWD:/path/to/ImageProgram/src"
MODEL_PY=/path/to/ImageProgram/.venv/bin/python
$MODEL_PY -m unittest -v adapters.imageprogram_reference.test_contour_l1_review

$MODEL_PY -m adapters.imageprogram_reference.contour_l1_review \
  --phase prepare \
  --observation /path/to/prior/g1/observation.json \
  --observation-sha256 01d4cb52b2cc62f86c06730b9bc00982e03209ad14b2c7b519f0d1d1796b0af0 \
  --scope adapters/imageprogram_reference/cc02_l1_review_scope.json \
  --out /tmp/cc02-l1-review-new

# Give separate reviewers their own JSON templates and raster/overlay images.
# Do not show reviewer B the A response. Do not provide G0/G1 labels.
# After both independently record real answers:
$MODEL_PY -m adapters.imageprogram_reference.contour_l1_review \
  --phase reconcile \
  --packet /tmp/cc02-l1-review-new/packet.json \
  --review-a /path/to/completed-reviewer-A.json \
  --review-b /path/to/completed-reviewer-B.json \
  --out /tmp/cc02-l1-review-reconciliation-new.json
~~~

Output directories and reconciliation file use exclusive creation; do not overwrite earlier receipts. Publish the review-packet canonical SHA before annotation and record each actual review submission time/provenance before any downstream G evaluation. Images here derive from existing synthetic inputs, not Google Drive user art.

## Experiment ledger and decision

| Stage | Status | Evidence |
|---|---|---|
| Frozen universe of original UNKNOWN | **DONE** | 3 DEV scenes, 10 pairs, exact prior hashes |
| Code + isolated tests | **DONE** | 7/7, py_compile, exact Git blobs |
| Full source-exact Python3.12 revalidation of new code | **NOT RUN** | earlier G1 301/176 PASS does not transfer to new branch |
| Render actual 3 synthetic review scenes from original saved observation | **NOT RUN** | requires saved observation.json |
| Real independent two-person blind judgement | **NOT RUN** | no fabricated labels |
| Compare frozen G0/G1 to new independent reference | **NOT RUN** | no semantic accuracy claim |
| L2 ordered path / STOP / HOLD | **NOT RUN** | defer until task-intent ground truth |

**SELECT** annotate the existing ten unknown relations before any threshold tuning; **REJECT** interpreting G1 7/7 as end-to-end drawing skill or treating undecidable junction pixels as positive/negative by default; **DEFER** curved/slanted new family experiment until its generation/source-family split and label contract are independently preregistered, then P0+P02 duplicate-aware adapter and R0/R1 ordered-path comparison on the same frozen graph.

Parent [#99](https://github.com/ryonakayama234/ImageProgram/issues/99) / [#101](https://github.com/ryonakayama234/ImageProgram/issues/101), ADR-CC02-001. Original confirmation six pairs remain sealed and unscored; keep both new PRs Draft/unmerged.
