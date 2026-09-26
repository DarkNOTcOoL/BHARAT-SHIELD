See ../START_HERE.md. Run from this folder after creating a virtual environment:

    python -m pip install -r requirements.txt
    python manage_users.py --username SNEH --name "Sneh" --role supervisor
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

The frontend is served from ../dist. State is stored in private/ (excluded from distribution).
Use BHARATSHIELD_DATA_DIR only to select another LOCAL state directory, for example during testing.

Regression tests:

    python -m pip install pytest httpx
    python -m pytest -q tests

Tests use isolated temporary storage and deny outbound socket connections.
