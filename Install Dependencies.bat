@echo off
title Install Dependencies
cd /d "%~dp0"
echo ============================================
echo  Wire Bond Group - Install Dependencies
echo ============================================
echo.
echo Installing required Python packages...
echo.
pip install flask werkzeug Pillow pywebview pywin32
echo.
echo ============================================
echo  Done! You can now run:
echo   "Start App (Desktop Window).bat"  for desktop window
echo   "Start App (Browser).bat"         for browser mode
echo ============================================
pause
