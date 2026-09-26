# BHARATSHIELD v6.0 release notes

v6.0 adds visa-specific document intelligence and local stamp/seal forensic inspection while preserving the v5.7 tamper-anomaly, v5.8 portrait-integrity and v5.9 active-liveness upgrades.

## Implemented

- Browser-source parser support for visa type/class, entries, valid-from and duration-of-stay.
- Independent server supplemental parsing of those fields from retained OCR text; server parsing never silently overwrites officer-reviewed values.
- Visa consistency checks for validity ordering and recognized entries values.
- Synthetic registry optional fields for visa type, entries, valid-from and duration.
- Cross-document visa validity rules in addition to the existing visa-to-passport reference check.
- Country-agnostic local stamp/seal candidate localization using ink/edge proposals and circular proposals.
- Stamp candidate fusion with the existing unsupervised forensic anomaly regions and local recompression/edge mismatch.
- `STAMP_SEAL_TAMPER_REVIEW` only when stronger multiple cues agree; a stamp-like shape alone is manual-inspection evidence only.
- Stamp/seal findings share the same forensic-integrity risk family as generic tamper/photo-substitution cues to avoid double counting.
- v6.0 runtime UI enhancement for the already-built frontend, so npm is not required on the demo laptop.

## Validation performed in the build environment

- Dedicated v6.0 backend tests: visa extraction/normalization, invalid validity order, conservative stamp candidate behavior, risk-family de-duplication, system-status exposure and full visa screening evidence serialization.
- v5.8/v5.9 focused regression groups remained green.
- Broad backend suite excluding the known dense signed-QR native-decoder fixture passed. The dense `06_substituted_valid_qr.png` fixture needs native `zxing-cpp`; the OpenCV fallback in this Linux build does not decode that unusually dense sample. Windows Python 3.12 requirements still include `zxing-cpp`.
- Frontend source was updated, but this isolated build environment could not complete `npm ci` because one npm tarball was not available offline. The distributable therefore retains the known-good prebuilt v5.9 bundle plus a local v6.0 enhancement script; no npm command is needed to run the ZIP.

## Security/accuracy statement

This remains an SIH prototype. No authorized government/issuer database is connected. The stamp/seal module does not authenticate official stamps, and a clean result does not establish document authenticity.
