# ImageProgram-Arena

ImageProgram-Arena is the embodied experiment and experience-generation side of the ImageProgram project.

Its job is not to own the painter's model logic. It provides reproducible tasks, bodies/world adapters, execution isolation, episode collection, evaluator-private diagnostics, and benchmark comparison so that ImageProgram can learn from real or simulated drawing experience without mixing evaluation secrets into policy inputs.

## Boundary

```text
ImageProgram
  model / planner / ranker / effect / skill / training
        |
        | versioned executable/config + public task contract
        v
ImageProgram-Arena
  task fixtures
  body/world/robot adapters
  run orchestration
  public/private isolation
  episode collection
  benchmark evaluation
        |
        | versioned episode/result artifacts
        v
ImageProgram
  train / compare / validate / promote
```

### ImageProgram owns

- model and model registry
- candidate generation and ranking
- Effect / World-side model research
- Planner and Skill logic
- training and model promotion
- canonical wire/schema definitions

### Arena owns

- benchmark task fixtures and lineage
- embodiment/environment adapters
- episode execution orchestration
- public vs evaluator-private isolation
- benchmark-side oracle diagnostics
- episode/result artifact collection
- reproducible baseline-vs-candidate comparison

Arena must not silently copy or fork ImageProgram's canonical schemas. It should consume explicitly versioned/hash-bound contracts and artifacts from ImageProgram.

## First benchmark

The first target is `complete_structure_v0`, connected to:

- ImageProgram #26 — H3c non-blank public-only continuation
- ImageProgram #16 — fixed-candidate Construction Ranker v0
- ImageProgram #15 — drawing-task modes and evaluation boundaries
- Arena #1 — later UI for real baseline/learned episode comparison
- Arena #2 — Arena Foundation implementation

The initial benchmark uses synthetic Character v0 omission tasks and separates:

1. candidate availability,
2. ranker choice,
3. protection preflight,
4. lowering/execution,
5. final completion/evaluation.

This prevents a failed drawing from being reported generically as a "model failure" when the failure actually came from candidate recall, ranking, execution, or task reachability.

## Information boundary

Policy/runtime-visible data may include public incomplete observations, public task manifests, allowed Construction scaffolds, Goal/protection conditions, Body/Tool availability, budgets, and explicit model/runtime versions.

Evaluator-private data may include hidden completed witnesses, omitted source programs, witness spans, known continuations, oracle candidate outcomes, management checkpoints, and test-only labels.

Evaluator-private data must never become policy/model input.

## Development order

1. Freeze the repository boundary and benchmark semantics.
2. Add a file-based reference adapter for ImageProgram.
3. Run one real H3c safe/rejected episode through the Arena harness.
4. Add lineage/split and evaluator-private isolation tests.
5. Add fixed-candidate A/B collection for Construction Ranker v0.
6. Build UI only from real stored episode artifacts.

Robot hardware adapters, live services, and autonomous model update are later stages and must not be inferred from the initial Arena Foundation.

## Current state

Repository initialization / research foundation. No learned-ranker improvement, robot-hardware integration, general character understanding, or real-image adaptation is claimed yet.
