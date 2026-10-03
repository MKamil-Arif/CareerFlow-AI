@echo off
title CareerFlow AI
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  py -m venv .venv 2>nul || python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo Python 3.10+ was not found. Install it from https://www.python.org/downloads/ and run this again.
  pause & exit /b 1
)

echo Installing / checking packages...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r backend\requirements.txt
if errorlevel 1 echo (Package install had a problem - trying to start anyway.)

if not exist ".env" if exist ".env.example" copy ".env.example" ".env" >nul

echo.
echo Checking AI providers...
pushd backend
"..\.venv\Scripts\python.exe" -m app.check_ai
popd

echo.
echo Starting CareerFlow AI at http://127.0.0.1:8000  (press Ctrl+C to stop)
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8000"
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --ws none
pause
