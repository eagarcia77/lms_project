@echo off
if not exist .venv\Scripts\python.exe (
  echo Primero ejecute setup_windows.ps1 desde PowerShell.
  exit /b 1
)
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
