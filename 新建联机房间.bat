@echo off
chcp 65001 >nul
cd /d "%~dp0"
python lan_server.py --host 0.0.0.0 --port 8765 --new-room --scenario IBS-S-03
pause
