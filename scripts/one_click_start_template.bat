@echo off
setlocal ENABLEDELAYEDEXPANSION

REM STL Manager One-Click Start (Template)
REM Creates isolated venv (if absent), installs pinned deps, then launches API & opens browser.
REM User Requirements: Windows 10, bundled Python (preferred) OR python.exe on PATH.

set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..\
pushd %REPO_ROOT%

set VENV_DIR=.venv
set PY_EXEC=python

if exist bundled_python\python.exe (
  set PY_EXEC=bundled_python\python.exe
)

if not exist %VENV_DIR% (
  echo [SETUP] Creating virtual environment...
  %PY_EXEC% -m venv %VENV_DIR%
)

call %VENV_DIR%\Scripts\activate.bat

if not exist requirements.txt (
  echo requirements.txt not found. Please generate via poetry or pip freeze.
  goto :LAUNCH
)

for /f "delims=" %%i in ('dir /b %VENV_DIR%\Lib\site-packages 2^>NUL') do set HAVE_DEPS=1
if not defined HAVE_DEPS (
  echo [SETUP] Installing dependencies...
  pip install --no-cache-dir -r requirements.txt
)

:LAUNCH
echo [RUN] Starting STL Manager API...
start "API" cmd /c "uvicorn stl_manager.main:app --host 127.0.0.1 --port 8077"

REM Small delay to let server boot
ping 127.0.0.1 -n 3 >NUL
start "BROWSER" http://127.0.0.1:8077/

echo [INFO] Press any key to stop (Ctrl+C in API window or close windows)...
pause >NUL
popd
endlocal
