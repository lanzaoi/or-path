@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM OR-Path product launcher (relocatable).

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
if /i "%CMD%"=="gate-t3" goto :gate_t3
if /i "%CMD%"=="isolation" goto :isolation
if /i "%CMD%"=="pi" goto :pi
if /i "%CMD%"=="openpi" goto :openpi
if /i "%CMD%"=="t2" goto :t2
if /i "%CMD%"=="run" goto :run
if /i "%CMD%"=="status" goto :status
if /i "%CMD%"=="resume" goto :resume
if /i "%CMD%"=="list" goto :list
if /i "%CMD%"=="intake" goto :intake
if /i "%CMD%"=="gate-intake" goto :gate_intake
if /i "%CMD%"=="env" goto :envshow
if /i "%CMD%"=="paper" goto :paper
if /i "%CMD%"=="paper-gate" goto :paper_gate
if /i "%CMD%"=="gate-paper" goto :paper_gate
if /i "%CMD%"=="paper-1.0-gate" goto :paper_10_gate
if /i "%CMD%"=="paper-1_0-gate" goto :paper_10_gate
if /i "%CMD%"=="gate-paper-1.0" goto :paper_10_gate
if /i "%CMD%"=="paper-tube" goto :paper_tube
if /i "%CMD%"=="tube-paper" goto :paper_tube
if /i "%CMD%"=="paper-protocol" goto :paper_protocol
if /i "%CMD%"=="subagent-gate" goto :subagent_gate
if /i "%CMD%"=="gate-subagent" goto :subagent_gate

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
echo    orpath.bat gate-t3
echo    orpath.bat run [args...]
echo    orpath.bat status --thread-id ID
echo    orpath.bat resume --thread-id ID [args...]
echo    orpath.bat list
echo    orpath.bat intake --slug SLUG --in FILE [--assets DIR]
echo    orpath.bat gate-intake
echo    orpath.bat paper template^|review^|gate-research^|plan-log^|protocol ...
echo    orpath.bat paper-gate
echo    orpath.bat paper-1.0-gate
echo    orpath.bat paper-tube
echo    orpath.bat paper-protocol --slug ... --solution ...
echo    orpath.bat subagent-gate
echo    orpath.bat t2 [args...]
echo    orpath.bat pi [args...]
echo    orpath.bat openpi
echo    orpath.bat env
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

:gate_t3
"%PY%" "!ORPATH_HOME!\scripts\t3_lg_gate.py"
if errorlevel 1 exit /b %ERRORLEVEL%
"%PY%" "!ORPATH_HOME!\scripts\t3_gate.py"
exit /b %ERRORLEVEL%

:paper
shift
"%PY%" "!ORPATH_HOME!\scripts\orpath_paper.py" %*
exit /b %ERRORLEVEL%

:paper_gate
"%PY%" "!ORPATH_HOME!\scripts\paper_gate.py"
exit /b %ERRORLEVEL%

:paper_10_gate
"%PY%" "!ORPATH_HOME!\scripts\paper_1_0_gate.py"
exit /b %ERRORLEVEL%

:paper_tube
"%PY%" "!ORPATH_HOME!\scripts\run_tube_cut_paper.py"
exit /b %ERRORLEVEL%

:paper_protocol
shift
"%PY%" "!ORPATH_HOME!\scripts\orpath_paper.py" protocol %*
exit /b %ERRORLEVEL%

:subagent_gate
"%PY%" "!ORPATH_HOME!\scripts\subagent_gate.py"
exit /b %ERRORLEVEL%

:t2
shift
"%PY%" "!ORPATH_HOME!\orpath\run_t2.py" %*
exit /b %ERRORLEVEL%

:run
shift
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run %*
exit /b %ERRORLEVEL%

:status
shift
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" status %*
exit /b %ERRORLEVEL%

:resume
shift
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run --resume %*
exit /b %ERRORLEVEL%

:list
shift
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" list %*
exit /b %ERRORLEVEL%

:intake
shift
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" intake %*
exit /b %ERRORLEVEL%

:gate_intake
"%PY%" "!ORPATH_HOME!\scripts\intake_gate.py"
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
