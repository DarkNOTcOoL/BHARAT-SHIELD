# v5.8 validation and limitations

## Added in v5.8

- Local YuNet-based document-portrait localization.
- Dedicated portrait/photo-integrity analysis module.
- Photo-region overlay endpoint/view (`photo-integrity`).
- Multi-cue review logic using boundary, JPEG-residual, noise-pattern and v5.7 tamper-overlap evidence.
- Explainable `PHOTO_SUBSTITUTION_REVIEW` finding.
- Shared `forensic_integrity` risk family to prevent generic tamper + portrait evidence from being double counted.
- System status now reports `YUNET_PLUS_LOCAL_FORENSIC_ASSIST` for photo substitution.
- Prebuilt frontend receives the v5.8 portrait-integrity panel/button through a local static enhancement script; no network resource is used.

## Validation performed in this build environment

- Python syntax checks passed for the new and modified backend modules.
- Focused v5.8 portrait tests passed: a clean procedural portrait region stays below review; a deliberately discontinuous/pasted region with independent forensic cues is routed to review.
- A separate YuNet smoke check confirmed that a face can be localized while a natural portrait-texture anomaly alone does not automatically become a photo-substitution review.
- Backend regression result: **94 tests passed**. Two dense signed-QR assertions for `06_substituted_valid_qr.png` depend on the optional native `zxing-cpp` decoder in this Linux build environment and were excluded from the passing count. The Windows requirements still include `zxing-cpp` as the primary decoder; this is unrelated to the v5.8 photo-integrity module.
- The active prebuilt frontend bundle and the v5.8 local enhancement script passed JavaScript syntax checks.

## Limitations

- Not a trained/calibrated universal altered-photo classifier.
- Not a replacement-photo probability.
- YuNet only localizes face-like portrait regions; legitimate ghost portraits/security images can produce multiple detections.
- Strong local forensic cues can also be caused by legitimate scanning, lamination, holograms, resaving or printer differences.
- No face liveness/PAD yet.
- No stamp/seal classifier yet.
- No authorized government/watchlist connection.
- A clean result never establishes document authenticity.

Next planned SIH26188 upgrade: stronger face verification with quality gating and liveness/anti-spoofing, followed by visa/stamp analysis and multiple-identity biometric history checks.
