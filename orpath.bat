@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM OR-Path product launcher (relocatable).
REM Install root = directory containing this bat (or ORPATH_HOME if already set).

if not defined ORPATH_HOME (
  set "ORPATH_HOME=%~dp0"
)
if "!ORPATH_HOME:~-1!"=="\" set "ORPATH_HOME=!ORPATH_HOME:~0,-1!"

if not defined ORPATH_WORKDIR set "ORPATH_WORKDIR=!ORPATH_HOME!"

cd /d "!ORPATH_HOME!"
if errorlevel 1 (
  echo [ERROR] cannot cd to ORPATH_HOME=!ORPATH_HOME!
  exit /b 1
)

set "PY="
if exist "!ORPATH_HOME!\.venv-314\Scripts\python.exe" set "PY=!ORPATH_HOME!\.venv-314\Scripts\python.exe"
if not defined PY if exist "!ORPATH_HOME!\.venv\Scripts\python.exe" set "PY=!ORPATH_HOME!\.venv\Scripts\python.exe"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [ERROR] Python not found. Create .venv-314 under install root.
  exit /b 1
)

set "PYTHONNOUSERSITE=1"
set "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1"

set "CMD=%~1"
if "%CMD%"=="" set "CMD=help"

if /i "%CMD%"=="help" goto :help
if /i "%CMD%"=="doctor" goto :doctor
if /i "%CMD%"=="gate" goto :gate
if /i "%CMD%"=="isolation" goto :isolation
if /i "%CMD%"=="pi" goto :pi
if /i "%CMD%"=="openpi" goto :openpi
if /i "%CMD%"=="t2" goto :t2
if /i "%CMD%"=="env" goto :envshow

echo [ERROR] unknown command: %CMD%
goto :help

:help
echo.
echo  OR-Path launcher  (relocatable)
echo  ORPATH_HOME    = !ORPATH_HOME!
echo  ORPATH_WORKDIR = !ORPATH_WORKDIR!
echo.
echo  Usage:
echo    orpath.bat doctor
echo    orpath.bat isolation
echo    orpath.bat gate
echo    orpath.bat t2 [args...]
echo    orpath.bat pi [args...]
echo    orpath.bat openpi
echo    orpath.bat env
echo.
echo  Optional:
echo    set ORPATH_HOME=D:\apps\orpath
echo    set ORPATH_WORKDIR=E:\cases\demo
echo.
exit /b 0

:envshow
echo ORPATH_HOME=!ORPATH_HOME!
echo ORPATH_WORKDIR=!ORPATH_WORKDIR!
echo PY=!PY!
exit /b 0

:doctor
"%PY%" "!ORPATH_HOME!\scripts\orpath_doctor.py"
exit /b %ERRORLEVEL%

:isolation
"%PY%" "!ORPATH_HOME!\scripts\t2_multiagent_isolation.py"
exit /b %ERRORLEVEL%

:gate
"%PY%" "!ORPATH_HOME!\scripts\t2_gate.py"
exit /b %ERRORLEVEL%

:t2
shift
"%PY%" "!ORPATH_HOME!\orpath\run_t2.py" %*
exit /b %ERRORLEVEL%

:pi
if not exist "!ORPATH_HOME!\runtime\node_modules\@earendil-works\pi-coding-agent\dist\cli.js" (
  echo [ERROR] Pi runtime missing under install home.
  exit /b 1
)
shift
call "!ORPATH_HOME!\pi.bat" -a %*
exit /b %ERRORLEVEL%

:openpi
echo.
echo  [OR-Path] ORPATH_HOME=!ORPATH_HOME!
echo  [OR-Path] OpenPi project folder must be this install home.
echo  [OR-Path] running doctor...
echo.
"%PY%" "!ORPATH_HOME!\scripts\orpath_doctor.py"
if errorlevel 1 (
  echo [ERROR] doctor failed - refusing OpenPi start.
  exit /b 1
)
call "!ORPATH_HOME!\openpi.bat" %*
exit /b %ERRORLEVEL%
