# v5.7 validation and limitations

## Added in v5.7

- Local unsupervised tamper-anomaly model (`ROBUST_PCA_PATCH_ANOMALY`).
- AI anomaly heatmap endpoint/view.
- Normalized anomaly regions saved in screening evidence.
- OCR field-region attribution when field geometry overlaps a strong anomaly.
- Explainable `tamper_anomaly` risk factor (20 prototype points; not a probability).
- OpenCV QR fallback if the primary `zxing-cpp` decoder is unavailable.
- Frontend labels updated from v5.3/v5.6 to v5.7.

## Focused validation performed during this upgrade

- Clean procedural document remains `NO_STRONG_ANOMALY`.
- Deliberately manipulated patch produces `REVIEW_REQUIRED`, a localized region and an affected OCR-field association.
- Risk policy records 20 prototype points for `AI_TAMPER_ANOMALY` and keeps the band explainable.
- New v5.7 backend tests: 2/2 passed in the build environment.
- Existing backend regression tests were exercised until the build environment reached a QR fixture that the OpenCV fallback cannot decode. The packaged requirements still include `zxing-cpp`, which remains the primary decoder used by the project. The failure was environment/dependency-specific rather than caused by the tamper module.
- Active prebuilt frontend JavaScript was syntax-checked after the v5.7 UI update.

## Limitations

- This is not a calibrated authenticity classifier or government policy.
- No dedicated photo-substitution classifier yet.
- No stamp/seal model yet.
- No face liveness/PAD yet.
- No real government/watchlist connection.
- No distributed blockchain.
- No claim is made that all real-world document edits will be detected.

Next planned SIH26188 upgrades: altered-photo detection, stronger face verification/liveness, visa/stamp analysis, and multiple-identity biometric history checks.
