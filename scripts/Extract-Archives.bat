@echo off
REM ================================================================
REM  Extract-Archives.bat
REM  Convenience launcher for Extract-Archives.ps1
REM  Edit the configuration section below, then double-click or run.
REM ================================================================

REM -------- Configuration Defaults (You can still change via menu) --------
REM Root directory containing archives
set "ROOT=D:\Models"
REM Optional separate output root (leave empty to use ROOT)
set "OUTPUT_ROOT="
REM Space-separated list of archive extensions (each with leading dot)
set "EXTENSIONS=.rar .zip .7z"
REM Optional explicit log CSV path (leave empty for auto-generated)
set "LOGCSV="
REM Optional explicit 7z path (leave empty to auto-detect). Example:
REM set "SEVENZIP=C:\Program Files\7-Zip\7z.exe"
set "SEVENZIP="
REM Always-applied options (advanced users). Leave blank normally.
set "ALWAYS_OPTIONS="
REM -----------------------------------------------------------------------

setlocal ENABLEDELAYEDEXPANSION

REM Detect PowerShell executable explicitly (prefer Windows PowerShell for widest compatibility)
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL_EXE%" (
  echo [ERROR] Could not locate Windows PowerShell at %POWERSHELL_EXE%
  echo Aborting.
  pause
  exit /b 1
)

REM Resolve script path (this batch file sits next to the .ps1)
set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%Extract-Archives.ps1"
if not exist "%PS1%" (
  echo [ERROR] Could not find Extract-Archives.ps1 at "%PS1%"
  exit /b 1
)

REM Build command
set "BASE=\"%POWERSHELL_EXE%\" -NoLogo -NoProfile -ExecutionPolicy Bypass -File \"%PS1%\" -Root \"%ROOT%\""

if defined OUTPUT_ROOT set "BASE=%BASE% -OutputRoot \"%OUTPUT_ROOT%\""
if defined SEVENZIP set "BASE=%BASE% -SevenZipPath \"%SEVENZIP%\""

REM Append extensions ONCE (PowerShell array param) -- multiple -Extensions causes errors
set "BASE=%BASE% -Extensions %EXTENSIONS%"

if defined LOGCSV set "BASE=%BASE% -LogCsv \"%LOGCSV%\""

REM ================= INTERACTIVE MENU =====================
echo.
echo  Archive Extraction Launcher
echo  Root: %ROOT%
if defined OUTPUT_ROOT (echo  OutputRoot: %OUTPUT_ROOT%) else (echo  OutputRoot: (same as root))
echo  Extensions: %EXTENSIONS%
echo.
echo  Select a run mode:
echo    1 ^) Dry run (preview only)
echo    2 ^) First pass extract (mark extracted) 
echo    3 ^) Incremental (skip by marker)
echo    4 ^) Overwrite (re-extract EVERYTHING) [danger]
echo    5 ^) List candidates only (inventory)
echo    6 ^) Custom options (manual entry)
echo    7 ^) Change basics (ROOT / OUTPUT_ROOT / EXTENSIONS) then show menu again
echo    8 ^) Quit
echo.

:promptChoice
choice /c 12345678 /n /m "Select option: "
set "SEL=%errorlevel%"
if "%SEL%"=="8" goto :eof
if "%SEL%"=="7" goto :reconfigure
if "%SEL%"=="1" set "ACTION_OPTIONS=-DryRun"
if "%SEL%"=="2" set "ACTION_OPTIONS=-MarkExtracted"
if "%SEL%"=="3" set "ACTION_OPTIONS=-SkipIfMarker"
if "%SEL%"=="4" set "ACTION_OPTIONS=-Overwrite -MarkExtracted"
if "%SEL%"=="5" set "ACTION_OPTIONS=-ListOnly"
if "%SEL%"=="6" (
  set /p ACTION_OPTIONS="Enter custom options (e.g. -SkipIfMarker -SkipIfNonEmpty): "
  if not defined ACTION_OPTIONS set "ACTION_OPTIONS="
)
goto :build

:reconfigure
echo.
set /p ROOT="Enter ROOT (current %ROOT%): "
if not defined ROOT set "ROOT=D:\Models"
set /p OUTPUT_ROOT="Enter OUTPUT_ROOT (blank=same as root) (current '%OUTPUT_ROOT%'): "
set /p EXTENSIONS="Enter extensions space separated (current %EXTENSIONS%): "
if not defined EXTENSIONS set "EXTENSIONS=.rar .zip .7z"
echo.
goto :promptChoice

:build

set "BASE=%BASE% %ACTION_OPTIONS% %ALWAYS_OPTIONS%"
echo.
echo  Using options: %ACTION_OPTIONS% %ALWAYS_OPTIONS%

echo ------------------------------------------------
echo Running: %BASE%
echo ------------------------------------------------
echo.
echo [EXEC] %BASE%
echo.
%BASE%
set ERR=%ERRORLEVEL%

echo.
echo Completed with exit code %ERR%.
if %ERR% NEQ 0 (
  echo.
  echo One or more errors occurred. See log CSV (if any) for details.
)
echo.
echo Press any key to close...
pause >nul
exit /b %ERR%
