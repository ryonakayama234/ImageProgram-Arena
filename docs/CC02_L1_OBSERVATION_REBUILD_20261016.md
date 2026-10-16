# CC02-L1 recovery route: pinned source re-observation and 27-case hash audit

Status: **IMPLEMENTED, NOT EXECUTED AGAINST THE HISTORICAL OBSERVATION BANK** (2026-10-16 JST). This supplements [L1 blind review gate](CC02_L1_BLIND_REVIEW_GATE_20261016.md) rather than altering frozen G1/P02 thresholds. Model [#109](https://github.com/ryonakayama234/ImageProgram/pull/109), Arena [#45](https://github.com/ryonakayama234/ImageProgram-Arena/pull/45).

## Specific obstacle resolved at the interface level

The original full `observation.json` is not committed to GitHub. Its archived canonical SHA-256 is `01d4cb52b2cc62f86c06730b9bc00982e03209ad14b2c7b519f0d1d1796b0af0`. Source code includes measured `observation_seconds` in each row, so a source-exact repeat usually **cannot** match the original byte/canonical JSON SHA. It would be dishonest to label the new JSON as an exact copy.

**Solution implemented:** create a new observation *only from the original frozen Model+Arena code heads*, compare all 27 code/head and case identities, status, fragment digests/counts and pair counts against the historical GitHub evidence file, and write a **new scope with a new canonical observation digest**. Preserve the old digest as a distinct reference and mark the human-review packet `REBUILT_VERIFIED_CASE_FINGERPRINTS_NOT_ORIGINAL_BYTES`.

The original original-observation SHA is not asserted as reproduced. The archived aggregate does not independently bind every per-pixel P02 arm-support coordinate; reproduction derives support from exactly pinned deterministic code and original public rasters, with full code provenance checked. No claim of cryptographic identity of every original support pixel absent a saved original observation file. A mismatched fragment, missing/extra row, changed code identity or changed pair universe fails closed.

## Frozen contracts

| Asset | Recorded identity |
|---|---|
| Original Model execution HEAD | `531d78d365b4c7882a3898a3e11fda3e809b4857` |
| Original Arena observation/prediction HEAD | `7a7c26815472ae2bc866415f04c5d9888f0d4021` |
| Historical machine-readable evidence Git blob SHA1 | `7427a2e8d51773916e11bdd19da818e9a2f79167` |
| Historical observed fragment total | 32 |
| Historical pair total | 37 |
| Historical scenes | 27 (17 empty, including two budget abstentions) |
| Blind L1 review scope | obs-02:3, obs-10:6, obs-11:1 |

The comparison code never imports the old source-label grade module, never calls G0/G1 path selection, and does not present archived label counts to the human reviewer. Full source evidence is only consumed by the administrative recovery stage. No original confirmation images generated or scored.

## System

~~~mermaid
flowchart TD
 P["Frozen Model+Arena code and unchanged 27 public synthetic rasters"] --> O["New source-exact observe (NEW timing fields)"]
 E["Historical GitHub evidence; verified blob SHA"] --> V["27-case exact source/code/Fragment/status/pair audit"]
 O --> V
 F["Original 10-pair scope"] --> V
 V -->|MATCH| S["Recovered scope: NEW digest and OLD reference digest"]
 V -->|MISMATCH| X["FAIL: do not create review packet"]
 S --> I["New branch review prepare: 3 PNG+SVG+JSON packets"]
 I --> H["Externally anchor packet SHA before human review"]
 H --> A["Independent reviewer A/B on L0/L1 only"]
~~~

## ER

~~~mermaid
erDiagram
 ORIGINAL_EVIDENCE ||--o{ HISTORICAL_SCENE_FINGERPRINT : records
 NEW_OBSERVATION ||--o{ REOBSERVED_SCENE_FINGERPRINT : contains
 HISTORICAL_SCENE_FINGERPRINT ||--|| REOBSERVED_SCENE_FINGERPRINT : must_match
 ORIGINAL_SCOPE ||--|| RECOVERED_SCOPE : derives
 RECOVERED_SCOPE ||--|| REVIEW_PACKET : identifies
 REVIEW_PACKET ||--o{ REVIEWER_RESPONSE : constrains
~~~

## WSL2/bash execution — three clean source roots

Use clean **historical** Arena HEAD, historical Model HEAD and a separate current review-branch Arena checkout. Do not run the historical `observe()` function from the newer review branch: its `source_identity()` verifies the exact code HEAD. Use the correct Python 3.12 locked environment; save all JSON outside checkout roots. File paths below are examples.

~~~bash
export MODEL_OLD=/work/ImageProgram-G1-original
export ARENA_OLD=/work/ImageProgram-Arena-G1-original
export ARENA_REVIEW=/work/ImageProgram-Arena-L1-draft
export REPRO=/work/cc02-l1-evidence
export PYTHONPATH="$ARENA_OLD:$MODEL_OLD/src"

# Pin and verify git commit objects and clean checkouts first.
git -C "$MODEL_OLD" rev-parse HEAD
git -C "$ARENA_OLD" rev-parse HEAD
git -C "$MODEL_OLD" status --porcelain
git -C "$ARENA_OLD" status --porcelain

cd "$ARENA_OLD"
"$MODEL_OLD/.venv/bin/python" -m adapters.imageprogram_reference.contour_relation_g1_observed \
  --phase observe --out "$REPRO/rebuilt-observation.json"

# Switch imports to review branch but KEEP a matching Model code path.
export PYTHONPATH="$ARENA_REVIEW:$MODEL_OLD/src"
cd "$ARENA_REVIEW"
"$MODEL_OLD/.venv/bin/python" -m adapters.imageprogram_reference.contour_l1_recover_scope \
  --observation "$REPRO/rebuilt-observation.json" \
  --frozen-scope adapters/imageprogram_reference/cc02_l1_review_scope.json \
  --historical-evidence docs/evidence/cc02-g1-python312-observed-p02-20261016.json \
  --out "$REPRO/rebuilt-scope.json"

# The script prints REBUILT_OBSERVATION_SHA256 (new) and RECOVERED_SCOPE_SHA256.
# Publish both externally before accepting any reviewer response.
"$MODEL_OLD/.venv/bin/python" -m adapters.imageprogram_reference.contour_l1_review \
  --phase prepare \
  --observation "$REPRO/rebuilt-observation.json" \
  --observation-sha256 NEW_REBUILT_OBSERVATION_SHA256 \
  --scope "$REPRO/rebuilt-scope.json" \
  --out "$REPRO/packet-new"

# Publish the BLIND_PACKET_SHA256 before sending independent A and B packets.
# No model prediction or source-answer label is included.
~~~

Outputs use exclusive file creation. Prior canonical original receipt and held-out confirmation stay unchanged. The new packet is distinctly labelled a verified **reconstruction**, not the originally published JSON.

## Experiment evidence and decision

- New `contour_l1_recover_scope.py` and `test_contour_l1_recover_scope.py`: local Python 3.13.5 **9/9 PASS**, `py_compile` PASS; source code and tests uploaded with exact Git blob identities.
- Negative tests cover different source file SHA, changed case ID, altered Fragment fields, missing even empty scenes, wrong UNKNOWN denominator, changed 10-pair scope, and changed timing (which correctly produces a distinct new canonical digest).
- New code run against full authentic Python 3.12 Model/Arena checkouts, full suites/Ruff, actual 27-scene replay and packet rendering: **NOT RUN this turn**.
- Human independent annotations, inter-reviewer reconciliation, L2 artist/task intent, R1 path selection, original confirmation, Motor and Skill learning: **NOT RUN**.

**SELECT** case-fingerprint-gated reconstruction to unblock the audit without inventing the lost original JSON. **REJECT** silently normalizing or declaring the original canonical SHA recreated, claiming source-stroke IDs equal artist intent, or scoring UNKNOWN/empty scenes as success. **DEFER** G1 promotion, G0/G1 rescore and R0/R1 path study until actual independent reviews. Both PRs remain Draft/unmerged.
