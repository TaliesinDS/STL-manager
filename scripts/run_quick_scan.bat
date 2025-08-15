@echo off
REM Double-click wrapper for quick_scan.py
REM Behavior: scans the directory containing this batch file (recursively) and writes quick_scan_report.json there.

set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

REM Prefer 'python' then fallback to 'py'
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%SCRIPT_DIR%quick_scan.py"
) else (
  where py >nul 2>nul
  if %ERRORLEVEL%==0 (
    py "%SCRIPT_DIR%quick_scan.py"
  ) else (
    echo Could not find Python on PATH. Please install Python 3 and retry.
    pause
    exit /b 1
  )
)

echo.
echo Scan complete. Press any key to exit.
pause >nul
popd
