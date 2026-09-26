# BHARATSHIELD v5.6 — Local OCR and explained screening risk

## Install after copying private

1. Stop the previous backend with Ctrl+C. Keep the previous installation unchanged.
2. Extract the new ZIP into a new folder.
3. Copy the COMPLETE `backend/private` folder from your current working installation into the new `BHARATSHIELD/backend` folder. Keep accounts, encryption keys, databases and evidence together. Do not merge private folders or copy `.venv`. Preserve any customized public issuer trust configuration in `backend/trust` too.
4. Open PowerShell in the NEW `backend` folder and run each command separately:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use 64-bit Python 3.12. If it is missing, `py -0p` lists installed Python versions. Dependency installation needs internet. Application processing, OCR and face inference run locally. Node/npm is not required to run this package: the built frontend, English OCR assets and face models are included.

5. Open http://127.0.0.1:8000 and press Ctrl+F5. Sign in with your existing supervisor account.
6. Open **Demo Registry**, then click **Load v5.6 video demo records**. This adds eight fictional records and preserves existing records.
7. Start a new screening, upload `demo_samples/video_demo/01_active_match.png`, select **Permit**, extract text locally, review the fields against the original, and run local checks.
8. On the result page, find **Synthetic-reference risk score**. With the unchanged sample/reference and sufficient extraction, expect **0 / 100 · LOW**. This means no weighted inconsistency was detected; it does not authenticate a document or person.
9. Follow `DEMO_VIDEO_GUIDE_V56.md` for the conflict, expiry, revoked, blocked, unknown and poor-capture cases.

## Restart after closing PowerShell

Open PowerShell inside this installation's `backend` folder and run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000. Installation commands need not be repeated.

## What changed

- Small working images are enlarged for OCR while the original is retained and still governs capture quality.
- Label parsing recognizes additional date and document-number labels. An incomplete or low-confidence non-QR read gets at most one sparse-layout retry. A retry replaces the first read only if it adds fields without losing or contradicting existing fields. Both reads remain available for review. The existing two-read QR comparison remains in place.
- Texture-view rendering is computed when that inspection view is requested, reducing unnecessary forensic-image work.
- A versioned, explained rule-point score is saved with each new screening and its evidence export. History shows saved rule points separately from recommendation risk. Old screenings are not retroactively rescored.
- A supervisor-only seed button installs fictional references without overwriting records. Editing reference status changes the result through the normal verification rules; image filenames and expected sample outcomes do not determine results.

An OCR retry adds work and may increase latency on difficult images. English OCR is bundled; accuracy on arbitrary real IDs, multilingual layouts and photographs remains unvalidated. There is no government database connection. Visual inspection assistance is not a trained tamper detector; camera comparison does not establish liveness. Optional person comparison and supervisor acceptance from v5.5 remain available.
