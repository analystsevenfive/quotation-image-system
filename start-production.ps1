# Quotation Image Automation System - Production Startup Script (PowerShell)
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Quotation Image Automation System - Production Server" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Ensure .data/products.json exists
if (-not (Test-Path ".data\products.json")) {
    Write-Host "[*] Importing product catalog from 'web sevenfive 75.xlsx'..." -ForegroundColor Yellow
    $env:PYTHONPATH = "apps/api"
    python -m app.import_catalog "web sevenfive 75.xlsx" --json .data/products.json
}

# Ensure frontend build exists
if (-not (Test-Path "apps\web\.next")) {
    Write-Host "[*] Building Next.js production bundle..." -ForegroundColor Yellow
    Push-Location "apps\web"
    npm run build
    Pop-Location
}

# Start FastAPI Backend
Write-Host "[*] Starting FastAPI Backend on port 8000..." -ForegroundColor Green
$backendJob = Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONPATH = 'apps/api'; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000" -PassThru

# Start Next.js Production Frontend
Write-Host "[*] Starting Next.js Production Web Server on port 3000..." -ForegroundColor Green
$frontendJob = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd apps/web; npm start -- --hostname 0.0.0.0 --port 3000" -PassThru

# Get Local IP addresses for sharing
$ips = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -notlike "169.254.*" }).IPAddress

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "  SYSTEM IS READY FOR USERS!" -ForegroundColor Green
Write-Host "  Local URL:    http://127.0.0.1:3000" -ForegroundColor White
if ($ips) {
    foreach ($ip in $ips) {
        Write-Host "  LAN URL:      http://${ip}:3000" -ForegroundColor Yellow
    }
}
Write-Host "========================================================" -ForegroundColor Green
Write-Host "Press Ctrl+C or close this window when done."
