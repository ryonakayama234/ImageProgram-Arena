# ImageProgram reference adapter

This adapter will execute/consume an explicitly versioned ImageProgram runtime or artifact contract.

Rules:
- ImageProgram remains the canonical owner of schemas and model/runtime semantics.
- Arena must not maintain a forked compatibility schema.
- Bind runs to ImageProgram commit/version/hash.
- Freeze the Brain/Model bundle for the whole episode.
- Return episode/result artifacts with provenance.
- Never pass evaluator-private fixtures into ImageProgram policy/model inputs.

The first adapter milestone is one H3c safe episode and one H3c rejected episode from ImageProgram #26.
