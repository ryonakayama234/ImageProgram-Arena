# ART-1 local SourceArtwork intake v0 (draft)

Initial A02 intake primitive: one local PNG/JPEG + ROI bbox -> **private management manifest** with source-byte and normalized RGB-pixel SHA-256, EXIF orientation, mode, rights/source-family provenance and protected-region validation. No image pixels are copied into the record or GitHub. No canonical ImageProgram Task contract is changed.

Requires Pillow in the executing Python environment (e.g., ImageProgram's WSL2 environment). Safe synthetic test fixtures only; run `python -m unittest tests.test_source_artwork_intake -v` from repo root with both repositories' dependencies available.

Example (never add the artwork, cropped pixels, or output manifest to Git):

```bash
python -m adapters.imageprogram_reference.source_artwork /local/path/artwork.png \
  --roi 20 30 80 95 --source-family my-local-source-A \
  --rights local-study-only --out runs/real_reference/source_manifest.json
```

This record is **not policy-visible**; its source hashes and family IDs are management-only and must not be added to a TaskView used by a painter. The scored bbox is also management-only. Observation authorization is recorded as a channel name, not yet an enforced observation broker. TaskView generation, true editable/protected World enforcement, motor drawing, overlay scoring, learned Eye, and Skill acquisition are **not implemented** by this slice. See ImageProgram A02/A03/A05 and [Arena #16](https://github.com/ryonakayama234/ImageProgram-Arena/issues/16) / [ImageProgram #63](https://github.com/ryonakayama234/ImageProgram/issues/63).
