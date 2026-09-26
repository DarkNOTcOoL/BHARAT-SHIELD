@echo off
setlocal
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo First complete the setup in START_HERE.md.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8000 in your browser. Press Ctrl+C to stop.
echo For the SIH presentation, START_SIH_DEMO.bat runs the v7.0 preflight first.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
