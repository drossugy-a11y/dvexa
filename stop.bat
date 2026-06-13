@echo off
cd /d "%~dp0"
py -3 stop.py
if errorlevel 1 python stop.py
pause
