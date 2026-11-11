@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "IBS_DICE_SOURCE=os_csprng"
echo =====================================
echo OS CSPRNG TEST MODE - NOT PHYSICAL HRNG
 echo =====================================
python lan_server.py
pause
