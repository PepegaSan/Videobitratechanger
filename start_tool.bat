@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PY_SCRIPT=%SCRIPT_DIR%mass_bitrate_gui.py"

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python nicht gefunden.
  echo Installiere Python 3 und aktiviere "Add python to PATH".
  pause
  exit /b 1
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo [ERROR] ffmpeg nicht gefunden.
  echo Bitte ffmpeg installieren und PATH setzen.
  pause
  exit /b 1
)

where ffprobe >nul 2>&1
if errorlevel 1 (
  echo [ERROR] ffprobe nicht gefunden.
  echo Bitte ffmpeg/ffprobe installieren und PATH setzen.
  pause
  exit /b 1
)

python "%PY_SCRIPT%"
if errorlevel 1 (
  echo.
  echo [ERROR] Tool wurde mit Fehler beendet.
  pause
  exit /b 1
)

endlocal
