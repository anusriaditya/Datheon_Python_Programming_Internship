@echo off
title File Organiser & Cleanup Utility
cd /d "%~dp0"
python organizer.py --path "%USERPROFILE%\Downloads"
echo.
pause
