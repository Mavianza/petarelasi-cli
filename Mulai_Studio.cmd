@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 studio_setup.py
goto finished
:use_python
python studio_setup.py
:finished
if errorlevel 1 pause
endlocal
