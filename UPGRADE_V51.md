# Upgrade your working v5 to v5.1

Keep your current v5 as a backup. Use your CURRENT v5 private folder, not the older v4 copy,
so your latest screenings and registry edits are retained.

## 1. Stop and copy

1. Stop v5 with Ctrl+C. Close other terminals running BHARATSHIELD.
2. Extract BHARATSHIELD_LOCAL_v5_1.zip into a NEW folder.
3. COPY the entire `backend/private` folder from your working v5 into the new v5.1 `backend` folder.
4. Copy all files together, including `document.key`, `documents`, `accounts.sqlite3`,
   `bharatshield.db`, and `registry.sqlite3`. Do not move the original or copy the old `.venv`.
5. If the new folder already contains private data you need, stop and back up both folders;
   do not merge their databases or replace keys. The supplied ZIP contains no private data.

## 2. Open PowerShell inside the new backend folder

Run each command separately:

```powershell
py -3.12 --version
```

If this fails, stop here and check the Python 3.12 installation you used for v5.
Do not accidentally create the environment with your other Python 3.14 installation.

```powershell
py -3.12 -m venv .venv
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 and press Ctrl+F5 to refresh the application.
Sign in with your existing v5 username and password. Do NOT recreate SNEH.
Node/npm is not needed to run the supplied build.

v5.1 adds a review_cases table to the copied screening database. Unresolved older cases needing
review/recapture/escalation are queued. Existing evidence and registry snapshots are retained.
Older records without parsed OCR snapshots show that correction history was not recorded.

## 3. Check the repeated-screening fix first

1. Upload `demo_samples/registry/01_match.png`, select Permit, extract and review, then run checks.
2. Click the result's New screening button. The previous document and fields must disappear.
3. Upload a second sample. Extract text locally must be enabled.
4. Complete ten screenings, alternating the result button and sidebar New Screening.
5. During extraction click Cancel & clear and confirm. Upload a fresh image and extract again.
6. Cancel during server submission only with fictional test data. The server may already have saved
   that request: check Screening History before submitting again. Cancellation is not deletion.

The interface blocks document/type edits while processing and stops waiting after 120 seconds.
OCR errors and failed requests return to a retryable form. Old results cannot populate a reset form.

## 4. OCR corrections

- Review the original image beside the parsed fields; use the zoom selector.
- Expand Raw OCR text to inspect the unchanged OCR output.
- Edited fields are highlighted. The server records submitting officer, time and before/after values.
- Digits in names are preserved and flagged; the app does not silently turn 0 into O.
- Missing comparison fields show warnings and remain unverified. Do not copy values from the registry.
- Use `08_name_transposition.png` for AARAV DEOM versus AARAV DEMO. Expected: REVIEW_REQUIRED.
  OCR still may misread text, so compare with the actual printed sample.

## 5. Manual review

1. Open Manual Review. Select PENDING, UNDER_REVIEW, RESOLVED or ALL.
2. Click Manage review, enter a reason, then Claim for review. Officers may claim unassigned cases.
3. Supervisors may assign an existing officer. Another officer cannot steal an assigned case.
4. Open evidence and assess the original, corrections, registry version and other checks.
5. Supervisors select an outcome and Resolve review, with a written explanation.
6. Blocked/revoked synthetic records allow only ESCALATE. Escalation records referral, not clearance.
7. RECAPTURE requests a new image/new screening. Old evidence remains unchanged.
8. Acceptance of queued cases must go through this version-checked review workflow.
9. Reopening requires a supervisor. Earlier decisions and reasons remain in audit history.

A stale review version returns an error. Click Reload queue, reopen the case and review changes.
Recommendation is retained separately from the final officer/supervisor decision.

## 6. Local report

Click Download local report on a screening result. This downloads a self-contained HTML file
with document checks, synthetic registry comparison, person-comparison limitations, OCR corrections,
reference version, evidence hash, review state and audit history.

Open the HTML file locally. For PDF, use your browser's Print > Save as PDF. This is browser-based
PDF export, not a separate server PDF engine. The JSON evidence export remains available.
Protect exported identity information; reports are not encrypted or digitally signed.

## Limits and rollback

All application processing remains local. No government connection, trained tampering/stamp detector,
calibrated biometric verdict, or liveness detection has been added. SQLite metadata remains unencrypted.
Automated frontend tests mock OCR and server responses; they do not establish real OCR accuracy.
Full browser rendering and Windows camera tests still require your local acceptance run.

To roll back, stop v5.1 and run the original backed-up v5 folder with its own untouched private folder.
Do not overwrite that backup with the modified v5.1 database. New v5.1 records will remain only in v5.1.
