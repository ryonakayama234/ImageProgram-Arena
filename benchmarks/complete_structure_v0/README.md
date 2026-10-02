# complete_structure_v0

Purpose: exercise ImageProgram's deterministic Construction execution seam on non-blank incomplete states before introducing learned ranking.

## Phase A — H3c

Input:
- public incomplete artifact/observation
- human-given Construction Scaffold
- public Goal/protection conditions
- fixed Body/Tool/World/runtime/model versions

Evaluation:
- preflight safe/rejected
- legal execution
- geometry realization / endpoint error
- protection violation
- motor/stroke/observation/sim/wall cost
- stop reason
- deterministic replay
- public/private leakage checks

Initial targets:
- jaw boundary
- center hair lock
- neck / shoulders

Include safe, protection-conflict, semantic-ID permutation, and affine variants.

## Phase B — Construction Ranker v0

A and B receive the exact same candidate set.

- A: handwritten fixed ranker
- B: learned ranker

Freeze candidate generation, candidate budget, feature contract, Effect Model, protection preflight, Body/Tool/World, lowering, evaluator, and episode budget.

Report separately:
- candidate valid recall@K
- top-1/top-k rank success conditional on an available valid candidate
- execution success conditional on valid selection
- final completion
- rank regret
- protection violation
- execution and research costs

Independent statistical unit: task lineage, not candidate, stroke, or near-duplicate template variant.

Evaluator-private oracle execution may diagnose candidate availability but must not be policy input.
