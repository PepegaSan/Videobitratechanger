@echo off
setlocal
cd /d "%~dp0"

echo Installing dependencies from requirements.txt ...
python -m pip install --upgrade pip
if errorlevel 1 goto fail
echo Tkinter is included with Python; no pip packages required for the GUI.

echo.
echo Done. Start with start_tool.bat
pause
exit /b 0

:fail
echo Install failed. Is Python on PATH?
pause
exit /b 1
