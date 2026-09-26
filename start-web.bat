@echo off
rem Double-click to start the GotIt web version on Windows.
rem First run installs dependencies and opens .env for your API keys.
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
if exist ".venv\Scripts\python.exe" if exist "frontend-v2\node_modules" goto start
%PY% scripts\web.py install
if errorlevel 1 goto end
echo.
echo Fill in your API keys in .env (opened in Notepad), save it, then double-click start-web.bat again.
start "" notepad .env
goto end
:start
%PY% scripts\web.py
:end
pause
