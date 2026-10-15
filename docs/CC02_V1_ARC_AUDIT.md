# CC-02-V1 — Development target-arc audit (research, NOT Gate V complete)

**Date:** 2026-10-15 JST  
**Owner:** ImageProgram-Arena independent evaluation surface  
**Issue:** [Model #99](https://github.com/ryonakayama234/ImageProgram/issues/99)  
**Counterpart:** [Model CC-02-V1 handoff](https://github.com/ryonakayama234/ImageProgram/blob/research/cc02-v1-arc-audit-20261015/docs/CC02_V1_AUDIT_HANDOFF.md)  
**Status:** IMPLEMENTED diagnostic code; component unit tests PASS on isolated local environment; exact GitHub checkout and full suite NOT RUN.

## 1. System (implemented)

~~~mermaid
flowchart LR
  S["Existing Arena DEV generator, version v1"] --> P["PUBLIC: L8, focus, anchor, budget"]
  P --> M["Frozen Model CC-01/v2 observe_graph + select B"]
  M --> D["Decision receipts computed before private review"]
  D --> V["Arena cc02_arc_review"]
  P --> V
  A["Arena-only source-derived DEV target main arcs"] --> V
  V --> C["Target pixels covered by accepted v2 components"]
  V --> G["Candidate -> continuation Edge -> action stages"]
  G --> L["Experiment ledger + Decision"]
  S -. "confirmation generator unchanged, NOT SCORED" .-> X["sealed confirmation"]
~~~

No source-art images, personal metadata, hidden real-art labels or confirmation prediction enters the model. The auditor is intentionally independent of the old *bounding-region center* check; it reconstructs 8-connected pixel supports from the PUBLIC raster and checks v2 node index, pixel count and intensity against the frozen candidate graph. Any mismatch causes an explicit error, not a silent positive.

**Limitations:** The six path coordinate sequences were transcribed from the synthetic development generator after previous results were known. They are **source-derived, unblinded procedural annotations**, NOT pre-registered independent human annotation, NOT proof of real illustration intent and NOT a new held-out dataset. V2 does not expose selected Edge IDs, so correct CONTINUE action is not verified target-path success.

## 2. ER/Data v1 (additive research evidence)

~~~mermaid
erDiagram
  PUBLIC_DEV_TASK ||--o{ V2_FRAGMENT : generates
  V2_FRAGMENT ||--o{ PIXEL_SUPPORT : verified_by
  PRIVATE_DEV_MAIN_ARC ||--o{ ARC_AUDIT : grades
  V2_CANDIDATE_GRAPH ||--o{ ARC_AUDIT : examined_by
  V2_DECISION_RECEIPT ||--o{ ARC_AUDIT : reviewed_after
  EXPERIMENT_RUN ||--o{ V2_DECISION_RECEIPT : records
  EXPERIMENT_RUN ||--o{ ARC_AUDIT : records
  EXPERIMENT_RUN ||--|| RESEARCH_DECISION : informs
~~~

New Arena-private implementation: `adapters/imageprogram_reference/cc02_arc_review.py`.
- `PrivateArc`: `pair_id,member_id,expected_action,path` (development-continue main path only; junction side-arms are not the main target arc).
- `ArcAudit`: `public_sha256,candidate_set_sha256,annotation_sha256,target_arc_pixels,arc_coverage_all_context_nodes,target_node_coverage,eligible_target_nodes,selected_local_neighbor,decision_action,diagnostic_stage,coverage_tolerance_px,min_single_node_coverage,path_edge_receipt`.
- `Experiment`: `decision_receipts_before_review,receipt_sha256,stage_counts,confirmation,real_art,source_review`. Receipts are materialized before private review but **not cryptographically timestamped or committed before review**.
- Contract: target pixel support is endpoint-inclusive synthetic rasterization, not inferred author brushstroke history. Coverage uses a 1.0-pixel Euclidean tolerance. A single v2 context Node needs >=0.5 target-arc coverage; if only the UNION of fragments has that support, mark `UNRESOLVED_FRAGMENTED_TARGET`, not `P_CANDIDATE_ABSENT`. No unknown can be silently coerced into P/G/R.
- `P_CANDIDATE_ABSENT`: no eligible context node, target support also insufficient in union.
- `G_CONTINUATION_EDGE_ABSENT`: target node admitted and a local neighbor selected, but no `possible_continuation` Edge between them.
- `R_SELECTION_FAILURE`: target edge exists but action not CONTINUE.
- `ACTION_CORRECT_PATH_EDGE_UNOBSERVED`: CONTINUE action correct; v2 lacks ordered edge receipt.
- `UNRESOLVED_LOCAL_PATH`: local neighbor was not selected.

## 3. Experiment: actual work vs outstanding checks

**Historical pinned parent GitHub heads (NOT checked out in local runner):**
- Model: `0f3df28b1c1c535c96db4dc05ab8d1070e649d85`
- Arena: `143ebc615486a4f3a86c1b675ed28f77b28d44f1`
- Historical DEV manifest from published generator: `4d796ebc0467153a119a233724e6f9cfc1b8509b65c77bd101c31da3a3d61dcd`.
- Frozen model args: `threshold=200,max_gap=8,max_nodes=16,max_pixels=8192,max_edges=64`.
- Reviewer args: `coverage_tolerance_px=1.0,min_single_node_coverage=0.5`.
- Local reproduction: the code read from GitHub was manually reconstructed into an isolated scratch environment with NumPy 2.3.5 and Python 3.13.5; **NOT** an actual GitHub checkout (repository targets Python >=3.12,<3.13). No claim of environment equivalence.

**Locally observed, reconstructed-v2 DEVELOPMENT ONLY:**

| Pair | Source-derived main arc pixels | Context target coverage | Classification |
| --- | ---: | ---: | --- |
| dev-00 slanted | 10 | 1.000 | G_CONTINUATION_EDGE_ABSENT |
| dev-01 T branch | 11 | 0.000 | P_CANDIDATE_ABSENT |
| dev-02 curve | 11 | 1.000 | G_CONTINUATION_EDGE_ABSENT |
| dev-03 L8=218 weak stroke | 11 | 0.000 | P_CANDIDATE_ABSENT |
| dev-04 parallel distractor | 11 | 1.000 | ACTION_CORRECT_PATH_EDGE_UNOBSERVED |
| dev-05 Y branch | 11 | 0.000 | P_CANDIDATE_ABSENT |

- Reviewer result: P 3 / G 2 / correct-action-with-unobserved-path 1; agrees with the historical 3/2/1 counts, **without treating the old bbox heuristic as ground truth**.
- Locally reconstructed complete DEV pair manifest **exactly equals** historical `4d796ebc...`; baseline A1=6/12, B=7/12, B-shuffle=6/12 and B both-correct pairs=1/6 agree with historical reports. This does **not** replace SHA-pinned checkout execution.
- SHA256 of local pre-review receipt content: `bafc3a935ce45257d695ae72ee2601ec0b87f31700fff528f4c7292471a0e0b2`.
- Local unit tests: `PYTHONPATH=. python -m unittest discover -s tests -p test_cc02_arc_review.py -v` -> **6 PASS**; focused synthetic/stub test, not full suite.
- The **old generator, candidate model, confirmation manifest/labels and existing v2 baseline are unchanged**.

**NOT RUN / pending:**
- Real complete checkout of either repository at the pinned HEAD: NOT RUN (container DNS for github.com unavailable).
- Python 3.12 locked environment, all suites, Ruff, CI: NOT RUN; no paid CI requested.
- Human-independent review/adjudication of source arcs: NOT RUN.
- Full 12-member stage review with forbidden/STOP path audit: NOT RUN (six DEV-continue cases only).
- Confirmation six pairs: NOT SCORED. Real-art ROI/Motor/Canvas/Skill: NOT RUN.

To reproduce with real pinned GitHub worktrees on WSL2 after resolving network access:

~~~bash
# run from Arena repository root; install pinned Model editable into same Python 3.12 environment
PYTHONPATH=. python -m unittest discover -s tests -p 'test_cc02_arc_review.py' -v
PYTHONPATH=. python -m adapters.imageprogram_reference.cc02_arc_review \
  --development --out /tmp/cc02-v1-arc-audit.json
# Run full suites/Ruff and unchanged legacy pilot independently.
# Do NOT score confirmation or silently overwrite existing evidence.
~~~

## 4. Decision (2026-10-15)

- **SELECT:** add a source-arc-based diagnostic independent of the old Node-center-in-bbox proxy; require public graph↔pixel-support verification, provenance and explicit unknown/path-unobserved statuses. Retain historical results.
- **REJECT NOW:** declaring #99 complete or blindly treating the source-derived review as independently annotated natural artwork; treating 1 correct action as verified ordered path.
- **DEFER:** P1/G1/R1 implementation, integration and held-out confirmation until GitHub checkout provenance and independent review are improved.
- **REVISIT:** if the exact full checkout differs, if target support differs under independent annotations, if fragmented subarcs need a path-level candidate adequacy definition, or if ambiguous full public inputs make the binary action unidentifiable.

**Project next:** finish #99: full paired checkout, full suites, independent review/adjudication, failure ledger including STOP cases, then make #100/#101 allocation decision.
