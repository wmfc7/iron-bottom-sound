@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Build-IBS.ps1" %*
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" (
  echo Build failed. Please check IBS-build-*.log in the project directory.
) else (
  echo Host and Guest packages created. Check the project dist folder.
)
pause
exit /b %RESULT%
