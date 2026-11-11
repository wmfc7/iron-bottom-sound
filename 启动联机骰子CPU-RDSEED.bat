@echo off
setlocal
cd /d "%~dp0"
set IBS_DICE_SOURCE=cpu_rdseed
python lan_server.py
if errorlevel 1 pause
