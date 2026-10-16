# Arena CC-02-G1 — DEV-only fixed public Fragment comparator (2026-10-16)

**Status: research-only source-author synthetic geometry bank and separate PREDICT/GRADE implementation. Actual current controlled evidence: local smoke on Python 3.13.5 with CC01-compatible stub. Authoritative full Python 3.12 whole-repository run NOT RUN.**
Model counterpart: [Model G1](https://github.com/ryonakayama234/ImageProgram/blob/research/cc02-g1-fixed-fragments/docs/CC02_G1_FIXED_FRAGMENTS_20261016.md). Issues [#101](https://github.com/ryonakayama234/ImageProgram/issues/101), [#99](https://github.com/ryonakayama234/ImageProgram/issues/99). W0 full reproducibility: [Arena #43](https://github.com/ryonakayama234/ImageProgram-Arena/pull/43), [Model #107](https://github.com/ryonakayama234/ImageProgram/pull/107).

## Hypothesis, test fixture and integrity
Test isolated G0 vs G1 on the exact same tuple of read-only public Fragment nodes. The independent **Arena-owned** grading module has source-author relation labels for six unambiguous edge pairs and three explicitly UNKNOWN candidate pairs across eight constructed geometry scenes. This is not a blinded annotator or artwork evaluation. Public identifiers `gdev-00` to `gdev-07` do not encode positive/negative/unknown answer polarity.

This initial smoke fixture directly constructs Fragment objects and **does not** pass genuine P0/P02 image observations; correctness on it does not establish a perception or safe contour capability. Score possible_continuation for source-derived positives, disallow confident continuation on negatives. UNKNOWN pairs are retained but not credited as path success. Keep G1 alternatives, particularly competing branches; no selected path or R action is recorded.

## System
~~~mermaid
flowchart TD
 G["Source-author DEV fixture maker"] --> PUB["PUBLIC fixed Fragment objects, neutral task IDs"]
 G --> PRIV["PRIVATE G-only relation labels, no artist intent claim"]
 PUB --> A["G0 baseline, frozen _relation"]
 PUB --> B["G1 geometry relation hypotheses"]
 A --> S["PREDICT saved JSON with common Fragment SHA"]
 B --> S
 S --> H["External SHA retained BEFORE GRADE"]
 H --> V["Separate GRADE process: label-specific correct/false joins/UNKNOWN"]
 PRIV --> V
 V --> E["Saved DEV-only diagnostic, no confirmation"]
~~~

## ER / data
~~~mermaid
erDiagram
 PUBLIC_TASK ||--|{ PUBLIC_FRAGMENT : contains
 PUBLIC_TASK ||--|| FRAGMENT_SHA : identifies
 FRAGMENT_SHA ||--o{ G0_EDGE : supports
 FRAGMENT_SHA ||--o{ G1_RELATION : supports
 PREDICTION_RECEIPT ||--o{ G1_RELATION : persists
 PREDICTION_RECEIPT ||--|| EXTERNAL_SHA : gates
 PRIVATE_SOURCE_LABEL ||--o{ GRADE_ROW : checks
 EXTERNAL_SHA ||--o{ GRADE_ROW : authorizes
~~~

Prediction JSON: protocol, eight task identities, public Fragment SHA, both G0 and G1 relations, G1 status/pair-work counts, explicit original confirmation NOT_RUN and independent annotation NOT_RUN. GRADE JSON: six scored source-derived pairs plus three UNKNOWN pairs; correct/incorrect for G0 and G1, no selected-path/real-art claim. SHA is canonical JSON SHA256 (not pretty file-byte SHA). Private labels are imported exclusively from the GRADE function. The prediction code cannot receive private labels through its G1 API.

## Execution and full negative accounting
- New Model G1 module 8/8 tests PASS under local Python 3.13.5 compatible CC01 stub (NOT source-exact whole P02 checkout).
- Arena trial tests **3/3 PASS** under the same local stub: eight named public tasks, SHA tamper rejection, no private label in public prediction, source-author diagnostic aggregate. `py_compile` PASS. These are development mechanics, NOT independent source validation.
- PREDICT CLI and GRADE CLI implemented as separate invocations with new-file output and user-supplied external receipt digest. **At this stage full authoritative source checkouts, Python 3.12 full suites/Ruff, confirm6, real artwork, R1, Motor and learned Skill are NOT RUN.**
- Pure hand-built geometry diagnostic contains six conditionally scored pairs: G0 4/6, G1 6/6 in the smoke. The 2/6 improvement is an **in-sample source-author proxy** and is not a generalization or semantic accuracy claim. The three UNKNOWN pairs are not added to the six-pair accuracy denominator. No artist-selected branch label is available.
- Test statuses on the fixed geometry fixture: eight small tasks within default pair/relation budget; overflow is separately unit-tested. CPU and actual Motor costs NOT RUN. No original W0 receipt replaced.
- Distinct failure gate: any false confident continuation on the three negatives, any hidden positive/negative polarity in public IDs, any mismatch of frozen input sha between G0 and G1, or unanchored GRADE is FAIL. We do not silently convert overflow or HOLD to success.

## Reproduction: separate processes, fresh SHA anchor
Use matching Model/Arena research branches, clean pinned Python 3.12 checkouts, and full Model/Arena suite from the existing W0 gate. Never run original confirmation. Source code follows standard Arena Python imports.

~~~bash
cd /path/to/ImageProgram-Arena
export PYTHONPATH="$PWD:../ImageProgram/src"
../ImageProgram/.venv/bin/python -m adapters.imageprogram_reference.contour_relation_g1_trial \
  --phase predict --out /tmp/g1-predict-unique.json
# Capture the printed canonical SHA and publish it to Model Issue #101 BEFORE GRADE.
../ImageProgram/.venv/bin/python -m adapters.imageprogram_reference.contour_relation_g1_trial \
  --phase grade --receipt /tmp/g1-predict-unique.json \
  --expected-sha256 EXTERNALLY_RETAINED_PREDICTION_SHA --out /tmp/g1-grade-unique.json
~~~

These paths are examples; exclusive-write semantics reject existing output files. Separate invocations still need an externally witnessed digest publication; command ordering alone is insufficient integrity evidence.

## Decision
**SELECT:** retain tiny source-derived geometry diagnostic and pairwise stage-isolation, no baseline mutation. **REJECT:** promote hypothetical edge to semantic ownership/actual contour path, ignore three UNKNOWN pairs, or report 6/6 as a real-art result. **DEFER:** real authentic P0/P02 Fragment G-only audit, blinded annotation (#99), fixed-Relation R1 comparison (#101), CC-03, Skill, confirm6, merge/paid CI. W0 remains PASS only for its exact previously pinned heads; adding G1 requires a fresh full regression.

Wolfram exact two-sided sign reference for 2 improvements/0 regressions is 0.5 under independent paired-discordance assumptions; these fixtures are deliberately code-authored and correlated, so significance is not claimed.
