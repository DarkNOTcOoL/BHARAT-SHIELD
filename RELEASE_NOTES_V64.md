# BHARATSHIELD v6.4 Release Notes

## Step 8: Layout / security-zone anomaly assistance

This release adds `LOCAL_EXPLAINABLE_LAYOUT_SECURITY_ZONE_V1` and keeps all earlier local OCR, tamper, portrait-integrity, liveness, visa/stamp, biometric-history and document-routing features.

### Validation performed in the release environment
- Step 8 tests: **6/6 passed**.
- Individually executed backend regression groups: **129 tests passed**.
- Two known dense signed-QR cases for `06_substituted_valid_qr.png` were excluded because native `zxing-cpp` is not installed in the Linux validation environment. The Windows Python 3.12 requirements continue to include `zxing-cpp`.
- ZIP CRC and release SHA-256 manifest are verified by the packaging script.

### Important limitations
This is explainable anomaly triage, not official document-template authentication. Broad family zones intentionally tolerate normal layout variations. A low anomaly score does not prove genuineness, and a review signal does not prove forgery. Production-grade exact template verification would require authorized, versioned references for the specific issuing authority and document generation.
