@echo off
setlocal EnableExtensions
cd /d "%~dp0openpi"

set "NODE="
if exist "%ProgramFiles%\nodejs\node.exe" set "NODE=%ProgramFiles%\nodejs\node.exe"
if not defined NODE if exist "%LocalAppData%\hermes\node\bin\node.exe" set "NODE=%LocalAppData%\hermes\node\bin\node.exe"
if not defined NODE where node >nul 2>&1 && set "NODE=node"
if not defined NODE (
  echo [ERROR] node.exe not found in PATH
  pause
  exit /b 1
)

if not exist "package.json" (
  echo [ERROR] openpi folder missing package.json
  pause
  exit /b 1
)
if not exist "node_modules\" (
  echo [ERROR] dependencies not installed. Run:
  echo   cd /d "%~dp0openpi" ^& npm ci
  pause
  exit /b 1
)

echo.
echo  ========================================
echo   OpenPi  (desktop workbench for Pi)
echo   Repo:   openpi\
echo   Start:  npm run dev
echo   Stop:   close the app window or Ctrl+C
echo  ========================================
echo.

call npm run dev %*
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  echo.
  echo [ERROR] OpenPi exited with code %EC%
  pause
)
exit /b %EC%
