@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%start_tool.ps1"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
if errorlevel 1 (
  echo.
  echo [ERROR] PowerShell-Start fehlgeschlagen.
  pause
  exit /b 1
)

endlocal
