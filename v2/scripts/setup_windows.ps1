param(
    [string]$Python = "py"
)

$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "[NODARIS V2] Criando ambiente virtual..."
& $Python -m venv .venv

Write-Host "[NODARIS V2] Atualizando pip..."
& .\.venv\Scripts\python.exe -m pip install --upgrade pip

Write-Host "[NODARIS V2] Instalando dependencias..."
& .\.venv\Scripts\python.exe -m pip install -e ".[dev,build]"

Write-Host ""
Write-Host "Ambiente pronto."
Write-Host "Para abrir a UI:"
Write-Host "  .\.venv\Scripts\python.exe -m nodaris.ui.main"
