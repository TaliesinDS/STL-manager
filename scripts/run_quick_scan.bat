@echo off
REM Double-click wrapper for quick_scan.py
REM Behavior: scans the directory containing this batch file (recursively) and writes quick_scan_report.json there.
REM Adds dynamic vocab (--tokenmap tokenmap.md), ignore list, domain summary, and JSON report.

set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

set TOKENMAP=tokenmap.md
set IGNORE_FILE=ignored_tokens.txt
set JSON_OUT=quick_scan_report.json

if not exist "%IGNORE_FILE%" (
  echo # Tokens to suppress from unknown list>"%IGNORE_FILE%"
  echo base>>"%IGNORE_FILE%"
  echo body>>"%IGNORE_FILE%"
  echo arm>>"%IGNORE_FILE%"
  echo head>>"%IGNORE_FILE%"
  echo left>>"%IGNORE_FILE%"
  echo right>>"%IGNORE_FILE%"
  echo weapon>>"%IGNORE_FILE%"
  echo preview>>"%IGNORE_FILE%"
  echo # add more noisy tokens as desired>>"%IGNORE_FILE%"
)

set ARGS=--unknown-top 300 --json-out "%JSON_OUT%" --emit-known-summary --ignore-file "%IGNORE_FILE%"
if exist "%TOKENMAP%" (
  set ARGS=%ARGS% --tokenmap "%TOKENMAP%"
) else (
  echo [info] tokenmap.md not found alongside batch; proceeding with embedded defaults.
)

echo Running quick_scan with arguments: %ARGS%

REM Prefer 'python' then fallback to 'py'
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%SCRIPT_DIR%quick_scan.py" %ARGS%
) else (
  where py >nul 2>nul
  if %ERRORLEVEL%==0 (
    py "%SCRIPT_DIR%quick_scan.py" %ARGS%
  ) else (
    echo Could not find Python on PATH. Please install Python 3 and retry.
    pause
    exit /b 1
  )
)

echo.
echo Scan complete. JSON: %JSON_OUT%
echo Press any key to exit.
pause >nul
popd
