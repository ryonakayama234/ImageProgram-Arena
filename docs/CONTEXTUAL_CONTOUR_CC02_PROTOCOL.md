> **2026-10-15 decision update:** [ADR-CC02-001: Arena独立診断・Oracle arms・停止/保留判定](ADR_CC02_001_PERCEPTION_REASONING.md). The CC-02d bundled-next-step recommendation below is HISTORICAL and superseded in execution order; this document's prior results, hashes and frozen confirmation state are retained without retrospective adjustment.

# CC-02a/b/c — hard-pair protocol, System/Data and pre-change v2 diagnostic
2026-10-14 JST | Status: **hard development tested in isolated local mirror; original Code checkout full-suite NOT RUN. Confirmation NOT SCORED; Canvas NOT RUN.**

Parent issue: [ImageProgram #96](https://github.com/ryonakayama234/ImageProgram/issues/96). Stacked baseline: Model Draft #97 HEAD \`92729312c7b4a3edfdaab04d8f3c91c43af85a38\`, Arena Draft #36 HEAD \`00642c2481c8084705b7955950d0f05134f2f7cc\`. These are pre-CC02 parent commit refs, NOT evaluated new-branch checkouts. The new CC-02 branch is \`research/contextual-contour-cc02\`. Related Model architecture+decision record: [CONTEXTUAL_CONTOUR_CC02_DIAGNOSIS.md](https://github.com/ryonakayama234/ImageProgram/blob/research/contextual-contour-cc02/docs/CONTEXTUAL_CONTOUR_CC02_DIAGNOSIS.md).

## 1. System — implemented and not implemented

~~~mermaid
flowchart TD
  S["Arena procedural source / PRIVATE target & genealogy"] --> P["PUBLIC: L8 raster, ROI focus, anchor, pixel budget"]
  P --> O["UNCHANGED CC-01 v2 observe_graph: components + PCA"]
  O --> G["CandidateGraph: Fragments and hypothetical geometric Edges"]
  G --> A["A1: local-only"]
  G --> B["B: contextual successor"]
  G --> X["B-shuffle: correspondence diagnostic"]
  A --> D["pre-review decision receipts"]
  B --> D
  X --> D
  S --> E["Arena-private evaluation labels / excluded arcs"]
  D --> R["Arena after-decision independent reviewer"]
  E --> R
  R --> L["CC02 development ledger: failure classified by stage"]
  D -. "NOT RUN" .-> W["fit/Motor/Canvas/Replay"]
  L -. "NEXT PHASE ONLY" .-> N["CC-02d v3 Node/Edge/Stop-Hold redesign"]
~~~

CC-02 model v3 has **NOT** been implemented. This step intentionally measures current v2 unchanged. Code \`adapters/imageprogram_reference/contextual_contour_cc02_tasks.py\` generates deterministic tasks and private targets; \`contextual_contour_cc02_pilot.py\` performs v2 decision-only evaluation and independent grading; \`tests/test_contextual_contour_cc02.py\` tests pair/split/public contracts. No actual artwork imported; no changes to World, P1/P2 or learned Skill.

## 2. Data and permission boundaries

~~~mermaid
erDiagram
  TEMPLATE_FAMILY ||--o{ PAIR : organizes
  PAIR ||--|{ MEMBER : owns
  MEMBER ||--|| PUBLIC_TASK : exports
  MEMBER ||--|| PRIVATE_TARGET : annotates
  PUBLIC_TASK ||--o{ GRAPH_DECISION : produces
  GRAPH_DECISION ||--o| REVIEW : evaluated_by
  PRIVATE_TARGET ||--o{ REVIEW : grounds
  EXPERIMENT_MANIFEST ||--o{ REVIEW : records
~~~

Public task EXACT keys: \`format,pixels_l8,focus_box,anchor_px,raster_digest,budget_pixels\` (72x72 uint8), no action label, template, source family, or target curve. \`PrivateTarget\`: \`pair_id,member_id,split,family,scene_kind,expected_action,target_region,excluded_region,evidence_policy\`. Only the Arena evaluator consumes private fields, after the unmodified Model emits the candidate graph and decisions. The labels here refer to finite, visibly specified, procedural target strokes: absent successor outside the bounded gap is **synthetically declared stop**, NOT evidence that an arbitrary real drawing stops. Meaningfully unknowable owners require \`hold\`.

CC-02 study split: development 6 opposite-action pairs across slanted/T-junction/curved/low-contrast/parallel/branched scenes; confirmation 6 different noncardinal arc-template pairs. Control examples: ambiguity, true stop, neutral peripheral ink (3 scenes, outside 6 pairs). **Rotation-only versions are not confirmation.** Binary pair local focus raster/anchor identical and public raster digest different. Two crops sharing a pair form ONE evaluation unit; each family source is a procedural template, not a different authentic artwork.

Confirmation is sealed by a reproducible public-manifest hash and the generator version, **not evaluated on v2 and not exposed to training selectors**. This seal does not mean cryptographic access control or statistically independent source-family; the generator is source-readable. Do not run Model on confirmation before final code/config freeze. Never change the confirmation grammar to match observed predictions.

### Frozen generator manifest (canonical sorted compact JSON; 6 validation receipts)
- development \`4d796ebc0467153a119a233724e6f9cfc1b8509b65c77bd101c31da3a3d61dcd\`
- confirmation \`ce2f33f187dcb5155b3e66c85f03dd7650e3a946889064cfaeb694db4b86fd36\`
- Code version \`arena-contextual-contour-cc02-v1\`. Reviewer retains exact pair input digests; private labels excluded from publicly printed pair-manifest output.

## 3. Experiment — PRE-change diagnostic, settings and records

**Frozen Model CC-01/v2 settings**: \`threshold=200, max_gap=8, max_nodes=16, max_pixels=8192, max_edges=64\`, 72x72 L8. A1/B/B-shuffle share the SAME candidate graph instance/hash within each member, and no oracle is passed to the selector. \`contextual_contour_cc02_pilot.py --development\` refuses models whose \`VERSION\` is not \`contextual-contour-cc01-v2\`. The on-repo runner computes SHA from the current Model and Arena checkout and saves complete per-member pre-review receipts, independent reviews and metrics to a local file without overwriting.

**Actually observed in local isolated mirror of v2 algorithm with numpy 2.3.5** on 2026-10-14 (not yet full source checkouts, CI or all unit tests):

| Arm | Correct members /12 | Both-correct pairs /6 | False continues on stop | Hold |
|---|---:|---:|---:|---:|
| A1 local | 6 | 0 | 6 | 0 |
| B context | 7 | 1 | 0 | 0 |
| B-shuffle | 6 | 0 | 0 | 0 |

B per-pair positive (continue) failures:
| Pair | stimulus | Current B decision | evidence stage | root cause inferred from public graph |
|---|---|---|---|---|
| dev-00 | diagonal/slanted neighbor | STOP (wrong) | relation | context Node detected, but orientation evidence rejects Edge |
| dev-01 | T-junction distal path | STOP (wrong) | candidate | entire branching component rejected as non-line-like |
| dev-02 | curved successor | STOP (wrong) | relation | context Node present, but no supported continuation relation |
| dev-03 | low-contrast visible line | STOP (wrong) | candidate | threshold=200 discards intensity=218 |
| dev-04 | valid forward plus parallel neighbor | CONTINUE (right) | success | one supported distal successor |
| dev-05 | Y/branched successor | STOP (wrong) | candidate | branching component rejected as non-line-like |

All six STOP cases: B answered STOP. Independent controls: ambiguous HOLD correct, true-stop STOP correct, neutral-context STOP correct (3/3). This is *only* finite visible-synthetic evidence. A1 6/12, B 7/12, B-shuffle 6/12, unlike prior simple CC-01 dev where B=12/12. Review failure tag \`candidate_missing\` means no *admitted context Node with center in the oracle target bounding region*, not definitive proof that all target pixels are invisible.

The local-mirror report is stored outside the repo; it is **not** claimed to be a run of the exact GitHub checkout HEAD. To promote evidence: run the published Arena runner against pinned pair of working tree SHAs; verify pair hash, selected arms, unit tests, Ruff, and compare metrics. All required tests must be run, not inferred from file existence.

Run in WSL2/bash with matching Model/Arena worktrees:
~~~bash
# ImageProgram root:
uv sync --locked --extra render
uv run python scripts/check.py
uv run ruff check .

# Arena root with matching ImageProgram importable:
python -m unittest discover -s tests -p 'test_contextual_contour_cc02.py'
python -m adapters.imageprogram_reference.contextual_contour_cc02_pilot \
  --seal-confirmation --out /tmp/cc02-confirmation-seal.json
python -m adapters.imageprogram_reference.contextual_contour_cc02_pilot \
  --development --out /tmp/cc02-development-v2.json
~~~
The seal command does NOT import ImageProgram. The development command imports and pins v2. Run files contain source SHA, private reviews and raw decisions; KEEP LOCAL by default, only publish aggregates, non-sensitive hashes and failure summaries.

## 4. Hypothesis judgment / CC-02c

- **SUPPORTED**: harder procedural scenes expose a repeatable two-stage limitation: 3/6 intended continuation cases lack an admitted distal Node, 2/6 contain a distal Node but no accepted continuation Edge, 1/6 passes.
- **NOT SUPPORTED**: robust contextual contour grouping, correct termination in real art, novel skill learning, held-out generalization or quality/legal ink execution.
- **Interpretation**: v2 interprets absent accepted successor as STOP, conflating missing observation with true termination. Changing selector alone cannot repair Node loss. Adding a global threshold alone cannot repair T/Y topology and may increase false joins. Stage-by-stage comparisons and held-out gate therefore remain necessary.
- **NEXT only after CC-02c SHA-valid full run**: branch from this state for CC-02d evidence-preserving skeleton chain segmentation / branch-aware graph and explicit \`hold\` on unsupported or ambiguous evidence. Test same fixed development inputs, then freeze code before sealed confirmation.
- **DO NOT**: retune based on confirmation results, infer semantic ownership from generator-only private labels, claim path coverage on a decision-only experiment, or merge Drafts without review.

Engineering goal remains >=5/6 BOTH-correct on genuinely unused confirmation pairs with >=2 pairs advantage over strong collinearity-only baseline C, zero forbidden joins and correct holds on ambiguity controls. N=6 is not a statistical generalization certificate: Wolfram exact binomial tail P(K>=5|iid p=.5)=7/64=.109375, assumptions not demonstrated here.
