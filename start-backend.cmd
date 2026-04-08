@echo off
setlocal

set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [ERROR] Virtual environment Python not found at:
  echo         %PY%
  echo Create it first, then install backend dependencies.
  exit /b 1
)

cd /d "%ROOT%"
"%PY%" -m uvicorn main:app --reload
