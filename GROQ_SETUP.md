# Groq setup for BHARATSHIELD

1. Copy `backend/.env.example` to `backend/.env`.
2. Open `backend/.env`.
3. Paste your **new** Groq API key after `GROQ_API_KEY=`.
4. Leave `GROQ_MODEL=qwen/qwen3.6-27b` unless you intentionally choose another Groq vision model.
5. Start FastAPI normally.

Example:

```env
GROQ_API_KEY=YOUR_KEY_HERE
GROQ_MODEL=qwen/qwen3.6-27b
```

Never put the key in React code, `src/`, screenshots, Git, or the ZIP you submit.

When the key is absent, the app still works with local Tesseract OCR and the deterministic Verification Engine.

When the key is present, each uploaded document is sent from FastAPI to Groq Vision. Groq returns structured document fields plus visible visual observations. The Verification Engine then performs MRZ, reference, watchlist, cross-document and risk checks. Groq does not make the final accept/flag/escalate decision.


## Debugging Groq integration

The backend prints a sanitized `[BHARATSHIELD][GROQ ERROR] ...` line when a Groq request fails, without printing the API key. A successful request prints `[BHARATSHIELD][GROQ] Vision analysis complete ...`.
