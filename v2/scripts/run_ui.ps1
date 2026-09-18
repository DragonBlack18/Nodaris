$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    throw "Ambiente .venv nao encontrado. Execute .\scripts\setup_windows.ps1 primeiro."
}

& .\.venv\Scripts\python.exe -m nodaris.ui.main
