@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\start-lan.ps1" -Mode os_csprng
if errorlevel 1 pause
