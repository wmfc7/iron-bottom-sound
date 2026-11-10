@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>&1 || (echo Python not found && pause && exit /b 1)
python -m pip install -e . || (pause && exit /b 1)
python patch_frontend.py || (pause && exit /b 1)
cd frontend
call pnpm.cmd install || (cd .. && pause && exit /b 1)
call pnpm.cmd run build || (cd .. && pause && exit /b 1)
cd ..
echo The LAN duel files are installed.
pause
