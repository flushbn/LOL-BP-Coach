@echo off
cd /d "%~dp0"
python run_ingame_overlay.py
if errorlevel 1 (
  echo startup failed, ensure Python 3.8+ and PySide6 are installed
  pause
)
