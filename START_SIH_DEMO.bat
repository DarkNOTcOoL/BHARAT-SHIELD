@echo off
setlocal
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo BHARATSHIELD v7.0 requires a prepared Python 3.12 virtual environment.
  echo Follow START_HERE.md first.
  pause
  exit /b 1
)
echo Running SIH26188 local demo preflight...
".venv\Scripts\python.exe" demo_preflight.py
if errorlevel 1 (
  echo.
  echo Preflight found a blocking issue. Fix it before the judge demo.
  pause
  exit /b 1
)
echo.
echo Starting BHARATSHIELD v7.0 at http://127.0.0.1:8000
echo Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
