# v5.4 validation and release scope

## Implemented

- Clickable OCR rectangles on review and saved-result screens, with responsive normalized
  coordinates, keyboard-accessible buttons, a box visibility toggle and field-name buttons.
- Per-field mean word confidence and separate raw/parsed/reviewed/QR/registry evidence.
  Source text is never populated from the registry or QR payload.
- Saved extraction geometry with an explicit original-image coordinate frame; legacy
  records show unavailable geometry rather than invented rectangles.
- A perspective-corrected candidate preview when the contour heuristic finds a usable
  quadrilateral. Transformation and inverse are returned with the preview. Original bytes,
  OCR input and signature verification remain unchanged. This is not automatic alignment
  for OCR and does not claim to improve recognition accuracy.
- Dashed amber repeat-pattern region rectangles derived from existing ORB candidates.
  No trained tamper detector, probability, automatic fake verdict or rejection is added.
- Bounded OCR-note serialization now emits valid JSON rather than truncating JSON mid-string.

## Executed validation

- 83 backend tests passed, including authenticated preparation, QR/original preservation,
  saved geometry, perspective corner mapping/inverse, invalid-boundary rejection,
  normalized repeat-region bounds and unchanged tamper coverage.
- 36 frontend tests passed, including click-through evidence, no invented geometry,
  invalid rectangles, repeated-value ambiguity, coordinate scaling, confidence averaging,
  valid note serialization, cancel/failure recovery and ten consecutive screenings.
- Production frontend built successfully with bundled offline English OCR assets.
- Real local Tesseract engine smoke tests on TWO SYNTHETIC images:
  - Signed demo: document number DEMO5201, correct value rectangle, word confidence 59.
  - Different synthetic layout: AX729381, correct value rectangle, word confidence 91.
  These are test expectations, not values hard-coded into extraction. Five unambiguous
  field boxes were generated on each image. Repeated IND values were deliberately not
  assigned guessed locations. Timing is machine-dependent and is not a throughput claim.
- Original signed demo trust configuration and model files are retained from v5.3.

The backend tests prohibit outbound socket connections. Full Windows browser rendering,
camera interaction and a disconnected-laptop acceptance run were NOT executed here.
No real-ID accuracy, tamper precision/recall or forensic error-rate benchmark is claimed.
Run the manual checklist in UPGRADE_V54.md on the target laptop before presentation.

## Dependencies and warnings

No new runtime dependency was added. The build reports an existing large JS-chunk warning.
Backend tests report dependency deprecation warnings, but all tests pass. Versions remain
constrained by the existing requirements; installation should be tested using Python 3.12.

## Privacy and unchanged limitations

Everything remains local at runtime. This is a demonstration prototype, not an authorized
government verifier. OCR and metadata are not independently attested. Database metadata is
not fully encrypted by the application; use OS permissions and disk encryption. Original
document bytes retain the existing encrypted storage. Face similarity and demo signatures
are not identity or authenticity verdicts. Do not upload real IDs to chat for testing.

## Reproducible commands (development environment)

```text
npm test
cd backend
python -m pytest -q
cd ..
npm run postinstall
npm run build
python scripts/prepare-ocr-smoke.py --out <new-temporary-directory>
node scripts/inspector-smoke.mjs demo_samples/signed_qr/01_signed_match.png <new-temporary-directory>/unseen_layout.png
python scripts/package-release.py --out <new-absolute-path-outside-project.zip>
```

The fixture generator uses DejaVuSans at a Linux system path. That developer-only script
is not required to run the packaged app on Windows. The release ZIP includes file hashes
in RELEASE_SHA256.json and excludes private data, environments and node_modules.
