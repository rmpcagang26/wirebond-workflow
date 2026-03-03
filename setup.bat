@echo off
title Wire Bond Group - Setup
echo ============================================================
echo   Wire Bond Group - Activity Flow - Setup
echo ============================================================
echo.
echo Installing required Python packages...
echo.
pip install flask pillow pywin32
echo.
echo ============================================================
echo   Setup complete!
echo   Run "run.bat" to start the application.
echo   Then open http://127.0.0.1:5000 in your browser.
echo.
echo   Default admin login:
echo     Username: admin
echo     Password: admin123
echo ============================================================
pause
