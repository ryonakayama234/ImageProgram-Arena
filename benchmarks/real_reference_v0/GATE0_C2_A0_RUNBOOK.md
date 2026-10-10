# ART-1 Gate 0 — genuine C2 → Arena A0 end-to-end verification

**Status: implementation candidate; Gate 0 PASS not yet claimed.** Tracks [Arena #16](https://github.com/ryonakayama234/ImageProgram-Arena/issues/16), [ImageProgram #63](https://github.com/ryonakayama234/ImageProgram/issues/63) and [Arena planning PR #17](https://github.com/ryonakayama234/ImageProgram-Arena/pull/17).

## Scope and executable sequence

With two sibling local Git checkouts, the Gate 0 runner:
1. Rejects dirty/unexpected branches and records the two exact Git commit SHAs. Never does Git checkout, reset or pull behind the user's back.
2. Installs locked ImageProgram dependencies under its venv, executes full ImageProgram unit checks and Ruff, then all Arena unittest cases in the installed ImageProgram venv.
3. Runs the merged C2 producer to generate a **fresh** legal Character preparation and **two independently executed hair continuation episodes** from one checkpoint.
4. Runs the Arena A0 Review Pack. Its consumer invokes ImageProgram source replay for **each** verified episode, rather than trusting a supplied replay JSON flag.
5. Audits actual source and Review Pack outputs: same checkpoint/task/body/budget, distinct Motor programs and final state hashes, positive new ink, zero protected new ink, correct incremental costs and re-observation, fresh source replays, three image frames per session.
6. Writes a local machine audit whose successful status is **AUTOMATED_PASS_VISUAL_REVIEW_PENDING**. A human inspects images before complete Gate 0 PASS.

These are analytic/fixed proposals using a human-given Construction scaffold, **not learned perception or drawing skill**.

## Run from WSL2/Linux

Prerequisites: sibling checkouts in ~/src/ImageProgram (private) and ~/src/ImageProgram-Arena, Python 3.12, git and uv available. ImageProgram on clean latest main. Arena on clean main **after merge**, or clean branch feat/art1-gate0-c2-a0-verified-run **for review before merge**. The runner does not fetch/pull your Git history automatically.

From the Arena checkout:

~~~bash
bash adapters/imageprogram_reference/run_gate0_c2_a0.sh
~~~

Or give the local ImageProgram directory:

~~~bash
bash adapters/imageprogram_reference/run_gate0_c2_a0.sh "$HOME/src/ImageProgram"
~~~

The command prints a fresh, Git-ignored run folder containing:
- run.log (real test and runner logs)
- c2/public/summary.json and c2/private/{preparation_episode,analytic_episode,manual_episode,...}
- review/index.html, review/review.json and each session's initial/mid/final PNG frames
- gate0_report.json (automated audit, actual code SHAs, no "learned" claim)

Source/private World checkpoints, outputs, images and logs **are never committed** to the public Arena repository. Failures leave partial output for diagnosis rather than overwriting prior runs.

## Required visual inspection and evidence

Open the printed review/index.html in the user's local browser. Confirm that the two final strokes visibly differ, make sense within the hair drawing, do not intrude on protected face/eye, and have real intermediate frames. Record human acceptance/failure with the local run ID and both SHAs. This cannot be replaced by mock tests.

Failures: preserve the locally saved run.log, pinned SHAs and partial artifacts, then fix the appropriate owning repository and re-run in a fresh directory. Never change hidden evaluator, replay or protection expectations just to obtain PASS.

## Gate 0 Definition of Done

- Full relevant regression checks and Ruff on pinned code versions.
- Exactly two different legal source Motor episodes from the same checkpoint; no newly protected ink; actual new ink.
- Independent **Arena consumer validation** invoking the pinned ImageProgram source replay. Arena is not an independent physics simulator.
- Authentic review HTML shows initial, intermediate and final PNG from actual episodes with versioned provenance.
- Machine evidence audit passes, followed by human visual sign-off.
- Errors are not silently discarded and original Character/H5a frozen cases remain untouched.

This runner does **not** start GitHub Actions automatically; ImageProgram's existing CI is manually triggered to avoid incidental billing.

## Unit and script sanity checks

~~~bash
cd ~/src/ImageProgram-Arena
python3 -m unittest discover -s tests -p 'test_gate0_audit.py' -v
bash -n adapters/imageprogram_reference/run_gate0_c2_a0.sh
~~~

The eleven audit tests use **mock-only fixtures**, covering identical outcomes, changed task, fake fresh replay, zero ink, protected-zone violations, same Program, inconsistent continuation costs, tampered PNG bytes, mismatched frame SHA-256, and unsafe paths. Unit tests are not real-episode evidence. These checks cannot substitute for a real ImageProgram replay and a human visual review.

After Gate 0, the next milestone is Gate 1: real local reference-image ingestion, digest, ROI, visibility boundaries and coordinate contract; no need to add a new drawing primitive or learned model at this stage.
