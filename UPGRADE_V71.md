# BHARATSHIELD v7.1 — UI refinement on the v7 integrated console

1. Extract the ZIP into a new folder.
2. Copy the complete `backend/private` folder from your working v7.0 installation into the new v7.1 `backend` folder.
3. Do not copy `.venv`.
4. In `backend`, create a Python 3.12 virtual environment and install `requirements.txt`.
5. Start `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
6. Open `http://127.0.0.1:8000` and hard-refresh once (`Ctrl+Shift+R`).

This release changes presentation only. Existing data and verification logic remain compatible.
