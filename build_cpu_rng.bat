@echo off
setlocal
cd /d "%~dp0"
where cl.exe >nul 2>&1
if errorlevel 1 (
 echo [ERROR] Microsoft C compiler not found.
 echo Please install Visual Studio Build Tools with C++ and use:
 echo    x64 Native Tools Command Prompt for VS 2022 or newer
 pause
 exit /b 1
)
cl.exe /nologo /LD /O2 /W4 /GS ibs_cpu_rng.c /Fe:ibs_cpu_rng.dll
if errorlevel 1 (
 echo [ERROR] CPU RNG DLL build failed.
 pause
 exit /b 1
)
echo Built ibs_cpu_rng.dll. CPU instruction support is validated again on launch.
pause
