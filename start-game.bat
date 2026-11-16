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

set "IBS_START_PS=%IBS_GAME_ROOT%\scripts\start-game.ps1"
if not exist "%IBS_START_PS%" goto missing_script
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

pushd "%IBS_GAME_ROOT%"
if errorlevel 1 goto directory_failed
echo [INFO] Starting standalone mode from "%IBS_GAME_ROOT%".
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%IBS_START_PS%" %*
set "IBS_RESULT=%ERRORLEVEL%"
popd
if "%IBS_RESULT%"=="0" exit /b 0
echo.
echo [ERROR] Game startup exited with code %IBS_RESULT%.
echo Backend error:  "%IBS_GAME_ROOT%\tmp\runtime\backend-error.log"
echo Frontend error: "%IBS_GAME_ROOT%\tmp\runtime\frontend-error.log"
echo Verify Python and Node dependencies are installed before starting.
pause
exit /b %IBS_RESULT%

:missing_script
echo [ERROR] Missing scripts\start-game.ps1.
pause
exit /b 1

:directory_failed
echo [ERROR] Cannot open "%IBS_GAME_ROOT%".
pause
exit /b 1
