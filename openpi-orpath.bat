@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0orpath.bat" openpi %*
exit /b %ERRORLEVEL%
