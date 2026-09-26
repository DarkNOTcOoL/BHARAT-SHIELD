# BHARATSHIELD v5.8 — Step 2 upgrade: AI-assisted altered/replaced-photo inspection

This release keeps the v5.7 tamper-anomaly workflow and adds a dedicated, fully local portrait-integrity inspection layer for SIH26188.

## What changed

- Added `backend/app/photo_substitution.py`.
- Uses the bundled **YuNet** neural face detector to localize the principal portrait in a document image.
- Searches for a plausible surrounding portrait frame; if no frame is visible, it uses a conservative portrait region around the AI-detected face.
- Checks several independent local forensic cues around that region:
  - rectangular/boundary edge discontinuity,
  - JPEG recompression-residual mismatch,
  - local noise-pattern mismatch,
  - overlap with v5.7 strong tamper-anomaly regions.
- A review is raised only when multiple cues agree and at least one content-consistency cue is present. A normal printed photo frame by itself is not treated as fraud.
- Adds a **Photo integrity** evidence view with the localized portrait region and face box.
- Adds `PHOTO_SUBSTITUTION_REVIEW`, `PHOTO_SUBSTITUTION_INCONCLUSIVE`, and not-assessed informational findings.
- Adds a 30-point prototype `forensic_integrity` factor when the portrait review threshold is crossed.
- Generic tamper and photo-substitution findings share the same risk family, so the score uses only the stronger forensic signal instead of double counting related evidence.
- Documents with no detectable portrait are marked **NOT ASSESSED** for photo substitution; this is not a negative or fraud result.

## Important limitation

This is **AI-assisted portrait-substitution inspection**, not a trained universal replacement-photo classifier and not a probability that the document photograph was replaced. YuNet supplies AI face localization; the substitution evidence currently comes from conservative local forensic cues. Legitimate laminates, photo frames, holograms, scans, screenshots, printer/scanner differences and image resaving can change these cues. A clean result does not prove authenticity.

For a production deployment, the next technical milestone is a validated altered-photo segmentation/classification model trained and evaluated on authorized clean/altered print-scan and camera-capture data.

## Upgrade from v5.7

1. Stop the existing server with `Ctrl+C`.
2. Extract v5.8 into a **new folder**.
3. If you want to preserve users/evidence, copy the complete current `backend/private` folder into the new `backend` folder. Do not copy only the database or only `document.key`.
4. Use Python 3.12 and install the new folder's requirements:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

5. Start the app:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

6. Open `http://127.0.0.1:8000` and run a **new** screening. Existing saved screenings do not gain new forensic evidence retroactively.
7. For a document with a sufficiently clear portrait, open **AI-assisted document integrity analysis → Photo integrity**.

## What to tell SIH judges

Use this wording:

**“BHARATSHIELD uses YuNet to localize the document portrait and then performs local multi-cue photo-integrity analysis using boundary, compression, noise and tamper-overlap evidence. Suspicious portrait regions are highlighted for officer review; the score is an explainable anomaly index, not a black-box fraud probability.”**
