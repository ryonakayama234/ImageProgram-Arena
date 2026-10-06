# H5a Branch Isolation Gate

Status: implementation for Arena #8.

This gate verifies that a fixed candidate set can be executed from the same
management-side checkpoint without branch-to-branch contamination. It is an
experiment-integrity claim only. It does not claim Outcome learning, ranking,
Affordance, H5b transfer, or improved drawing quality.

## Source boundary

Arena does not copy ImageProgram's H5 Outcome schema or runtime implementation.

The current integration target is ImageProgram commit:

- `134d7cb8486373f3a70a1c506e3def0cb40d25c9`

The H5a canonical contracts at that line are:

- schema version: `0.1.0`
- record contract: `construction-outcome-record-v0`
- record contract hash:
  `sha256:a6d5c9bcbc26d6ee902c58849dbe7783c1e3067b327fa958627b6cf87eaa0fc7`
- outcome contract: `construction-outcome-v0`
- outcome contract hash:
  `sha256:0f50c772d24757e5fcda9336110b2f9ead26adeed05ac4206e0b2a73969f3e17`

A producer must pass these references into the harness and return the canonical
ImageProgram record unchanged. Arena checks version/hash/provenance identity but
does not re-implement the complete Pydantic Outcome schema.

## Execution invariant

For every candidate:

```text
same private management checkpoint
    |
    +-- fresh restore -> candidate A -> outcome A
    +-- fresh restore -> candidate B -> outcome B
    +-- fresh restore -> candidate C -> outcome C
    +-- fresh restore -> candidate D -> outcome D
```

The restored management-state hash must equal the frozen
`management_initial_state_hash` before every execution.

The harness does not accept "continue from previous branch final state" as a
valid implementation.

## Public/private boundary

The policy input and candidate public payload are scanned before execution for
management/evaluator-only keys and paths such as:

- hidden witness
- known continuation
- source Program / witness binding
- oracle Outcome / best-candidate labels
- checkpoint paths
- private paths / `.npz` checkpoint references

The opaque management checkpoint is supplied separately to the restore callback.
It is not placed inside the policy input.

## Forward/reverse canary

For K=4 candidates, the #8 isolation canary runs:

```text
forward: A B C D
reverse: D C B A
```

All `Binomial[4,2] = 6` candidate-pair relative orders are reversed by this
pair of schedules. Eight branch executions therefore provide:

1. every candidate executed twice from the frozen checkpoint;
2. every candidate pair observed under both relative orders;
3. one per-candidate semantic equality check across the two schedules.

This canary proves the harness property before #9. The 12 x 4 H5a pilot itself
does not need to double from 48 to 96 executions merely to repeat this
infrastructure gate.

## Semantic determinism and wall time

ImageProgram's cost record includes measured wall time. Wall time is real
research cost and must not be fabricated or discarded from the raw canonical
record, but it is not a deterministic state transition quantity.

Therefore:

- raw branch records retain `wall_time_s`;
- policy execution cost remains structurally separate from
  `branch_research_cost`;
- branch semantic digests exclude only `record_id` and `wall_time_s`;
- deterministic audit JSON excludes only `wall_time_s`.

Simulation time, motor commands, strokes, tip distance, observed Outcome,
initial/final state hashes, replay status, contract hashes, and provenance remain
inside the semantic comparison.

## Adapter callback contract

`run_exhaustive_branches(...)` accepts injected callbacks so Arena does not
vendor ImageProgram runtime code.

The execute callback receives:

1. a freshly restored management context;
2. one fixed public candidate;
3. a deep-copied public policy input.

It must return:

```text
initial_state_hash
final_state_hash
outcome_record          # canonical ConstructionOutcomeRecordV0 payload
policy_execution_cost   # agent/runtime execution cost, not research branching cost
```

Unexpected adapter exceptions are not silently converted into zero targets.
Collection failure must be represented explicitly by the canonical
`record_status="missing"` semantics supplied by ImageProgram.

## Acceptance covered by #8

The dedicated tests cover:

- forward/reverse branch-order invariance;
- fresh restore for every branch;
- failed branch cannot contaminate the next candidate;
- deliberately sticky restore is detected;
- repeated candidate semantic determinism;
- policy-private/oracle input rejected before execution;
- H5 contract hash mismatch rejected;
- research and policy cost channels remain separate;
- deterministic audit projection preserves simulation semantics while excluding
  measured wall time.

Run:

```bash
python -m unittest discover -s tests -p 'test_h5_branch_isolation.py' -v
```

## Handoff to Arena #9

#8 freezes the isolation harness. #9 is responsible for the concrete ImageProgram
adapter, fixed four-candidate producer, twelve independent lineage manifest,
raw branch record bundle, and 48-execution pilot collection.

#9 must not modify candidates using hidden witnesses or prior branch outcomes.
