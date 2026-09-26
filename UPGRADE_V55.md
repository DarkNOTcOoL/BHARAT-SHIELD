# BHARATSHIELD v5.5 — Optional person comparison and Accept fix

## Install after copying the private folder

1. Stop the old running backend with Ctrl+C. Keep its folder unchanged.
2. Extract this ZIP into a NEW folder.
3. Copy the COMPLETE `backend/private` folder from your CURRENT working installation
   into the new `BHARATSHIELD/backend`. Keep accounts, databases, keys and evidence together.
   Never merge two private folders. Preserve any customized public issuer trust settings
   in `backend/trust` too. Do not copy a virtual environment.
4. Open PowerShell inside the NEW `backend` folder. Run each command separately:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use Python 3.12, 64-bit. `py -0p` lists installed Python versions if 3.12 is missing.
Internet is needed for dependency installation; app operation and inference remain local.
Node/npm is not required to RUN this ZIP; the frontend, English OCR and face models are bundled.

5. Open http://127.0.0.1:8000 and press Ctrl+F5. Use your existing login; do not recreate it.

## Try optional live-camera comparison

1. Screen a document containing a CLEAR photograph: upload, extract, review fields,
   and run local checks. The signed demo permit does NOT contain a portrait; it should
   return INCONCLUSIVE if used for face comparison.
2. Before recording a final decision, scroll to **Optional person comparison**.
3. Leave it off to continue without comparison, or click **Skip person check** to
   explicitly record SKIPPED. Neither choice blocks a document decision.
4. To use it, tick **Enable optional person comparison**, then click **Open live camera**.
5. Allow your browser's camera permission. Keep only one person in frame, facing forward,
   with even lighting. Audio is not requested.
6. Click **Capture person**. The camera stops and a preview appears beside the document.
7. Use **Retake / choose another** if the image is unclear. It reopens the camera for a new capture.
8. Click **Compare locally** only after checking the preview.
9. Read the result. REVIEW_REQUIRED means the local model produced a similarity measurement;
   it does not mean identity verified. INCONCLUSIVE explains which image had no face,
   multiple faces or a face crop that was too small. A missing model returns NOT_RUN.
10. The captured photo is removed from the panel after saving. The server saves results,
    source label, submitting officer, time, model hashes where available and image hash.
    It does not persist the camera photo or face embedding. Original document storage is unchanged.

**Upload consented test photo** is a separate option, explicitly marked UPLOADED_PHOTO.
Camera captures are marked LIVE_CAMERA, but that source label comes from the browser and
is not hardware-attested. A virtual camera, printout or screen replay is not reliably rejected.
Liveness remains NOT_IMPLEMENTED / NOT VERIFIED. No new trained anti-spoof model is included.

## Accept button fix

The previous result screen disabled Accept for all queued cases, including supervisors.
v5.5 provides an explicit route through the existing versioned supervisor review process.

For a case whose document checks are complete:

1. Enter a decision reason of at least 10 characters.
2. Click ACCEPT. The accepted badge appears only after the server saves the decision.

For MANUAL_REVIEW, RECAPTURE or ESCALATE recommendations:

1. Sign in as supervisor and open the screening.
2. Click ACCEPT to open **Supervisor acceptance** on the same screen.
3. Inspect the evidence and enter your reason in **Reason for decision**.
4. If the case is PENDING, click **Claim case for review**.
5. Once UNDER_REVIEW, click **Confirm supervisor acceptance**.
6. A stale-version error means someone changed the review. Use **Reload review state**,
   inspect the updated assignment/state and decide again. Your typed reason is preserved.

Officers see **OPEN SUPERVISOR REVIEW** for queued cases. They cannot bypass supervisor
authorization. An assigned pending case may require supervisor reassignment through Manual
Review. Resolved cases must be reopened before changing a decision. Blocked/revoked synthetic
records still require escalation; acceptance remains unavailable. The system recommendation
is preserved even after a supervisor records a separate acceptance decision.

## Camera troubleshooting

- Permission denied: allow camera access for 127.0.0.1 in your browser, then Retry camera.
- Camera missing/busy: connect it or close other camera applications, then retry.
- Browser unsupported: use a desktop browser that supports getUserMedia on localhost.
- Close camera, leave the page or turn the option off to stop active tracks.
- Cancel/timeout: a server request already received may still finish. Reopen the screening
  before retrying to check whether the attempt was saved. Cancellation does not erase evidence.
- A final accepted/resolved case cannot receive new person evidence until its supervisor
  review is reopened; otherwise start a new screening.

## What stays optional

Face comparison never automatically accepts, flags or rejects a person. New v5.5 document
coverage excludes face/liveness. Existing saved coverage values are preserved. Performing
or skipping the optional check does not change the recommendation or recorded decision.
An existing comparison cannot be overwritten with SKIPPED. The last 30 person-check results
are retained in evidence, with an attempt count and audit events for saved attempts.

This release focuses on optional person comparison and the Accept workflow. The broader
watchlist, trained tamper detector, stamp classification and biometric history search discussed
as future ideas are not added. Real-person accuracy and spoof resistance have not been calibrated.

## Manual checks before presentation

- Run one case with the optional check off and one explicitly skipped.
- Test camera permission denied, Close camera, Retake and a successful capture.
- Compare your own consented capture with a clear document portrait; review the score.
- Test a document with no photograph: expect INCONCLUSIVE, not a fabricated match.
- Test supervisor acceptance of a queued case, ordinary acceptance, and officer restrictions.
- Start another screening and confirm OCR and camera controls reset normally.
- Repeat offline after setup. Check that the webcam indicator switches off after capture/close.

See RELEASE_NOTES_V55.md for automated test coverage and testing limits.

## Restart later

Open PowerShell in this installation's backend folder:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

To roll back, stop v5.5 and start the unchanged previous installation. Keep v5.5 private data
separately; new screenings are not automatically copied back to the old folder.
