# BHARATSHIELD v7.0 — Integrated officer console

This release consolidates the v6.9 FULL_FIXED frontend into a reproducible React build. It retains the existing colour theme and backend screening rules. It does not add a new trained model or change risk weights.

## Upgrade on Windows

1. Stop the old backend using Ctrl+C. Keep the working v6.9 folder as a backup.
2. Extract this ZIP into a NEW folder.
3. Copy the entire `backend/private` folder from your current installation to the new `BHARATSHIELD/backend` folder. Preserve the database, encryption keys and evidence together. Do not merge different private folders or copy `.venv`.
4. If you customized public issuer trust configuration in `backend/trust`, preserve that configuration too.
5. Open PowerShell inside the NEW `backend` folder. Run these commands separately:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use 64-bit Python 3.12. `py -0p` lists installed runtimes if it is missing. Dependencies need internet during installation; runtime OCR and screening remain local. Node is not required to run the bundled application.

6. Open http://127.0.0.1:8000 and press Ctrl+F5. Sign in using your existing account.
7. Open **Command Center → SIH26188 Demo Readiness**. Run preflight. Supervisors can choose **Prepare all synthetic demo data**. Existing references are preserved.
8. Start a screening. After extraction, check the fields against the original, then run local checks.

## What to look for

- The top Decision Center shows recommendation, rule points, coverage and current case status.
- Priority findings appear before the detailed module outputs.
- Open **Risk factors and unresolved evidence** for the existing score breakdown.
- Open **Inspect document fields and forensic evidence** for OCR boxes and anomaly/photo/stamp/layout/issuer views.
- Open **Reference comparison and linked identity** for registry evidence.
- Open **Optional person comparison and liveness** before a final decision when you want the optional camera checks. Closing this section releases its camera UI.
- Person-check completion refreshes the saved result. If refresh fails, use **Refresh saved evidence** before deciding.
- **Demo Registry** includes native linked-identity search and supervisor actions for document links, travel events and alerts.

The full evidence and local HTML report remain downloadable. A low rule score or a CLEAR lane does not authenticate a document or person.

## Restart

After the initial setup, double-click `START_LOCAL.bat`, or `START_SIH_DEMO.bat` for preflight followed by launch. These launchers require the prepared virtual environment. They do not automatically install Python.

## Windows rehearsal before judging

1. Run preflight with no blocking items. Refresh the browser cache after switching versions.
2. Screen a clean permit, a DOB conflict and a blocked reference. Read the actual factors rather than assuming an exact score when references or history have changed.
3. Run ten consecutive screenings using **New screening** and verify that extraction stays available each time.
4. Open and close each evidence section. Test history navigation and a multi-document case.
5. With a supervisor account, inspect an identity graph and test a fictional audited link/alert action. With an officer account, confirm mutation controls are unavailable.
6. Deny camera permission, retry, then test the optional capture/liveness flow with a consented test subject. Check refresh and the saved report.
7. Test both dense signed-QR fixtures with the installed native decoder.
8. Verify queued supervisor review/claim/decision and blocked-record escalation. Do not clear genuine saved evidence to obtain demo results.
9. Disconnect internet after dependencies are installed and repeat the demo.

Automated Linux tests are documented in `RELEASE_NOTES_V70.md`. A Windows/browser/camera rehearsal remains required. Keep v6.9 as your fallback until your rehearsal passes.

## Developer build

From the project root with a supported Node installation:

```text
npm ci
npm test
npm run build
```

`npm ci` runs the local OCR asset-copy step. `npm run build` includes all console features from source and clears stale output. Do not edit compiled JavaScript or re-add old enhancement scripts. Use `scripts/package-release.py` and `scripts/verify-release.py` when distributing a release.
