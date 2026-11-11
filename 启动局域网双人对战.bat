@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\lan\start-lan.ps1" -Mode inherit
if errorlevel 1 pause
