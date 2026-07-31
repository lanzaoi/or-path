@echo off
REM Double-click friendly starter for OR-Path (keep window open).
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 (
  echo [ERROR] cannot cd to install root
  pause
  exit /b 1
)
title OR-Path
chcp 65001 >nul 2>&1
echo.
echo  Starting OR-Path menu...
echo  Folder: %CD%
echo.
call "%~dp0orpath.bat" menu
set "EC=%ERRORLEVEL%"
echo.
if not "%EC%"=="0" (
  echo [ERROR] exit code %EC%
  pause
  exit /b %EC%
)
pause
exit /b 0
