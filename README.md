# Sentinel AI — SIH 2026 Frontend Prototype

Frontend prototype for the Smart India Hackathon 2026 project:
**AI-Based Fake Identity & Document Screening System (SIH 26188)**.

## Run

```bash
npm install
npm run dev
```

Open the local Vite URL shown in the terminal.

## Demo

The login is a prototype login: any Officer ID/password can enter.

The screening page accepts an image upload. The verification pipeline then runs using demo/mock results and leads to a screening result page.

## Current implementation

- Secure-style login
- Command Center dashboard
- New document screening
- Upload/capture UI
- Mock AI verification pipeline
- Screening result
- Risk/confidence scores
- Accept / Flag / Escalate demo actions
- Screening history
- Cases & alerts
- Fictional watchlist
- Analytics
- Blockchain evidence prototype
- Audit trail
- Integration status/settings
- Responsive layout
- Service-ready separation can be added when FastAPI is connected

## Important

AI, biometric, watchlist, database, and Hyperledger outputs are currently **DEMO/MOCK** UI behavior. Replace them with FastAPI endpoints and real models/integrations when available.


## Real OCR
The New Screening flow uses Tesseract.js in the browser to OCR the uploaded image. Extracted text and detected identity fields are sent to the FastAPI backend and stored in SQLite. OCR is a genuine recognition layer; forgery, biometric, watchlist, issuing-database and blockchain components remain adapters until integrated.


## OCR parser update
Passport MRZ parsing now separates surname/given names and uses fixed MRZ field positions, with label-aware fallback extraction.
