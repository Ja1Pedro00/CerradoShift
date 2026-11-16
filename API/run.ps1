# Sobe a API no Windows (PowerShell).
#   .\run.ps1              -> http://127.0.0.1:8000
#   .\run.ps1 -Port 8077   -> outra porta

param(
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Criando ambiente virtual..." -ForegroundColor Cyan
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip -q
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt -q
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Criado .env a partir de .env.example" -ForegroundColor Yellow
}

$args = @("-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "$Port")
if ($Reload) { $args += "--reload" }

Write-Host "API em http://127.0.0.1:$Port/docs" -ForegroundColor Green
& .\.venv\Scripts\python.exe @args
