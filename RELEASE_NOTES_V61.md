# BHARATSHIELD v6.1 release notes

v6.1 adds local encrypted biometric identity-history retrieval for multiple-identity / identity-impersonation investigation while preserving the v5.7 tamper-anomaly, v5.8 portrait-integrity, v5.9 active-liveness and v6.0 visa/stamp features.

## Implemented

- New `biometric_history.py` retrieval layer using normalized SFace templates and cosine similarity.
- Biometric template creation only after a passed active-liveness challenge.
- Raw liveness frames remain non-retained.
- Retained biometric templates are Fernet-encrypted under a separate local `biometric.key`.
- Search is bounded to the latest 500 local templates and returns at most 10 candidates.
- Candidate retrieval threshold, review threshold and strong-review threshold are explicitly recorded in evidence.
- Identity-attribute comparison distinguishes different name, DOB and document number.
- `BIOMETRIC_IDENTITY_HISTORY_CANDIDATE` creates manual-review routing without asserting that two records are the same person.
- Document-authenticity risk points are not automatically increased by uncalibrated biometric history evidence.
- Evidence JSON and audit trail record identity-history status and retained-template metadata without raw face images.
- Prebuilt frontend receives a local v6.1 enhancement script, so npm is not required on the demo laptop.

## Validation

- Dedicated v6.1 tests cover encrypted template round-trip, similarity candidate generation, same-identity non-alert behavior, liveness-triggered history search, template persistence and system-status exposure.
- Focused v5.9/v6.0/v6.1 regression group: 16 tests passed.
- The known dense signed-QR fixture `06_substituted_valid_qr.png` still requires native `zxing-cpp`; OpenCV's fallback decoder in the Linux validation environment cannot decode that unusually dense QR. Windows Python 3.12 requirements include `zxing-cpp`.
- Frontend source is updated, and the packaged prebuilt frontend loads `dist/v61-identity-history.js` so the new evidence is visible without rebuilding React.

## Security / accuracy statement

This remains an SIH prototype. No government biometric repository is connected. Similarity candidates are local investigative leads only, not identity verdicts, watchlist matches or calibrated probabilities. Human review and independent evidence remain required.
