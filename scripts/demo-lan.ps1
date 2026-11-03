param([Parameter(Mandatory=$true)][string]$LanIp)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$localNpm = Join-Path $PWD '.local-tools/bin'
if (Test-Path $localNpm) { $env:PATH = $localNpm + ';' + $env:PATH }
$env:PUBLIC_BASE_URL = "http://${LanIp}:5173"
$env:ALLOWED_ORIGINS = "http://${LanIp}:5173,http://localhost:5173,http://127.0.0.1:5173"
$env:COOKIE_SECURE = 'false'
docker compose up -d --build postgres_dev backend
if ($LASTEXITCODE -ne 0) { throw 'Không khởi động được backend/Docker.' }
docker compose exec backend alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration thất bại.' }
$barista = Read-Host 'Mật khẩu demo cho barista.demo' -MaskInput
$cashier = Read-Host 'Mật khẩu demo cho cashier.demo' -MaskInput
docker compose exec -e "DEMO_BARISTA_PASSWORD=$barista" -e "DEMO_CASHIER_PASSWORD=$cashier" backend python -m app.seed
if ($LASTEXITCODE -ne 0) { throw 'Seed thất bại.' }
$env:VITE_USE_MOCK = '0'
$env:VITE_API_BASE = '/api/v1'
Set-Location frontend
Write-Host "Mở http://${LanIp}:5173/staff/login trên các máy cùng Wi-Fi."
npm run dev
