# BHARATSHIELD v6.2 release notes

v6.2 adds automatic local document-type routing and type-aware OCR/parser selection while preserving the v5.7 tamper anomaly, v5.8 photo-integrity, v5.9 active-liveness, v6.0 visa/stamp and v6.1 encrypted biometric-history features.

## Implemented

- `backend/app/document_type.py`: explainable local OCR-evidence router for nine supported document types.
- `src/documentTypeDetector.js`: matching browser/source router and type-aware OCR page-segmentation selection.
- Strong-cue routing for TD3 Passport MRZ, Visa fields, UIDAI/Aadhaar, PAN, EPIC/Voter ID and Driving Licence evidence.
- Conservative `DETECTED`, `AMBIGUOUS` and `UNDETERMINED` states.
- Backend independent type re-check before cross-document and document-specific verification.
- `DOCUMENT_TYPE_DETECTED`, `DOCUMENT_TYPE_UNCERTAIN` and `DOCUMENT_TYPE_CONFLICT` findings.
- Auto-rerouting preserves officer-corrected fields and only replaces blank/unchanged OCR-derived values.
- Type-aware field re-parsing (`AUTO_DOCUMENT_FIELD_REPARSE_V1`) runs in the packaged backend. The React source also contains a type-routed OCR retry path for future frontend rebuilds; the supplied prebuilt UI keeps the existing bundled Tesseract pass and relies on the backend reparse at local-check submission.
- `dist/v62-auto-document-routing.js` upgrades the supplied prebuilt frontend without requiring npm on the demo laptop: untouched rows are auto-routed at local-check submission, manual selector changes are respected, and routing evidence is displayed on the result screen.
- System status exposes `LOCAL_EXPLAINABLE_DOCUMENT_TYPE_ROUTER_V1` and `TYPE_AWARE_LAYOUT_RETRY_V1`.

## Validation

- Dedicated v6.2 backend tests: **7/7 passed**.
- Regression batches across v5.x/v6.x: **117 backend tests passed**.
- The same two parameterized cases using `demo_samples/signed_qr/06_substituted_valid_qr.png` were excluded from the aggregate count in this Linux environment because native `zxing-cpp` is unavailable and OpenCV cannot decode that unusually dense QR. Windows Python 3.12 requirements still include `zxing-cpp`; this limitation is unrelated to v6.2 routing.
- `documentTypeDetector.js` was exercised directly with Passport, Visa, Aadhaar, PAN, EPIC and Driving Licence samples; weak unknown text remains undetermined.
- The packaged prebuilt v6.2 enhancement script passes JavaScript syntax checking.

## Accuracy statement

The routing confidence is an explainable relative routing score, not a probability that a document is genuine or that the detected type is correct. Strong type conflicts are review evidence. No government issuer/type service is connected.
