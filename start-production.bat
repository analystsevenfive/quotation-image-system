@echo off
title Quotation Studio Production Server
echo ========================================================
echo   Quotation Image Automation System - Production Server
echo ========================================================
echo.

REM Verify products catalog exists
if not exist ".data\products.json" (
    echo [!] WARNING: .data\products.json not found.
    echo [*] Importing catalog from 'web sevenfive 75.xlsx'...
    set PYTHONPATH=apps\api
    python -m app.import_catalog "web sevenfive 75.xlsx" --json .data\products.json
)

echo [*] Starting FastAPI Backend on http://127.0.0.1:8000 ...
set PYTHONPATH=apps\api
start "Quotation API (FastAPI)" /min cmd /c "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo [*] Checking Frontend build...
if not exist "apps\web\.next" (
    echo [*] Building Next.js frontend production bundle...
    cd apps\web
    call npm run build
    cd ..\..
)

echo [*] Starting Next.js Production Web Server on http://0.0.0.0:3000 ...
cd apps\web
start "Quotation Web (Next.js)" cmd /c "npm start -- --hostname 0.0.0.0 --port 3000"
cd ..\..

echo.
echo ========================================================
echo   SYSTEM IS READY FOR USERS
echo   Local access:   http://127.0.0.1:3000
echo   Network access: http://^<YOUR_SERVER_IP^>:3000
echo ========================================================
echo.
pause
