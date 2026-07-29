@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PI_JS=%~dp0runtime\node_modules\@earendil-works\pi-coding-agent\dist\cli.js"

set "NODE="
if exist "%ProgramFiles%\nodejs\node.exe" set "NODE=%ProgramFiles%\nodejs\node.exe"
if not defined NODE if exist "%LocalAppData%\hermes\node\bin\node.exe" set "NODE=%LocalAppData%\hermes\node\bin\node.exe"
if not defined NODE (
  where node >nul 2>&1 && for /f "delims=" %%I in ('where node') do (
    set "NODE=%%I"
    goto :have_node
  )
)
:have_node
if not defined NODE (
  echo [ERROR] node.exe not found.
  pause
  exit /b 1
)
if not exist "%PI_JS%" (
  echo [ERROR] Pi CLI missing:
  echo   %PI_JS%
  pause
  exit /b 1
)

"%NODE%" "%PI_JS%" %*
exit /b %ERRORLEVEL%
