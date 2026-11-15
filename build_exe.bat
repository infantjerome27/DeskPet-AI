@echo off
REM Build a standalone Buddy.exe with PyInstaller (run this on Windows).
REM Needs: Python 3.10+ installed with "Add python.exe to PATH" ticked.
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller
python -m PyInstaller --onefile --windowed --name Buddy main.py
echo.
echo Done! Your app is in the dist folder: dist\Buddy.exe
echo (If it ever fails to start, rebuild without --windowed to see errors.)
pause
