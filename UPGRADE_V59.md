# BHARATSHIELD v5.9 — Step 3: Face Quality + Active Liveness

v5.9 keeps every v5.8 document, OCR, registry, signed-QR, tamper, photo-integrity, review and audit feature and upgrades the optional person-comparison workflow.

## What changed

- **Quality-gated YuNet + SFace comparison.** The live/person face crop is checked for blur, exposure and size before a similarity measurement is accepted for officer review.
- **Randomized active liveness challenge.** The server issues a short-lived, one-time sequence consisting of a neutral pose and left/right head turns. The order of the two turn steps is randomized.
- **YuNet landmark motion analysis.** The backend measures nose position relative to the eye line and requires opposite head-turn motion around the neutral capture.
- **Local-only processing.** Challenge frames are processed on the local FastAPI service. The backend stores hashes, quality/landmark measurements and the result, but not the three challenge images.
- **Evidence history.** Liveness attempts and method metadata are retained in exported evidence and audit history.
- **No biometric overclaim.** SFace cosine similarity remains an uncalibrated review measurement, not an identity probability. The active challenge is prototype replay resistance, **not certified presentation-attack detection (PAD)**.

## Upgrade from v5.8

1. Stop v5.8 with `Ctrl+C` and keep the entire old folder as a backup.
2. Extract v5.9 into a **new** folder.
3. To keep users/evidence, copy the entire old `BHARATSHIELD/backend/private` folder into the new `BHARATSHIELD/backend/` folder. Do not merge individual database/key files.
4. Use Python 3.12 and create a fresh virtual environment:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## Demo the new feature

1. Complete a normal document screening containing a usable portrait.
2. In **Optional person comparison**, use the person's consented live camera capture and click **Compare locally**.
3. Review YuNet/SFace similarity and face-quality evidence.
4. Click **Run active liveness challenge**.
5. Follow the three on-screen poses. Start facing forward; then perform the randomized left/right turn instructions.
6. A successful run shows `PASSED_ACTIVE_CHALLENGE`. If movement or image quality is insufficient, the result is `RETRY_REQUIRED` rather than a fraud accusation.
7. Download the evidence JSON/report to show the liveness method, frame hashes, motion checks and audit event.

## Security / interpretation limits

This active challenge primarily adds resistance to a **static photograph** being presented to the camera. It is not a certified ISO/IEC 30107 PAD implementation and has not been calibrated against sophisticated video replay, masks, deepfakes or virtual-camera attacks. A successful challenge does not establish identity by itself. The final person/document decision remains with the authorized officer.
