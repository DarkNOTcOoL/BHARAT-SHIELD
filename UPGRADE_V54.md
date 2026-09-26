# BHARATSHIELD v5.4 — Visual field inspection

## Upgrade safely

1. Stop the CURRENT working backend using Ctrl+C.
2. Extract this ZIP into a NEW folder. Keep the old installation unchanged.
3. Copy the ENTIRE current `backend/private` folder into the new `BHARATSHIELD/backend`.
   Do not merge two private folders. Keep databases, keys, evidence and accounts together.
   If you customized `backend/trust/demo_issuers.json`, preserve your approved public trust settings too.
4. Open PowerShell inside the NEW `BHARATSHIELD` folder, then run each line below:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use Python 3.12 (64-bit); if the launcher cannot find it, run `py -0p` to check installed
versions. Do not substitute Python 3.14 without testing dependency support. Do not copy
the old `.venv` or recreate accounts when you have copied private data.

5. Open http://127.0.0.1:8000 and press Ctrl+F5 once. Sign in with existing credentials.
   Node/npm is NOT needed to run the release. Internet is needed only for dependency installation.
6. Start a NEW screening. Old saved records cannot acquire OCR positions retroactively.

## What to test

1. Upload `demo_samples/signed_qr/01_signed_match.png`, choose Permit, leave local
   preparation enabled, and click Extract text locally.
2. In Visual field inspector, click a rectangle or a field-name button. You should see
   the OCR source text, mean word confidence, parsed value and reviewed value.
3. Blue boxes locate OCR text. Amber boxes mean low/unknown confidence or an officer
   correction; they do NOT mean fake. Repeated or ambiguous values may have no box.
4. Change a field manually and confirm its original OCR value remains recorded and
   its box turns amber. Restore the value only by reading the original image.
5. Open Perspective-corrected preview, if a boundary candidate was found. Check all
   four edges. This preview is NOT used for OCR/QR and does not replace the original.
6. Run local checks. Click a box in the result inspector to see the saved OCR,
   reviewed/registry and printed/QR comparisons separately. These are saved snapshots,
   not fresh registry lookups. Load signed demo records as supervisor if not already loaded.
7. Repeated-feature candidates, when present, have dashed amber region boxes on the
   original view. Legitimate QR patterns, text or backgrounds can trigger them.
8. Start another screening and confirm extraction is enabled after adding a new image.
9. After setup, repeat with Wi-Fi disconnected to check offline operation on your machine.

## Exact scope and limitations

- Real OCR word rectangles, normalized to the EXIF-oriented original, remain aligned
  when the displayed image is resized. There are no hard-coded identity values.
- Geometry is browser-supplied and stored in the extraction notes. It is not independently
  attested. It never changes risk, QR signature validity, registry results or decisions.
- Field confidence is the mean of available word confidence values only when every word
  has a valid score. It is not a calibrated probability or authenticity score.
- If the same text appears more than once, no guessed field box is drawn. Missing word
  coordinates, unavailable dimensions and unsupported layouts also produce no box.
- Perspective correction is an inspection PREVIEW, not an OCR improvement claim. OCR
  still uses the existing original/prepared comparison flow. No automatic crop is accepted.
- English OCR remains bundled. Extraction on arbitrary real IDs is NOT guaranteed;
  document layout, language, resolution and glare still affect results. No real-ID
  accuracy benchmark was performed for this release.
- Repeat-region boxes come from the existing ORB feature-cluster heuristic. They are
  not a trained tamper model. No photo-replacement, stamp-forgery or font-classifier
  capability is claimed. `TAMPERING: NOT_IMPLEMENTED` remains intentionally unchanged.
- Missing synthetic records are not evidence of fraud. Valid demo signatures do not
  authenticate printed documents or holders. There is no government database connection.
- Original bytes, encryption, user roles, supervisor review and signed demo trust are retained.

## Testing and development

See `RELEASE_NOTES_V54.md` for executed checks and remaining manual validation.
Developers: run `npm ci` (copies OCR runtime assets), `npm test`, then `npm run build`.
The distributable already contains the production build, English OCR and existing face models.

To restart later, open PowerShell in this installation's backend folder and run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

To roll back, stop v5.4 and start your unchanged old installation. New v5.4 records are
not automatically copied back; retain the complete v5.4 private folder as a separate backup.
