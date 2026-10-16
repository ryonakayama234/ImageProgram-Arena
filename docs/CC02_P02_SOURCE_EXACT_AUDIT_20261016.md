# CC-02-P02 — Verified GitHub source modules, development-only candidate audit (2026-10-16)

**Status: SELECT research-only branch evidence bank for further tests; DO NOT MERGE or PROMOTE to G/R.** This is a source-exact **module-level** validation, not an entire repository clone, not the original full Python test matrices, not semantic perception, and not production readiness. Search keys: CC-02-P02, #100, audit-20261016, P0+P02, source-exact, branch-evidence. Replaces the earlier shim-only descriptive results for correctness claims; historical shim receipt remains archived unchanged.

## System and causal boundary
~~~mermaid
flowchart LR
 U["Arena public L8 + focus + budget"] --> P0["Frozen P0 CC01/v2"]
 U --> P2["P02 isolated junction arm bank"]
 P0 --> R0["Frozen B R0 decision (unchanged)"]
 P0 --> PRE["PREDICT receipt 27 / SHA anchored"]
 P2 --> PRE
 R0 --> PRE
 PRE --> GRADE["Arena GRADE, separate process"]
 O["Arena-private source masks/regions"] --> GRADE
 GRADE --> AUDIT["Candidate presence / excluded ink / budgets / decision"]
 AUDIT -. "not integrated" .-> FUT["#101 relation/path reasoning: separate study"]
~~~

## Research data / ER
~~~mermaid
erDiagram
 PUBLIC_INPUT ||--|| STRONG_GRAPH : frozen
 PUBLIC_INPUT ||--o{ ARM_HYPOTHESIS : observes
 ARM_HYPOTHESIS ||--o{ SHARED_JUNCTION : cites
 PUBLIC_INPUT ||--|| PREDICTION_RECEIPT : emits
 PREDICTION_RECEIPT ||--|| RECEIPT_SHA : sealed_before_grade
 RECEIPT_SHA ||--o{ SOURCE_MASK_REVIEW : authorizes
 PRIVATE_SOURCE_MASK ||--o{ SOURCE_MASK_REVIEW : grades_only
 SOURCE_MASK_REVIEW ||--|| DECISION_RECORD : informs
~~~
Data/version: original CC01/v2 `CandidateGraph` + research-only P02 `BranchObservation(ArmHypothesis[] with ownership=unknown, no selected edges, status, work proxy, evidence_sha256)`; Arena private labels remain grade-only. No changes to canonical P1/P2 wire, G/R0, Motor, Canvas, Replay, learned skills.

## Authenticated local source, exact GitHub blob identity
The container cannot resolve `github.com` for `git clone`. Five necessary source files were therefore reconstructed from the connected GitHub API and **each local `git hash-object` exactly matches the current GitHub blob SHA**:
| File | Git blob SHA |
|---|---|
| Model frozen `src/imageprogram/models/contextual_contour_cc01.py` | `f64f6799d4432064c06e80a723bebbc832c1c4f5` |
| Model `src/imageprogram/models/branch_contour_p02.py` | `d5b026cadc2486b4b8e6f5bb46a09d045d9d1a0f` |
| Arena `adapters/imageprogram_reference/contextual_contour_cc02_tasks.py` | `39b1bb4d2be5d127083428674a107b65ff1a1d23` |
| Arena `adapters/imageprogram_reference/branch_contour_p02_trial.py` | `41369d0242d28fc78e131750c09e33d7f21464bf` |
| Arena `adapters/imageprogram_reference/branch_contour_p02_private.py` | `0c17676a57820e96f5e809db3b92922904048077` |

Three additional original official test source blobs separately matched and were run: Model P02 `f26dd6dc87c6f8ce6c55eccb0383e71c8f4ee302` (6 tests), Model P0 `b730ae5d4d148cfb15dae22405fdafb422ee7c91` (5 tests), Arena P02 `2ed660716d7b1d89af028dd984b57122cc5c094a` (3 tests). Targeted **14/14 PASS** on Python 3.13.5 and installed NumPy. **Python 3.12 project lock/full Model and full Arena historical matrix/Ruff are NOT RUN**. This validates selected authentic modules/tests only.

## Frozen evidence and independent GRADE sequence
1. Executed source-exact `--predict` on unchanged DEV6 pairs (12 raster images), existing controls3, new technical12 = 27 PUBLIC images. The untouched original confirmation family was NOT SCORED/NOT IMPORTED by the trial.
2. Published canonical PREDICT receipt SHA256 **`d9d56faf9aca7b3ff15632824cdd5d88f99225adb8c99885c63f8871935eca54`** to [ImageProgram #100 before grading](https://github.com/ryonakayama234/ImageProgram/issues/100#issuecomment-6213592083).
3. Executed `--grade` in a separate Python process using that exact SHA; this passed hash and source checks. Private source masks are procedural, not blind/independent semantic annotations.
4. File SHA256 identities retained outside Git: PREDICT `4281a0c61a92f898576b361a5f8629d235817d1d57f1037c43e3d228e9714210`, GRADE `882a1b5aaa4cb3b045b1e8ac0bec88898aad20e186bf0d3acaf0d476b9d33cd1`, aggregated audit JSON `2547cd1440d88bd03c588e3883b112a21b084a035f37d965a039486bc0501ff1`. GitHub does not receive original raster artwork or large raw episodes.

## Development diagnostic (NOT semantic accuracy)
| Positive DEV | P0 source-derived bbox-center proxy | P02 branch arm core support | P0+P02 candidate present |
|---|---|---|---|
| dev-00 slanted | yes | none | yes |
| dev-01 T junction | no | 20/21 target pixels union; three arms | yes |
| dev-02 curved | yes | none | yes |
| dev-03 low contrast | no | none | **no** |
| dev-04 parallel | yes | none | yes |
| dev-05 Y branch | no | 16/17 union; four arms | yes |

**P0 3/6 -> P0+P02 5/6**, using a transparent *source-derived regional midpoint + arm-support presence proxy*. That reaches the preregistered >=5/6 **technical candidate-presence threshold under this proxy** only. It does not show a selected correct ordered edge path. P02-only all images keep original strong graph exactly, and R0 decision in frozen branch remains unchanged 27/27. P01 low-contrast bank is **separate**, not combined in this comparison.

### Negative evidence, all costs
- One negative `dev-05-stop` nevertheless emits **two** unknown branch arms covering **14 core pixels** in the excluded bounding region. These are uncertain observed physical ink, not an executed false join; cannot claim correct ownership/STOP based on candidate count.
- In the twelve new technical cases, the sum of excluded-only physically observed pixels retained in branch arm cores is **115** (especially T/Y/X). No claim that these are uniquely labelled line owners.
- Two technical input abstentions remain counted: thick-T `junction-budget-exceeded`, junction-grid `arm-budget-exceeded`. Technical 10/12 returned `ok`, 2/12 overflow. Full 27-case statuses: 25 `ok` and two overflow; P0 remains present in every BranchObservation.
- P02 budget charge: `2 * 72 * 72 = 10,368` pixel-pass **proxy** against declared 16,384 ceiling, **not** true instruction count or CPU/wall benchmark. No statistically meaningful runtime sample collected.
- Independent blinded annotation still OPEN under #99. Correct relation edges, STOP/HOLD/CONTINUE semantics, motor/replay/Canvas visual quality, real art, source-family transfer, confirmation, and learned Skill all **NOT RUN**.

## Decision and follow-on gates
**SELECT FOR FURTHER RESEARCH:** Keep P02 a bounded, unpromoted, versioned, separately scored bank of weakly owned junction arms. **Do not merge** Model Draft #105 or Arena Draft #41 yet. The source-derived 5/6 engineering *candidate-presence* screen is informative, but extra physical distractor evidence/unknowns and source-family coupling mean it is not a perception/reasoning capability gate.

**NEXT required:** (a) authoritative complete locked Python 3.12 paired checkout with full Model/Arena tests + Ruff; (b) #99 independent blind target/excluded arc audit on legitimate data with leakage controls; (c) P0/P02/P01 separate factorial/isolated source-family splits and candidate/false-ink/budget trade-offs; then #101 G0/G1 on identical fragments, R0/R1 on identical relations with selected ordered path and STOP/HOLD correctness. Do not score original sealed confirmation until full settings freeze.

**REJECT for now:** automatic P02 candidate→G edge or path, pretending union-support is correct line ownership, monolithic Graph v3, Canvas optimization, learned policy/Skill. Resume only with source-clean regressions and independent path/contamination evaluation.

Wolfram check: under *hypothetical independent Bernoulli trials*, exact Clopper-Pearson 95% CI for 5/6 is approx **0.3588–0.9958**; the six synthetic family labels share construction assumptions, so this interval does **not** justify population/general artwork performance claims.
