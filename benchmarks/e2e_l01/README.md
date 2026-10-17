# E2E-L01 independent Arena scoring (Draft / NOT RUN on P1 episodes)

Paired ImageProgram model-side branch: feat/e2e-l01-learning-changes-drawing-v0. Issue: https://github.com/ryonakayama234/ImageProgram/issues/114.

~~~mermaid
flowchart LR
 A["P1 saved episode + source file SHA/replay receipt"] --> C["Arena grade.py independent file/semantic verification"]
 B["Private target path from source generator"] --> D["Centerline/corridor pixel score"]
 C --> D
 D --> E["Frozen A0 / A1 / A2 comparison"]
 E --> F["independent_grade.json + 12-task Before/After review/index.html"]
~~~

**Data boundary:** task generator creates permitted public Canvas + orientation + gap-center anchor; its hidden true path is grading only. The Model learner does not import Arena grader and refuses private target/grade fields. Arena checks P1 source file manifest hashes and exact recorded replay receipt, but its scorer does not independently recreate P1 physics. The true generator currently runs in ImageProgram research orchestration: strong process-level knowledge isolation remains an unproven claim.

**Protocol:** 12 train x 4 candidates; 6 validation + 12 frozen x 3 arms. Frozen comparison A0 offset -2, A1 observed exact offset 0, A2 learned offset. Different synthetic parameterizations are NOT disjoint grammar families or real-art OOD. Independent quality = zero missing centerline pixels across hidden true gap, zero newly dark pixels outside known corridor. False positive/line width/stroke economy are additional future diagnostics, not evidenced by this pass threshold.

**Engineering decision:** A2 >=9/12 passing frozen; >=3 pure A2-only wins vs A1; 0 pure regressions, at least one changed action. A P1 program_exhausted state is never synonymous with goal accomplished. If gate fails return NOT_DEMONSTRATED; preserve all grades and examples.

~~~bash
uv run python ../ImageProgram-Arena/benchmarks/e2e_l01/grade.py \
 --run runs/e2e-l01-<unique> --out runs/e2e-l01-grade-<unique>
# Offline review: runs/e2e-l01-grade-<unique>/review/index.html
~~~

**Actual validation:** isolated Python 3.13.5 numpy tests 3/3 PASS, syntax compilation PASS. Source exact Python 3.12 full repo runner, 102 real P1 episodes, independent grade against actual P1, review/human signoff **NOT RUN** because repository clone was blocked by DNS. No scientific improvement claim. No paid CI launched.
