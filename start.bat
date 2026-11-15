@echo off
REM Buddy - your offline desktop pet AI
REM Needs Python 3.10+ from python.org (tick "Add python.exe to PATH" during install).
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo Buddy couldn't start. Is Python installed and on your PATH?
    echo Download it free from https://www.python.org/downloads/
    pause
)
