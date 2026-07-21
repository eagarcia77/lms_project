$ErrorActionPreference = "Stop"

Write-Host "Configurando NEXUS EDU XR..." -ForegroundColor Green

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Se creó .env. Añada las credenciales de Google cuando esté listo." -ForegroundColor Yellow
}

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "Instalación completada." -ForegroundColor Green
Write-Host "Ejecute: .\run_windows.bat" -ForegroundColor Cyan
