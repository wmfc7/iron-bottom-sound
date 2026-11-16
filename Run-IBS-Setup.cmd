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

rem The NEW archive puts the builder in set-up\ (old archives used project root).
set "IBS_BUILDER="
if exist "%IBS_GAME_ROOT%\set-up\Install-Build-IBS.ps1" set "IBS_BUILDER=%IBS_GAME_ROOT%\set-up\Install-Build-IBS.ps1"
if not defined IBS_BUILDER if exist "%IBS_GAME_ROOT%\Install-Build-IBS.ps1" set "IBS_BUILDER=%IBS_GAME_ROOT%\Install-Build-IBS.ps1"
if not defined IBS_BUILDER goto missing_builder
if not exist "%IBS_GAME_ROOT%\scripts\build\Build-Host.ps1" goto missing_host_build
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
echo [INFO] Source:  "%IBS_GAME_ROOT%"
echo [INFO] Builder: "%IBS_BUILDER%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%IBS_BUILDER%" -ProjectRoot "%IBS_GAME_ROOT%" %*
set "IBS_RESULT=%ERRORLEVEL%"
popd
echo.
if not "%IBS_RESULT%"=="0" goto build_failed
echo [OK] Build completed. Check "%IBS_GAME_ROOT%\dist".
if exist "%IBS_GAME_ROOT%\set-up\Restore-IBS-Organized-Layout.ps1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%IBS_GAME_ROOT%\set-up\Restore-IBS-Organized-Layout.ps1" -ProjectRoot "%IBS_GAME_ROOT%"
    if errorlevel 1 echo [WARN] Some legacy duplicate files could not be cleaned. Check messages above.
)
pause
exit /b 0

:build_failed
echo [ERROR] Build exited with code %IBS_RESULT%.
echo Check IBS-build-*.log in "%IBS_GAME_ROOT%".
pause
exit /b %IBS_RESULT%

:missing_builder
echo [ERROR] Cannot find set-up\Install-Build-IBS.ps1.
pause
exit /b 1

:missing_host_build
echo [ERROR] Missing scripts\build\Build-Host.ps1.
pause
exit /b 1

:directory_failed
echo [ERROR] Cannot open "%IBS_GAME_ROOT%".
pause
exit /b 1

