# Release notes — BHARATSHIELD v6.8

## SIH26188 Checkpoint Decision Center

This release consolidates the existing BHARATSHIELD screening modules into a single evidence-oriented checkpoint view. It intentionally does not create a new ML/fraud score.

### New backend component

`backend/app/checkpoint_center.py` derives a live summary from the saved screening evidence and findings. It categorizes each evidence lane as `ESCALATE`, `RECAPTURE`, `REVIEW`, `INCOMPLETE`, `CLEAR`, optional/not-run, or not-applicable.

### UI

`dist/v68-checkpoint-decision-center.js` adds the unified view to the packaged local frontend without requiring npm. A refresh action reloads current person/liveness/identity-history evidence.

### Evidence/reporting

The computed center is included in `/api/screening/{id}`, evidence JSON export, and the self-contained local HTML report.

### Validation

- Dedicated v6.8 tests: **6/6 passed**.
- v5.7–v6.8 upgrade regression batch: **66/66 passed**.
- Core local/recovery/registry tests: **39/39 passed**.
- v5.1 tests: **8/8 passed**.
- v5.3–v5.4 tests: **10/10 passed**.
- v5.5–v5.6 tests: **9/9 passed**.
- v5.2 excluding the two known dense-QR native-decoder cases: **24/24 passed**.
- The same 2 `06_substituted_valid_qr.png` assertions remain environment-limited in this Linux validation environment because native `zxing-cpp` is unavailable. They are unrelated to v6.8.

Total confirmed passing regression assertions in this environment: **156**.
