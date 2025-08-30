Param(
    [switch]$InstallSample
)

# Clean, single bootstrap script (no duplicates).
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$projectRoot = Resolve-Path (Join-Path $scriptDir '..')
Set-Location $projectRoot

Write-Host 'Bootstrapping dev environment in:' (Get-Location)

# Choose Python executable
if (Get-Command python -ErrorAction SilentlyContinue) { $pythonCmd = 'python' }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $pythonCmd = 'py -3' }
else { Write-Error 'Python not found on PATH. Install Python 3.8+ and re-run this script.'; exit 1 }

$venv = Join-Path $projectRoot '.venv'
if (-not (Test-Path $venv)) {
    Write-Host 'Creating virtual environment at' $venv
    & $pythonCmd -m venv $venv
} else {
    Write-Host '.venv exists — using existing virtual environment.'
}

# Activate for this session
$activate = Join-Path $venv 'Scripts\Activate.ps1'
if (Test-Path $activate) {
    Write-Host 'Activating virtual environment...'
    . $activate
} else {
    Write-Error "Activation script not found at $activate"; exit 1
}

Write-Host 'Upgrading pip...'
& $pythonCmd -m pip install --upgrade pip

Write-Host 'Installing requirements...'
& $pythonCmd -m pip install -r requirements.txt

Write-Host 'Initializing database schema...'
& $pythonCmd scripts\init_db.py

if ($InstallSample) {
    if (Test-Path 'scripts\load_sample.py') {
        Write-Host 'Loading sample fixture...'
        & $pythonCmd scripts\load_sample.py
    } else {
        Write-Warning 'Sample loader not found; skipping.'
    }
}

Write-Host ''
Write-Host 'Bootstrap complete. To activate in new shells run:'
Write-Host '  .\.venv\Scripts\Activate.ps1'
