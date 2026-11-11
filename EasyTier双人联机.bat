@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

:menu
cls
echo ==============================================
echo  Iron Bottom Sound IV - EasyTier Multiplayer
echo ==============================================
echo.
echo [1] Host: resume existing room (recommended)
echo [2] Host: create NEW room (rotates invites)
echo [3] Guest: open the private invitation URL
echo [4] Host: start EasyTier core from private TOML
 echo [5] Exit
 echo.
 echo EasyTier GUI/core must be connected for options 1-3.
choice /C 12345 /N /M "Select [1-5]: "
if errorlevel 5 exit /b 0
if errorlevel 4 goto startcore
if errorlevel 3 goto join
if errorlevel 2 goto newroom
if errorlevel 1 goto host

:host
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\lan\start-easytier.ps1" -Mode Host
goto finish
:newroom
echo WARNING: New room invalidates both current invite links.
choice /C YN /N /M "Create a new room? [Y/N]: "
if errorlevel 2 goto menu
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\lan\start-easytier.ps1" -Mode NewRoom
goto finish
:join
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\lan\start-easytier.ps1" -Mode Join
goto finish
:startcore
set "EASYTIER_PRIVATE_CONFIG="
set /p "EASYTIER_PRIVATE_CONFIG=Absolute path to your PRIVATE EasyTier TOML: "
if not defined EASYTIER_PRIVATE_CONFIG goto menu
set "EASYTIER_CORE_EXE="
set /p "EASYTIER_CORE_EXE=Absolute path to easytier-core.exe (blank if on PATH): "
if defined EASYTIER_CORE_EXE (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\lan\start-easytier.ps1" -Mode Host -StartCore -EasyTierConfig "%EASYTIER_PRIVATE_CONFIG%" -CoreExe "%EASYTIER_CORE_EXE%"
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\lan\start-easytier.ps1" -Mode Host -StartCore -EasyTierConfig "%EASYTIER_PRIVATE_CONFIG%"
)
goto finish
:finish
if errorlevel 1 echo Launcher failed. Check the displayed error and docs\lan\EASYTIER.md.
echo.
pause
goto menu
