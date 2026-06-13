@echo off
chcp 65001 >nul 2>&1
title Stop Stock Radar

echo.
echo Stopping Stock Radar...
echo.

:: Kill by window title
taskkill /FI "WINDOWTITLE eq StockRadar-API*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq StockRadar-UI*" /F >nul 2>&1

:: Kill by port (fallback)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a on port 8000
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " ^| findstr "LISTENING"') do (
    echo   Killing PID %%a on port 3000
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo Done! All services stopped.
echo.
pause
