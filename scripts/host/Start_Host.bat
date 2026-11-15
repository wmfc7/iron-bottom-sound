@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Host.ps1"
if errorlevel 1 (
  echo Host startup failed. Check the error above.
  pause
)
