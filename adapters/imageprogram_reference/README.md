# ImageProgram reference adapter

This adapter consumes explicitly versioned ImageProgram runtime artifacts without copying
ImageProgram's canonical schemas into Arena.

## H3c Foundation consumer

The first concrete adapter consumes the frozen H3c jaw golden pair:

- `jaw--original--safe`
- `jaw--original--rejected`

The source artifact remains ImageProgram's `imageprogram-h3c-public-1` bundle. Arena verifies
every file hash in each public manifest, reads only files declared by that public manifest,
rejects private/traversal paths, and preserves each ImageProgram `summary.json` unchanged in
the Arena result.

Arena adds only its own experiment envelope: benchmark lineage, split, source provenance,
bundle-manifest hashes, explicit cross-cell checks, and PASS/FAIL.

The frozen source is ImageProgram PR #32 merge commit:

`824cbefc14e3e1e4978f10fd687a0c80fb200f4d`

Run against an actual ImageProgram H3c matrix output:

```bash
python -m adapters.imageprogram_reference.consume_h3c \
  --matrix-root ../ImageProgram/runs/h3c-matrix-freeze-v1 \
  --manifest benchmarks/complete_structure_v0/manifests/h3c_golden_pair_v0.json \
  --source-commit 824cbefc14e3e1e4978f10fd687a0c80fb200f4d \
  --out runs/arena2-h3c-jaw-golden-pair.json
```

The consumer does not read ImageProgram's sibling `private/` directories.

This phase does not rerun the 12-cell H3c claim, perform H4 Body A/B comparisons, branch
candidate outcomes, or introduce learning.
