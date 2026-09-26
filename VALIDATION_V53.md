# v5.3 validation

Tests run in Linux/Python 3.12; frontend unit tests use jsdom.

Release checks: **79 backend tests passed; 29 frontend tests passed; production frontend
build succeeded.** Commands:

```text
cd backend
python -m pytest tests -q
cd ..
npm test
npm run build
```

New test coverage includes authenticated/bounded image preparation, invalid images, QR
masking with unchanged original bytes/signature, capture guidance, forensic image bounds,
synthetic repeated-texture candidates, blank-image behaviour, saved intake notes/report
escaping, and original/prepared OCR disagreement. Existing repeated-screening, cancellation,
registry, signature, accounts, audit and recovery tests are retained.

Parser tests use multiple unrelated synthetic document numbers. They cover separate fields,
geometry-separated noise, retained contiguous/ambiguous suffixes, O/0 preservation, unique
PAN/EPIC/UID-pattern candidates, and visa/passport-reference separation. No fixture ID is
used as a production parser preset.

Real OCR smoke test used the packaged English Tesseract engine/assets on:

| Input | Observation |
| --- | --- |
| Original signed sample | Engine raw text included `Document number: DEMO5201 . pL Fak`; geometry-aware extraction produced `DEMO5201` |
| QR-excluded sample | Cleaner overall text, but number read `DEM0O5201`; demonstrates why confidence alone is unsafe |
| Separate fictional card layout | Correctly extracted `AX729381`, CASEY TEST and labelled dates without a QR or registry |

The application retains original-image suggestions when the two QR-case reads disagree,
shows both reads, and keeps officer corrections attributable. Dual reading is not a
guarantee of accuracy; the officer must inspect the original image.

The smoke script runs with Node and local worker/core/language paths, not browser automation.
No real personal IDs were used. These are small synthetic functional tests, NOT a real-ID
accuracy benchmark or a tampering-model evaluation. Runtime backend tests deny outbound
socket connections. The smoke test uses bundled local assets; no external inference service.

Full-browser layout/camera, Windows package installation, handwritten text, additional
languages, poor captures and representative real-ID accuracy are not validated here.
Repeated-feature detection is a bounded heuristic (700 ORB features at at most 1200 pixels
per side), not a trained fraud detector. Sensitivity and false-positive rates are uncalibrated.

Reproducible developer smoke test: `scripts/prepare-ocr-smoke.py --out NEW_QA_DIRECTORY`
creates synthetic fixtures (Linux font path in this developer script); then run
`node scripts/ocr-smoke.mjs PATH_TO_IMAGE ...` after installing frontend development dependencies.
Neither step is required to run the packaged app on Windows.
