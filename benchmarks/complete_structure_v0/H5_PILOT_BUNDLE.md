# H5a 12×4 Pilot Bundle

Status: implementation work for Arena #9. This document defines the Arena-side
bundle/consumer layer only. A real 48-execution pilot is not claimed until the
ImageProgram-owned fixed candidate corpus (ImageProgram #46) is consumed.

## Responsibility boundary

ImageProgram owns:

- the 12 task lineages and their public prediction inputs;
- exactly four fixed public Construction candidates per lineage;
- candidate payload/set hashes and canonical H5 outcome contracts;
- candidate generation semantics.

Arena owns:

- same-checkpoint execution through the frozen H5 branch-isolation harness;
- branch/result collection;
- evaluator-private raw outcome bundle;
- independent recomputation of producer integrity.

Arena must not alter a candidate from hidden witness/oracle information.

## Pilot arithmetic

The frozen pilot size is:

```text
12 independent task lineages
× 4 fixed candidates / lineage
= 48 branch executions
```

Each four-candidate lineage has `Binomial[4,2] = 6` candidate pairs, for 72
within-lineage pair relations overall. These 72 relations are diagnostics, not
72 independent statistical samples. The independent unit remains the 12 task
lineages.

The H5 #8 forward/reverse isolation canary already doubles one lineage to verify
order invariance. Arena #9 does not automatically double the research pilot to
96 executions.

## Producer API

`run_pilot_bundle(...)` accepts 12 lineage records. Each record contains:

- `source_lineage`
- optional `parent_lineage`
- the frozen H5 branch `spec`
- an opaque management `checkpoint`
- four ImageProgram-produced public candidates

The caller injects lineage-aware restore/state-hash/execute callbacks. For each
lineage Arena calls the existing `run_exhaustive_branches(...)` implementation
with canonical candidate-ID execution order.

The management checkpoint is never serialized into the returned bundle.

## Bundle integrity

The raw bundle stores every canonical candidate-level outcome record and measured
research cost. It also stores:

- a deterministic lineage manifest hash;
- Arena's full candidate-manifest hash per lineage;
- the ImageProgram candidate-set hash per lineage;
- a semantic bundle hash.

The semantic bundle hash excludes only run-local `record_id` and measured
`wall_time_s`. Raw measured wall time remains in the evaluator-private bundle and
is still summed by the independent audit.

## Independent consumer

`verify_pilot_bundle(...)` recomputes from raw branch artifacts:

- exactly 12 unique task lineages;
- exactly four unique candidates per lineage;
- exactly 48 total candidate executions;
- branch-harness PASS;
- same management initial state;
- candidate set and candidate manifest binding;
- replay semantics;
- explicit missing reasons;
- total research cost;
- lineage-manifest hash;
- semantic bundle hash.

The producer summary is not PASS authority.

## Dependency discovered during implementation

Arena #9 cannot safely invent its own four-candidate sets because repository
policy assigns candidate generation to ImageProgram. ImageProgram #46 therefore
owns the fixed public candidate corpus needed for the real pilot.

Until #46 exists as a consumable artifact, unit tests may verify orchestration and
integrity mechanics, but they do **not** satisfy the 48 real ImageProgram execution
acceptance item.

## Test

```bash
python -m unittest discover -s tests -p 'test_h5_pilot_bundle.py' -v
```

After ImageProgram #46 is available, the next step is a concrete reference adapter
that loads that artifact, restores each management checkpoint, executes all 48
branches, writes the raw evaluator-private bundle, and runs the independent
consumer over the written file.


## Concrete cross-repo run

After ImageProgram #47 / #46 / #50 are merged and validated, generate #47 and #46
artifacts from the **same exact ImageProgram commit**, then invoke Arena:

```bash
python adapters/imageprogram_reference/run_h5_pilot.py \
  --imageprogram-root ../ImageProgram \
  --lineage-root ../ImageProgram/runs/h5a-pilot-lineages \
  --candidate-corpus ../ImageProgram/runs/h5a-pilot/fixed_candidate_corpus.json \
  --source-commit <exact-40-hex-ImageProgram-commit> \
  --out runs/h5a-pilot-12x4
```

The concrete adapter verifies before any branch execution:

- #47 private summary benchmark/source commit;
- #46 candidate-corpus version/source commit;
- exact candidate-corpus hash provenance;
- #47 public-input hash == #46 lineage public input;
- checkpoint SHA-256;
- frozen management state hash;
- 12 unique task lineages and 12 unique source lineages;
- #50 contract/runtime descriptor bound to the same ImageProgram commit.

Each candidate is then executed by the ImageProgram #50 CLI in a fresh process from the
same immutable checkpoint file. Arena does not implement Skill lowering, World execution,
or Outcome measurement.

Generated branch directories and the raw pilot bundle are evaluator/management artifacts
and stay out of Git.
