# BHARATSHIELD v5.7 — Step 1 upgrade: local AI-assisted tamper anomaly analysis

This release is the first step in the SIH26188 fraud-detection upgrade path. It keeps the v5.6 OCR, registry, signed-QR, cross-document, face-comparison, review and audit workflows intact and adds a fully local machine-learning-assisted tamper inspection layer.

## What changed

- Added `backend/app/tamper_ai.py`.
- Runs a self-calibrating, unsupervised patch-anomaly model locally with NumPy/OpenCV.
- Uses forensic features including JPEG recompression residuals, local noise residuals, gradients, Laplacian energy, luminance statistics and entropy.
- Fits a robust PCA baseline for each submitted document and scores unusual patches against that document's own baseline.
- Requires a second forensic cue before an outlier is promoted to a strong region, reducing false alarms from ordinary printed text.
- Produces normalized suspicious-region boxes and an AI anomaly heatmap.
- Intersects suspicious regions with browser-supplied OCR field geometry when available, so the officer can see which extracted field region may be affected.
- A strong anomaly adds an explainable 20-point `tamper_anomaly` factor to the synthetic reference risk policy and forces manual review. It never directly marks a document as forged.
- Added an OpenCV QR decoding fallback when `zxing-cpp` is unavailable. Ed25519 signed-credential verification is unchanged.
- Updated the evidence screen with an **AI anomaly map**, max anomaly index, region count, patch count and affected-field display.

## Important limitation

The v5.7 tamper component is an **unsupervised anomaly detector**, not a universally trained forgery classifier and not a fraud probability. Legitimate photos, holograms, stamps, QR codes, folds, glare and complex security backgrounds can be unusual. A clean result does not prove authenticity. The officer remains responsible for the decision.

## Upgrade from your working v5.6

1. Stop v5.6 with `Ctrl+C`.
2. Extract v5.7 into a **new folder**. Do not overwrite the working folder.
3. Copy the complete existing `backend/private` folder from v5.6 into the new `backend` folder if you need existing users/evidence. Do not copy only the database or encryption key.
4. Reuse or create a Python 3.12 virtual environment and install `backend/requirements.txt`.
5. Start the backend as before:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

6. Open `http://127.0.0.1:8000`.
7. Run a new screening and open **AI-assisted tamper analysis** in the evidence view.

## What to show judges

Use the phrase: **"Local unsupervised ML-assisted tamper localization"**.

Do not call the anomaly index a fraud probability. Explain that BHARATSHIELD combines the anomaly signal with OCR, MRZ, registry, signed QR, cross-document and historical evidence, then sends suspicious cases to human review.
