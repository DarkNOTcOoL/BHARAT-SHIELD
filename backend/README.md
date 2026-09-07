# BHARATSHIELD FastAPI Backend

## Run locally (Python 3.14)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

## Add Groq manually

Open `backend/.env` and paste your NEW Groq key only into:

```env
GROQ_API_KEY=PASTE_YOUR_KEY_HERE
GROQ_MODEL=qwen/qwen3.6-27b
```

The key stays on the FastAPI server. React never receives it. If no key is configured, BHARATSHIELD continues with local OCR + deterministic verification.

The current Groq vision adapter uses Qwen 3.6 27B for structured document understanding and visible visual cues. It does **not** independently declare a document genuine. The Verification Engine remains responsible for MRZ, reference, watchlist, cross-document and risk logic.

## API

- `GET /api/health`
- `POST /api/screening/batch`
- `POST /api/screening/upload`
- `GET /api/screenings`
- `GET /api/screening/{screening_id}`
- `POST /api/screening/{screening_id}/decision`
- `GET /api/reference/summary`
- `GET /api/audit-logs`
- `GET /api/watchlist`
- `GET /api/cases`
- `GET /api/dashboard/summary`
