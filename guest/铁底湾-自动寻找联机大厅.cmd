@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0auto_find_lobby.ps1"
if errorlevel 1 (
  echo.
  echo Discovery failed; read the messages above.
  pause
)
