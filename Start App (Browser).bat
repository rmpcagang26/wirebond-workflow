@echo off
title Wire Bond Group - Activity Flow System
cd /d "%~dp0"
echo Starting Wire Bond Group Activity Flow System...
echo Open your browser to: http://127.0.0.1:5000
start "" "http://127.0.0.1:5000"
python app.py
pause
