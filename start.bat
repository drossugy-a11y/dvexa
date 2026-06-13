@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
title DVexa v1.0

echo.
echo ========================================
echo   DVexa v1.0 - AI Stock Research
echo ========================================
echo.

cd /d "%~dp0"

:: ---- Find Python ----
echo [1/5] Finding Python...
set "PYCMD="
py -3 -c "print('ok')" >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD (
    python -c "print('ok')" >nul 2>&1 && set "PYCMD=python"
)
if not defined PYCMD (
    echo ERROR: Python not found
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('!PYCMD! --version 2^>^&1') do echo   Found: %%v

:: ---- Find Node ----
echo [2/5] Finding Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do echo   Found: Node %%v

:: ---- Python venv + deps ----
echo [3/5] Python dependencies...
if not exist ".venv\Scripts\activate.bat" (
    echo   Creating virtual environment...
    !PYCMD! -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt >nul 2>&1
echo   OK

:: ---- Node deps ----
echo [4/5] Node dependencies...
if not exist "DENG-main\node_modules" (
    echo   Running npm install...
    cd /d "%~dp0DENG-main"
    call npm install
    cd /d "%~dp0"
)
echo   OK

:: ---- Start services ----
echo [5/5] Starting services...
echo.

:: Start backend
echo   Starting backend on port 8000...
start "DVexa-API" cmd /k "cd /d "%~dp0" && call "%~dp0.venv\Scripts\activate.bat" && echo Backend starting... && uvicorn interfaces.api.server:app --host 0.0.0.0 --port 8000"

echo   Waiting 5 seconds...
timeout /t 5 /nobreak >nul

:: Start frontend
echo   Starting frontend on port 3000...
start "DVexa-UI" cmd /k "cd /d "%~dp0DENG-main" && echo Frontend starting... && npm run dev"

echo   Waiting 8 seconds...
timeout /t 8 /nobreak >nul

:: Open browser
start "" "http://localhost:3000"

echo.
echo ========================================
echo   All started!
echo   Backend:  http://localhost:8000/docs
echo   Frontend: http://localhost:3000
echo ========================================
echo.
pause
