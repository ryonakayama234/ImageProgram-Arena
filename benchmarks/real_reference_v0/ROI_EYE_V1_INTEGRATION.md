# ART-1 v1 ROI/Eye Arena integration — independent acceptance checklist

**Status: DESIGN ONLY; current v0 harness not yet v1-ready.** 2026-10-11. Paired with [ImageProgram design on Draft #75](https://github.com/ryonakayama234/ImageProgram/pull/75), [R1 #77](https://github.com/ryonakayama234/ImageProgram/issues/77), [E1 #78](https://github.com/ryonakayama234/ImageProgram/issues/78), [Arena A1 #21](https://github.com/ryonakayama234/ImageProgram-Arena/issues/21), parent [Arena #16](https://github.com/ryonakayama234/ImageProgram-Arena/issues/16). No user image/crop or original metadata in GitHub.

## Frozen v0 baseline / acknowledged defects

- Existing `adapters/imageprogram_reference/public_reference_roi.py` exports a policy-visible permitted L8 crop **plus full source dimensions and absolute editable bbox** in `arena-public-reference-roi-v0`.
- Existing `score_first_contact.py` pastes permitted crop back into a full-size white canvas and resizes the **entire source** to 256×256 with bilinear L8 interpolation; its allowed-mask is resized nearest and terminal F1 is computed with a square 5×5 dilation (L∞ 2 World pixels).
- Existing `run_first_contact.sh` checks paired draft branches and clean Git checkouts and calls `first_contact.py` for actual legal P1 Episodes `fine/coarse/noop`. This is **not** P2 Eye closed-loop and has not been revalidated with the future v1 task.
- Do **not** modify old v0 output in place or compare cross-version F1 as though the metric geometry were identical. Existing A0×C2 Gate 0 and real-art visual gates remain independently pending.

## Arena-owned local v1 task export

The private SourceArtwork manifest retains original normalized image orientation/dimensions, source/family/rights information, absolute source bbox, protected boxes, raw and normalized digests. A user has authorized only the local crop. The Painter-facing v1 task must be strictly allow-listed:

```text
format: arena-public-reference-roi-v1
mode: restore_reference
reference_visibility: permitted_reference_processed
reference_roi_sha256: sha256 of public permitted L8 PNG
roi_width_px, roi_height_px: crop dimensions, *not* entire source dimensions
placement: transform_version=art1-roi-contain-v1, world_px=[256,256],
           margin_world_px=8, scale_world_px_per_source_px=s,
           offset_world_px=[ox,oy]
region_semantics: focus=local ROI, reference_observation=permitted local ROI,
                  editable=World E, scored=World S (v1 S=E),
                  protected=World complement(E)
sampling: inverse_world_pixel_centre_to_roi_bilinear_v1; outside ROI white
```

No full-source bbox/path/family/right/digest/hidden evaluator mask in public v1 task. Version mismatch/stale ROI/forged transform rejects. F/O/E/S/P are **five different concepts**, even if initial shapes coincide. A02 v1 uses explicit policy channel and access class, and management-only data stays private.

## Transform and independent target raster

For local crop w×h, N=256, M=8:
```text
s=min((N-2M)/w,(N-2M)/h), ox=(N-s*w)/2, oy=(N-s*h)/2
World raster E=[ox,ox+s*w)×[oy,oy+s*h)
World px centre (k+0.5,l+0.5) -> local ROI-boundary
  u=(k+0.5-ox)/s, v=(l+0.5-oy)/s
input image centre-grid index = (u-0.5,v-0.5)
```

Define exact deterministic bilinear with white outside ROI, explicit rounding to L8, threshold **target<145**, World final ink **<250**. E and P membership at World pixel centres (separate from strict actual World subpixel footprint legality); independently verify source world pixel alignment via synthetic witness. Off-by-one and fractional offset are part of the test matrix. Independent evaluator must recompute masks from task contract; it must **not import a candidate model's image/geometry prediction or planner outcome**. Keep score `precision_2px`, `recall_2px`, `f1_2px` but report alignment tolerance explicitly as **Chebyshev/L∞ 2 World px** and source-equivalent `2/s` px. If this scoring changes interpretation, version output to `art1-first-contact-independent-scoring-v1` with no v0 score overwrite.

**Wolfram synthetic check**: w=128,h=160,N=256,M=8 -> s=1.5, ox=32, oy=8, E=(32,8)..(224,248), effective source tolerance 4/3 px, reference pixel centres round-trip exactly. This is not a user-origin ROI measurement.

## E1 eye-feedback experiment materialization

Accept **true** initial/intermediate/final P1 World evidence with matching seed/Body/placement and legal actions, not a rendered image supplied as a purported Episode. Pair `feedback_off` and `feedback_on` using **identical initial strokes**; `feedback_on` may append <=1 observation-dependent legal correction after a fresh Canvas Observation; always include `noop`. Terminal evaluator never supplies the policy's live discrepancy. Distinguish `reference_observation`, `canvas_observation`, `analysis/decision`, actual `motor_action`, and `arena_score` by access/provenance. Verify same initial-state hash, fresh replay, ink outside E or in P = 0, query count/cost, accepted motors, actual strokes, simulated/wall times. Claim only limited local reference reconstruction.

## Source intake limits and negative tests

Keep current size ceilings (16MiB file, 16,777,216 decoded pixels, 12..256px ROI with <=65,536 area) until a separate change. Decode based on PNG/JPEG content, not misleading extension; ICC profile currently explicitly unsupported, do not remove color management silently. Symlink/file-race/EXIF orientation/alpha/ROI integrity tests remain. Public task and Review Pack cannot leak original images or source-family identifiers.

Tests before any acceptance:
- Synthetic portrait/landscape/square ROI, half-open borders, pixel centres and inverse transform.
- Exact expected independent target array on a tiny synthetic high-contrast open curve, fractional offset, letterboxing, threshold/edge behavior.
- Transform version mismatch, forged placement, different source crop hash, P overlap, pen tip centre safe but physical footprint crossing E: reject.
- Controlled underdraw after actual P1 initial stroke: feedback_on chooses different next action than feedback_off, while a complete post-stroke frame yields Stop.
- noop/fixed/fine/coarse/on/off comparisons cannot substitute direct pixel blit, private evaluator witness or a fake final screenshot.
- Full Arena and ImageProgram regression + Ruff + user WSL2 cross-repo actual episodes + **human PNG review**. No implemented, test-PASS or real-art claims before evidence.

## Runbook / PR state

Proposed order: **ImageProgram R1 placement** → **Arena A1 task+independent scorer** → **ImageProgram E1 reference/world difference + one correction** → **Arena v1 on/off/noop review**. Keep source inside local ignored image folder; Drive images are private analysis references, not automatically mounted into local WSL2. The two repos' task/sampling/transform versions and SHA must be stamped in every v1 Review Pack. Arena PR #20 is stacked atop #19; do not merge out of order or mark as ready only because this design exists.
