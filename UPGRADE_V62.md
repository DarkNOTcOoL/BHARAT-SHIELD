# BHARATSHIELD v6.2 — Automatic Document-Type Routing + Type-Aware OCR

## Upgrade safely

1. Keep your complete working v6.1 folder as a backup.
2. Extract v6.2 into a **new folder**.
3. To retain accounts, encrypted documents, audit records, biometric-history templates and keys, copy the entire old `BHARATSHIELD/backend/private` folder into the new `BHARATSHIELD/backend/` folder. Do not merge or copy individual database/key files.
4. Use Windows Python 3.12:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## New in v6.2

- New local explainable **document-type router** for Passport, Visa, Aadhaar, Voter ID/EPIC, Driving Licence, PAN, National ID, Permit and Travel Authorization.
- Strong OCR cues such as TD3 passport MRZ, UIDAI/Aadhaar labels and 12-digit structure, Income Tax/PAN patterns, Election Commission/EPIC patterns, Driving Licence labels, and visa-specific fields are independently weighted.
- The router runs locally; no cloud classifier or external API is called.
- Automatic routing is conservative: strong evidence can choose the parser/check family; ambiguous or weak evidence is routed to officer confirmation rather than silently treated as a different document.
- Manual document-type override remains available.
- The packaged runtime performs **type-aware field re-parsing** after OCR (`AUTO_DOCUMENT_FIELD_REPARSE_V1`) when automatic routing changes the document family. This improves extraction of document-number and visa/ID-specific labels without using registry values.
- Backend independently re-checks the OCR type before applying document-specific rules. A strong mismatch creates `DOCUMENT_TYPE_CONFLICT` and manual review.
- When the packaged prebuilt frontend is used, v6.2 marks untouched document rows as **AUTO DETECT** at local-check submission. If the officer changes the type selector, that row becomes a manual override.
- When automatic routing changes type, the backend conservatively reparses only OCR-derived/blank fields. **Officer-corrected values are never overwritten by automatic routing.**
- Screening evidence stores the detected type, confidence-like routing score, supporting cues, runner-up, source, limitation and backend/client routing evidence.

## Demo

1. New Screening → upload a clear Passport, Visa, Aadhaar, PAN, EPIC, Driving Licence or supplied Permit/Visa demo image.
2. Leave the document row untouched to keep **AUTO DETECT** active. The existing selector is the fallback/manual override.
3. Click **Extract text locally**, review/correct fields, then **Run local checks**.
4. The result should show **Automatic document-type routing** with the screening type, detected type and supporting OCR cues.
5. For a mismatch demo, deliberately choose the wrong type before local checks. The server should retain the officer selection but surface `DOCUMENT_TYPE_CONFLICT` for review when OCR evidence strongly favors another type.

## Important limits

The router is an explainable OCR-evidence routing system, not a document-authenticity classifier and not a trained universal document classifier. OCR errors, unusual layouts, multilingual documents, damaged documents and look-alike templates can make the type ambiguous or wrong. Automatic routing does not authenticate an issuer. Officer review remains required when evidence is uncertain or conflicting.
