# CC-01 / ImageProgram #96 — Arena独立評価・データ構造・実測・判断
2026-10-14 JST | Decision-only synthetic prototype. No real-art target validation, no Canvas, no Replay. Parent: https://github.com/ryonakayama234/ImageProgram/issues/96
Arena Draft https://github.com/ryonakayama234/ImageProgram-Arena/pull/36 ; Model Draft https://github.com/ryonakayama234/ImageProgram/pull/97
Model detailed system/data/results https://github.com/ryonakayama234/ImageProgram/blob/research/contextual-contour-cc00/docs/CONTEXTUAL_CONTOUR_CC01_IMPLEMENTATION.md

## System: independent oracle boundary

~~~mermaid
flowchart TD
  G["Arena: procedural generator and PRIVATE label"] --> P["Public grayscale raster+focus+anchor only"]
  G --> Q["PrivateAnswer: correct_action/source/template/split"]
  P --> M["ImageProgram: graph from raster, A1/B/B-shuffle"]
  M --> R["Immutable pre-review decisions, same candidate hash per member"]
  R --> V["Arena: independent evaluator compares decision with hidden label"]
  Q --> V
  V --> X["Decision counts + pair lineage + failures"]
  R -. "Not attempted" .-> W["fit / Motor / Canvas / Replay"]
~~~

No import of Model scoring algorithm in the independent evaluator; it reads decision fields after the selector runs. The optional pilot orchestrator imports Model module to run *inference*, then passes receipts and Arena-only truth to evaluator. Never feed correct_action/source-family/template-family back to selector. Original private image assets and annotations are not committed.

## Data / proposed compact lineage graph

~~~mermaid
erDiagram
  FAMILY ||--o{ PAIR : contains
  PAIR ||--|{ MEMBER : contains
  MEMBER ||--|| PUBLIC_TASK : provides
  MEMBER ||--|| PRIVATE_ANSWER : labels
  PUBLIC_TASK ||--o{ DECISION_RECEIPT : generated_by
  DECISION_RECEIPT ||--|| PRIVATE_REVIEW : graded
  PRIVATE_ANSWER ||--|| PRIVATE_REVIEW : oracle_for
~~~

PublicTask EXACT keys: format, pixels_l8 (72x72 uint8), focus_box (ROI-local half-open), anchor_px, raster_digest, budget_pixels. PrivateAnswer: pair_id, member_id, correct_action, source_family, template_family, split, label_version. Review: member_id, pair_id, arm, predicted_action, correct, false_join, hold, reason, candidate_set_sha256. Manifest: pair_id, local_digest, two distinct public raster digests, template_family, split. No Model selector receives PrivateAnswer.

Dataset = 6 development pairs with left-right cardinals; 6 rotation_probe pairs that are transpose of same generator, NOT independent confirmation. Local evidence is byte-identical within every pair; opposing truth and changed context are verified before admission. No real image or Google Drive raw material used in CC-01. No authenticated right/license inference from file names.

## Experiment / exact local isolated results

Equivalent local modules executed with numpy 2.3.5 on 2026-10-14. A1 local vs B context vs B-shuffle corrupted context-candidate correspondence, same graph hash within each member; finite budgets threshold=200, gap=8, nodes<=16, pixels<=8192, edges<=64. Decision_only is not World_execution.

| split | arm | correct members | both-correct pairs | false joins | holds |
|---|---|---:|---:|---:|---:|
| development (6 pairs) | A1 | 6/12 | 0/6 | 6 | 0 |
| development (6 pairs) | B | 12/12 | 6/6 | 0 | 0 |
| development (6 pairs) | B-shuffle | 6/12 | 0/6 | 0 | 0 |
| rotation_probe (6 pairs) | A1 | 6/12 | 0/6 | 6 | 0 |
| rotation_probe (6 pairs) | B | 12/12 | 6/6 | 0 | 0 |
| rotation_probe (6 pairs) | B-shuffle | 6/12 | 0/6 | 0 | 0 |

Pair-preserving manifest SHA256 of canonical JSON (not private artwork fingerprint):
- development = 710fc323f1a9862a6716cb61ad7b3aecd13806cc27aa05b5f79af757af4002a8
- rotation_probe = 41ccab21a7af9b7ba661071d4099b4e554401f58732c07ebe1293698fae1826b

Locally targeted 4 Model tests and 2 Arena tests passed. Full GitHub source checkout tests, entire Arena suite, CI and actual Canvas not run in this session. The joined pilot command in this branch emits complete post-decision review and hashes when executed in a proper WSL2 checkout:
~~~bash
python -m adapters.imageprogram_reference.contextual_contour_cc01_pilot --split development --out /tmp/cc01-development.json
python -m adapters.imageprogram_reference.contextual_contour_cc01_pilot --split rotation_probe --out /tmp/cc01-rotation.json
~~~
Written receipts MUST be kept local and are not safe raw data to publish by default. CI paid execution is not requested. Script refuses overwriting.

## Independent decision

- Positive narrow evidence: context-dependent collinear distal line allows this simple graph look-ahead to distinguish continue from stop while A1 cannot classify both labels given byte-identical local data.
- Alternative mechanism: trivial continuation cue, not learned topology/semantic grouping. No junctions, no occluded author-intended paths; generator and selector co-designed.
- Confirmation status **NOT RUN**: a rotated copy is correlated and does not meet original #96 request for separate template-family heldout six pairs. Original success gate remains pending. No claim of p-value, population reliability, generalization, learned skill or artist acceptance.
- Real target selection/covered-arc/contamination/line appearance, Motor legality and Replay: **NOT RUN**; source-family transfer: **UNKNOWN**.
- Fail taxonomy for next study: no_oracle_leak_check, candidate_missing, non_line_like, wrong_target, false_join, premature_stop, misleading_neighbor, ambiguous_hold, budget, fit, compile, motor, replay, independent_evaluator.
- Next dataset first: inject branching, T/Y junctions, occlusion gaps and *same amount of peripheral ink with different topology*, plus target/excluded arcs and real artwork. Freeze and hash an untouched genuinely separate confirmation set BEFORE modifying v2 thresholds.

System and ER must be updated with every new stage; preserve historic CC-00 contract at docs/CONTEXTUAL_CONTOUR_CC00_EVALUATION.md.
