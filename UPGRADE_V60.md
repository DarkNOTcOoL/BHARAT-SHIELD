# BHARATSHIELD v6.0 — Visa Intelligence + Stamp/Seal Inspection

## Upgrade safely

1. Keep the complete working v5.9 folder as a backup.
2. Extract v6.0 into a **new folder**.
3. To retain accounts, encryption keys, evidence and screenings, copy the entire old `BHARATSHIELD/backend/private` folder into the new `BHARATSHIELD/backend/` folder. Do not copy individual database/key files separately and do not merge two private folders.
4. Use Python 3.12 on Windows:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## New in v6.0

- Visa-specific extraction/evidence for **Visa type/class, Number of entries, Valid from, Duration of stay**.
- Visa number remains separate from referenced passport number.
- Visa validity-order and entry-value consistency rules.
- Synthetic registry schema can store the new visa fields without changing older signed-demo QR field sets.
- New **local stamp/seal forensic assistance**: country-agnostic stamp-like region localization plus fusion with the existing tamper anomaly layer.
- Stamp candidates alone do not create a fraud/tamper verdict. A stamp/seal review finding requires stronger independent forensic agreement.
- Stamp/seal evidence is included in screening JSON, checks, findings and the visual document-inspection regions.
- New `stamp-integrity` image view.
- New fictional visa demo record and three fictional visa images under `demo_samples/visa_intelligence`.

## Demo

1. Sign in as supervisor.
2. Open **Synthetic Demo Registry** and click **Load v6.0 visa demo record**.
3. Open **New Screening** and upload `demo_samples/visa_intelligence/01_visa_clean.png`.
4. Select **Visa**, extract OCR, review fields, then run local checks.
5. Inspect **Visa intelligence + stamp/seal inspection** and the **Visa stamp/seal** view.
6. Repeat using `03_visa_stamp_suspicious.png` to demonstrate multi-cue manual-review routing.

## Important limits

The new stamp/seal analysis is not issuer authentication, not a country-specific stamp classifier and not proof that a stamp was added or removed. Printed logos, signatures and security artwork may appear stamp-like. Visa MRZ validation remains unsupported. All final decisions remain human-supervised.
