# BHARATSHIELD v6.8 — SIH26188 Checkpoint Decision Center

v6.8 is a consolidation release tied directly to SIH26188. It does not add a new opaque AI verdict. Instead it turns the existing document/identity screening evidence into one officer-facing checkpoint summary.

## What is new

- Unified **SIH26188 Checkpoint Decision Center** on each screening evidence view.
- Dynamic recommendation state: `ESCALATE`, `RECAPTURE`, `MANUAL_REVIEW`, or `REVIEW_COMPLETE_CHECKS`.
- Separate decision-readiness state so a low rule score is never confused with a final officer decision.
- Ten evidence lanes covering document intake/OCR, MRZ/date/format, tamper/layout/visual integrity, altered-photo analysis, Registry 2.2 alerts, signed QR, visa/stamp/travel intelligence, identity history, face/liveness and cross-document consistency.
- Priority reasons are sorted from the existing findings; no new fraud conclusion is generated.
- Explicit SIH26188 scenario coverage for altered fields, replaced photo, visa/stamp issues, impersonation support, multiple identities, expired/revoked/blocked/lost-stolen records, visa-entry/stay conflicts and signed/reference identity conflicts.
- Optional face/liveness evidence is visually separated from mandatory document evidence.
- The center is computed dynamically when a screening is read/exported so later liveness/identity-history evidence is reflected.
- Evidence JSON and local HTML report include the unified center.

## Interpretation

`CLEAR` means only that a configured review threshold was not crossed. It never means a document/person is authentic. Registry 2.2, alerts, issuer references and travel history remain synthetic/local demonstration data.

## Run

Use Python 3.12, install `backend/requirements.txt`, then run:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` and run any screening. The Decision Center appears at the top of the evidence view.
