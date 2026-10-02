# Evaluator-private fixtures

Management/evaluation data only. The policy/model process must not read this path.

Examples:
- hidden completed witness
- omitted source Program / witness span
- known continuation
- oracle candidate outcomes
- management-only checkpoint/reference
- frozen test labels

These artifacts may be used to diagnose candidate recall, evaluate outcomes, or build research reports. They must never be copied into public features or ranker inputs.

A later harness test must prove that policy execution succeeds without this directory being mounted/readable.
