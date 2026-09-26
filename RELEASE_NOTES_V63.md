# BHARATSHIELD v6.3 release notes

v6.3 adds local capture intelligence and multi-preprocessing OCR fallback while preserving the v5.7–v6.2 tamper, photo-integrity, liveness, visa/stamp, encrypted identity-history and automatic document-routing upgrades.

## Implemented
- `LOCAL_CAPTURE_INTELLIGENCE_V1`: boundary confidence, glare localization, illumination variation, skew/text-axis guidance.
- Backend recomputes capture intelligence from the original uploaded bytes; browser-reported capture metadata is not authoritative.
- `MULTI_PREPROCESSING_TESSERACT_FALLBACK_V1`: same-geometry CLAHE/sharpen, illumination-normalized and adaptive-binary OCR inputs.
- Packaged prebuilt frontend patched to run fallback Tesseract reads only when the primary read is weak, rank actual reads, keep the best, and retain one alternative for officer comparison.
- Strong glare-like saturation is a recapture-quality signal, not a fraud signal.
- New UI evidence card and updated capture-control explanation.
- Fictional low-contrast/shadow and glare demo samples.

## Validation
- Dedicated v6.3 backend tests: 6/6 passed.
- Upgrade regression group v5.3–v6.3: 52/52 passed.
- Core local/registry/recovery/v5.1 group: 47/47 passed.
- v5.2 signed-QR group excluding the two environment-limited dense-QR parameter cases: 24/24 passed.
- Known environment limitation: `demo_samples/signed_qr/06_substituted_valid_qr.png` cannot be decoded by the OpenCV fallback in this Linux environment when native `zxing-cpp` is unavailable. Windows Python 3.12 requirements still include `zxing-cpp`.
- Controlled local sanity check on `01_shadow_low_contrast.png`: system Tesseract 5.5.0 read 0/5 selected key values from the degraded original; the adaptive-binary preprocessing recovered 5/5 and illumination normalization recovered 4/5. This is a synthetic sanity check using local Tesseract CLI, not a claim of real-document accuracy or a direct Tesseract.js benchmark.

## Safety/accuracy statement
Capture intelligence and OCR preprocessing are readability aids only. They do not authenticate an issuer or establish that a document is genuine/fraudulent. Officer review of the original remains required.
