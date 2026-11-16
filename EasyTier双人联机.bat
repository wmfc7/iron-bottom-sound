@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
rem Auto-locate the actual source root: same directory, extracted child, or parent.
set "IBS_GAME_ROOT=%~dp0"
if exist "%IBS_GAME_ROOT%scripts\start-game.ps1" goto root_ready
if exist "%IBS_GAME_ROOT%iron-bottom-sound\scripts\start-game.ps1" (
    set "IBS_GAME_ROOT=%IBS_GAME_ROOT%iron-bottom-sound\"
    goto root_ready
)
if exist "%IBS_GAME_ROOT%..\scripts\start-game.ps1" (
    set "IBS_GAME_ROOT=%IBS_GAME_ROOT%..\"
    goto root_ready
)
echo [ERROR] Cannot locate the extracted iron-bottom-sound source.
echo Expected scripts\start-game.ps1 next to this launcher, in iron-bottom-sound\,
echo or in the parent folder.
pause
exit /b 1
:root_ready
for %%I in ("%IBS_GAME_ROOT%.") do set "IBS_GAME_ROOT=%%~fI"

set "IBS_LAN_PS=%IBS_GAME_ROOT%\scripts\lan\start-easytier.ps1"
if not exist "%IBS_LAN_PS%" goto missing_lan_script
rem Prefer the user's installed tools; keep any project virtualenv first when present.
if exist "D:\nodejs\node.exe" set "PATH=D:\nodejs;%PATH%"
if exist "D:\Python\python.exe" set "PATH=D:\Python;%PATH%"
if exist "%IBS_GAME_ROOT%\.build-venv\Scripts\python.exe" set "PATH=%IBS_GAME_ROOT%\.build-venv\Scripts;%PATH%"
set "IBS_ROOT=%IBS_GAME_ROOT%"
set "IBS_LAUNCHER_UTF8=1"
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
if defined PYTHONPATH (
    set "PYTHONPATH=%IBS_GAME_ROOT%\backend\src;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%IBS_GAME_ROOT%\backend\src"
)

set "IBS_DICE_CPU_DLL=%IBS_GAME_ROOT%\CPU-RNG\ibs_cpu_rng.dll"
pushd "%IBS_GAME_ROOT%"
if errorlevel 1 goto directory_failed

:menu
cls
echo ===============================================
echo  Iron Bottom Sound IV - EasyTier Multiplayer
echo ===============================================
echo  Source: "%IBS_GAME_ROOT%"
echo.
echo [1] Host: resume existing room
echo [2] Host: create a NEW room
echo [3] Guest: join by PRIVATE invitation URL
echo [4] Host: start EasyTier core from PRIVATE TOML
echo [5] Exit
echo.
echo EasyTier must be connected for options 1-3.
choice /C 12345 /N /M "Select [1-5]: "
if errorlevel 5 goto quit
if errorlevel 4 goto startcore
if errorlevel 3 goto join
if errorlevel 2 goto newroom
if errorlevel 1 goto host
goto menu

:host
call :check_host_assets
if errorlevel 1 goto host_preflight_failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%IBS_LAN_PS%" -Mode Host
set "IBS_RESULT=%ERRORLEVEL%"
goto finish

:newroom
echo WARNING: New room invalidates existing invitation links.
choice /C YN /N /M "Create a new room? [Y/N]: "
if errorlevel 2 goto menu
call :check_host_assets
if errorlevel 1 goto host_preflight_failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%IBS_LAN_PS%" -Mode NewRoom
set "IBS_RESULT=%ERRORLEVEL%"
goto finish

:join
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%IBS_LAN_PS%" -Mode Join
set "IBS_RESULT=%ERRORLEVEL%"
goto finish

:startcore
call :check_host_assets
if errorlevel 1 goto host_preflight_failed
set "EASYTIER_PRIVATE_CONFIG="
set /p "EASYTIER_PRIVATE_CONFIG=Absolute path to your PRIVATE EasyTier TOML: "
if not defined EASYTIER_PRIVATE_CONFIG goto menu
set "EASYTIER_CORE_EXE="
set /p "EASYTIER_CORE_EXE=Absolute path to easytier-core.exe (blank if on PATH): "
if defined EASYTIER_CORE_EXE goto startcore_with_exe
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%IBS_LAN_PS%" -Mode Host -StartCore -EasyTierConfig "%EASYTIER_PRIVATE_CONFIG%"
set "IBS_RESULT=%ERRORLEVEL%"
goto finish

:startcore_with_exe
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%IBS_LAN_PS%" -Mode Host -StartCore -EasyTierConfig "%EASYTIER_PRIVATE_CONFIG%" -CoreExe "%EASYTIER_CORE_EXE%"
set "IBS_RESULT=%ERRORLEVEL%"
goto finish

:host_preflight_failed
set "IBS_RESULT=1"
goto finish

:finish
if not "%IBS_RESULT%"=="0" echo [ERROR] EasyTier exited with code %IBS_RESULT%.
echo.
pause
goto menu

:check_host_assets
if not exist "%IBS_GAME_ROOT%\frontend\dist\index.html" (
    echo [ERROR] Missing frontend\dist\index.html.
    echo First build the project using Run-IBS-Setup.cmd.
    exit /b 1
)
if not exist "%IBS_GAME_ROOT%\CPU-RNG\ibs_cpu_rng.dll" (
    echo [ERROR] Missing CPU-RNG\ibs_cpu_rng.dll.
    exit /b 1
)
exit /b 0

:quit
popd
exit /b 0

:missing_lan_script
echo [ERROR] Missing scripts\lan\start-easytier.ps1.
pause
exit /b 1

:directory_failed
echo [ERROR] Cannot open "%IBS_GAME_ROOT%".
pause
exit /b 1

