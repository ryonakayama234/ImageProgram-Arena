# CC-02-R / Independent ordered-visible-contour grade v0

Date: 2026-10-17 JST. **Research-only scorer: synthetic contract smoke PASS; frozen 17-case independent grading NOT RUN.** Parent: [Model Issue #101](https://github.com/ryonakayama234/ImageProgram/issues/101). Separate L1 blind review: Model #109 and Arena #45.

## Research question

Can ImageProgram infer a single ordered visible open contour from a public raster and start endpoint and recognize when it truly ends? This is a bounded synthetic unique-path test, not general art understanding, drawing, or a learned Skill.

## System / data flow

~~~mermaid
flowchart TB
 A["Arena task factory: public and private"]
 B["Public raster + start + frozen candidate graph"]
 C["ImageProgram P/G/R (NOT in this PR)"]
 D["Saved candidate paths, selected path, endpoint evidence"]
 H["Externally anchored prediction SHA"]
 G["Arena independent scorer (THIS PR)"]
 E["Private accepted path / control"]
 F["Per-case grade and totals"]
 A --> B --> C --> D --> H --> G
 A --> E --> G
 G --> F
~~~

Private acceptance never goes to the predictor. This scorer does not import ImageProgram, run inference, import a historical confirmation factory, invoke motor code, or load Google Drive/raw artwork.

## Data / ER

~~~mermaid
erDiagram
 PUBLIC_MANIFEST ||--o{ PUBLIC_CASE : contains
 PUBLIC_CASE ||--|| CANDIDATE_GRAPH : fixes
 PUBLIC_MANIFEST ||--|| PRIVATE_MANIFEST : hashes
 PUBLIC_MANIFEST ||--|| PREDICTION_MANIFEST : hashes
 PRIVATE_MANIFEST ||--o{ PRIVATE_CASE : accepts
 PREDICTION_MANIFEST ||--o{ PREDICTION_CASE : decides
 PUBLIC_CASE ||--|| PRIVATE_CASE : case_id
 PUBLIC_CASE ||--|| PREDICTION_CASE : case_id
 PRIVATE_CASE ||--|| GRADE_ROW : measures
 PREDICTION_CASE ||--|| GRADE_ROW : measures
~~~

Three separate versioned JSON artifacts using protocol = arena-visible-contour-path-grade-v0:

- Public: protocol / split / cases. Case: case_id, family_id, raster_sha256, start_node, nodes, edges (id,u,v), candidate_graph_sha256. Graph SHA hashes only {nodes, edges}; source raster digest must be independently audited upstream.
- Private: protocol / public_sha256 / cases. Each case: case_id, kind, allowed_edge_paths, expected_goal, expected_reasons. One or more accepted ordered paths only for kind unique_path; controls cannot contain private accepted paths.
- Prediction: protocol / public_sha256 / cases. Each case: case_id, candidate_graph_sha256, candidate_paths, selected_path, goal_status, termination_reason, endpoint_evidence, work_units. Public endpoint_evidence is {node_id, observation_sha256, unresolved_continuations}.

Canonical SHA256 uses UTF-8 JSON with sort_keys=True, separators comma/colon, ensure_ascii=False, allow_nan=False. All three full-document hashes must be externally precommitted; CLI validates them and grade() rejects mismatches. All cases, graph IDs, path continuity and public/private field allowlists are checked. Outfile is exclusive-create and refuses overwrite.

A satisfied claim requires selected_path, public observation-bound endpoint evidence, zero unresolved continuations and verified_visible_endpoint termination. This is only a **syntactic claim**; independent private acceptance decides correctness. Unique-path success requires exact ordered path, correct goal and reason. Controls require no selected path and matching goal/reason. All-HOLD fails unique positives. False join is selection deviating from every accepted prefix. Proper prefix is incomplete without being a false join. Candidate availability, selected path, unique success, control success, premature satisfied and work cost are separate metrics.

## Execute (WSL2/Linux, no paid CI)

~~~bash
python -m adapters.imageprogram_reference.visible_contour_path_grade_v0 \
  --public /path/to/public.json --public-sha256 PRECOMMITTED_PUBLIC_SHA \
  --private /path/to/private.json --private-sha256 PRECOMMITTED_PRIVATE_SHA \
  --prediction /path/to/prediction.json --prediction-sha256 PRECOMMITTED_PREDICTION_SHA \
  --out /path/to/new-grade.json
python -m unittest tests.test_visible_contour_path_grade_v0 -v
~~~

The original frozen 17-case records have not been verified as directly compatible with these edge-ID artifacts. They require a separate audited conversion mapping and new derived hashes that point back to the original precommitted hashes. Never substitute a new converted file's digest for its historical source hash.

## Experiment ledger (actually executed locally, 2026-10-17)

- Python3.13.5 local isolated synthetic test suite: 9/9 PASS, py_compile PASS.
- Scenarios: correct unique path and ambiguous control; wrong branch; all-HOLD fails unique; disconnected path; missing case; private data in public record; parent hash mismatch; false satisfaction without endpoint evidence; disconnected private target.
- Local CLI smoke using 2 toy cases, authentic CLI, three matching canonical SHA values, new output file: PASS. Counts: cases=2, unique=1, control=1, unique_success=1, control_success=1, false_join=0, work_units=4.
- No exact historical 17-case grading; no Model inference improvement; no actual image drawing; no learned Skill; no original sealed confirmation read. Full repo tests and Ruff in authenticated Python3.12 source-exact GitHub checkouts: NOT RUN. Existing G1 test evidence does not carry over to this branch.

### Historical pre-registration — not scored

[Model Issue #101, fixed predictions](https://github.com/ryonakayama234/ImageProgram/issues/101#issuecomment-6227167106): 12 unique synthetic development cases (six geometric transpose pairs) and five termination controls. Recorded canonical SHA256:
- public: 5497ad7e31e9d1528a01b881f92da0655de81d1d24da40f783cfc05b6f95b374
- private: 476cb257de6f19f9248771ca5953e4510902d9913a75bacf91110d0f0a1517ba
- prediction: f01a79ba93e9634c9d096c9cd2886b9c7498d2e1a5f44cdd7e2a5d7ba5240813

The underlying JSON files were not present in the inspected repository branch. A hash is not the dataset, and outputs cannot be reverse-engineered from it. No synthetic or historical accuracy inference is claimed by this PR.

## Statistical guard / Wolfram evaluation

If n independent Bernoulli trials exhibit zero errors, the one-sided 95% exact upper probability is 1 - 0.05^(1/n): n=6: 0.3930; n=12: 0.2209; n=17: 0.1616; n=60: 0.0487. Six geometric families with paired transpose examples are not twelve independent sources. Report per case and family; do not cite these limits as model ability confidence intervals.

## Decision / next steps

SELECT: strict evaluator boundary and replay-safe grading contract.
DEFER: Model R1 or CC-03, 17-case outcome claims, skill promotion.
REJECT: fake reconstruction of original prediction JSON from a hash, all-HOLD success, source-private target leakage, reopening old confirmation, changing historical experiment receipts.

Next: obtain authentic fixed public/prediction/private artifact bytes, verify original SHA, implement an explicit audited research adapter for that actual record format, freeze scorer/config, grade all 17 cases without reinvoking ImageProgram, then decide whether P/G/R is the limiting component. Update System/ER/Experiment/Decision and original Issue #101 with true results and failures.
