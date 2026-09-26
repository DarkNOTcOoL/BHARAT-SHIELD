# BHARATSHIELD v6.1 — Multiple-Identity / Identity-Impersonation History

## Upgrade safely

1. Keep the complete working v6.0 folder as a backup.
2. Extract v6.1 into a **new folder**.
3. To retain accounts, document-encryption keys, evidence and screenings, copy the entire old `BHARATSHIELD/backend/private` folder into the new `BHARATSHIELD/backend/` folder. Do not merge individual database/key files.
4. v6.1 creates a new `biometric.key` in that copied/new private folder on first start. Keep this key together with the private folder; losing it makes retained biometric templates unreadable.
5. Use Python 3.12 on Windows:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## New in v6.1

- After a **passed active-liveness challenge**, the neutral live-person frame is converted locally into a normalized SFace biometric template.
- The raw liveness frames are discarded; the SFace template is encrypted locally with Fernet before retention.
- The current template is searched against up to the latest 500 locally retained liveness-passed templates.
- Similar templates are ranked by cosine similarity and compared with the recorded name, DOB and document number.
- A high-similarity candidate under different identity/document attributes creates `BIOMETRIC_IDENTITY_HISTORY_CANDIDATE`, routes the case to manual review and shows the linked screening(s).
- Same-identity/same-document history can appear as a similar-template candidate without creating a multiple-identity alert.
- Biometric history is intentionally kept separate from the document-authenticity risk score because the prototype retrieval thresholds are not deployment-calibrated.
- Evidence export records the search method, candidate thresholds, template hash, candidate screening IDs and privacy/limitation statements.

## Demo

1. Complete a screening for a fictional identity and run **Optional person comparison → Active liveness** using one consenting test person.
2. Start a second screening with a different fictional name/document number.
3. Use the **same consenting test person** for face comparison and active liveness.
4. After the challenge passes, inspect **Multiple-identity / impersonation history**.
5. BHARATSHIELD should show the previous screening as a similarity candidate and route the second case to manual review.

## Important limits

This is prototype biometric retrieval, not a legal or operational identity verdict. The SFace similarity thresholds are not calibrated for the deployment population/cameras. Look-alikes, image quality, ageing, model bias and capture conditions can affect scores. Every candidate requires independent document/registry evidence and human review. Active liveness remains prototype replay resistance rather than certified PAD.
