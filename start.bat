@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating Python virtual environment...
  set "PYTHON_CMD="

  rem CrewAI 1.6.1 currently supports Python 3.10 through 3.13.
  rem The generic `py -3` command may select an incompatible Python 3.14.
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.13 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.13"
    if not defined PYTHON_CMD py -3.12 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.12"
    if not defined PYTHON_CMD py -3.11 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.11"
    if not defined PYTHON_CMD py -3.10 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.10"
  )

  if not defined PYTHON_CMD (
    python -c "import sys; raise SystemExit(0 if (3, 10) ^<= sys.version_info[:2] ^<= (3, 13) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
  )

  if not defined PYTHON_CMD (
    echo Python 3.10-3.13 is required. Python 3.14 is not yet supported.
    goto :error
  )

  echo Using compatible Python: !PYTHON_CMD!
  !PYTHON_CMD! -m venv .venv
  if errorlevel 1 goto :error

  echo [2/3] Installing dependencies. The first run can take several minutes...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)

if not exist ".env" copy /Y ".env.example" ".env" >nul
if "%API_PORT%"=="" set "API_PORT=8000"

echo [3/3] Starting REagent with embedded SQLite...
echo API: http://127.0.0.1:%API_PORT%
echo Docs: http://127.0.0.1:%API_PORT%/docs
".venv\Scripts\python.exe" main.py serve --host 127.0.0.1 --port %API_PORT%
goto :eof

:error
echo.
echo Startup failed. Review the error above.
pause
exit /b 1
