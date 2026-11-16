@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0guest\auto_find_lobby.ps1"
if errorlevel 1 (
  echo.
  echo Discovery failed. Connect EasyTier and try again.
  pause
)
