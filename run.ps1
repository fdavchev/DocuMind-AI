# run.ps1 — start DocuMind AI with the correct interpreter.
#
# WHY THIS EXISTS:
# Terminals no longer auto-activate the virtualenv (see .vscode/settings.json),
# which avoids another project's venv leaking in. The trade is that `python`
# means the *global* interpreter until you activate. This script activates this
# project's venv and starts the app with it, so there is one command to get it
# right.
#
#   .\run.ps1

$ErrorActionPreference = "Stop"

$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "No virtualenv found at $venvPython" -ForegroundColor Red
    Write-Host "Create it with:  python -m venv venv; venv\Scripts\activate; pip install -r requirements.txt"
    exit 1
}

Write-Host "Using $venvPython" -ForegroundColor DarkGray
& $venvPython -m streamlit run (Join-Path $PSScriptRoot "app.py")
