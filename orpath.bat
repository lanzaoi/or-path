@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM OR-Path product launcher (relocatable).
REM OpenPi desktop shell REMOVED 2026-07-31 - use menu / pi.
REM NOTE: never use "shift" + "%*" together; on Windows %* ignores shift.

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
set "PYTHONUNBUFFERED=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

if not defined ORPATH_LIVE_SUBAGENT set "ORPATH_LIVE_SUBAGENT=1"

set "CMD=%~1"
REM Double-click / no args -> interactive menu
if "%CMD%"=="" set "CMD=menu"

if /i "%CMD%"=="help" goto :help
if /i "%CMD%"=="menu" goto :menu
if /i "%CMD%"=="doctor" goto :doctor
if /i "%CMD%"=="gate" goto :gate
if /i "%CMD%"=="gate-t3" goto :gate_t3
if /i "%CMD%"=="isolation" goto :isolation
if /i "%CMD%"=="pi" goto :pi
if /i "%CMD%"=="openpi" goto :openpi_removed
if /i "%CMD%"=="t2" goto :t2
if /i "%CMD%"=="run" goto :run
if /i "%CMD%"=="run-full" goto :run_full
if /i "%CMD%"=="gui-demo" goto :gui_demo
if /i "%CMD%"=="status" goto :status
if /i "%CMD%"=="resume" goto :resume
if /i "%CMD%"=="list" goto :list
if /i "%CMD%"=="intake" goto :intake
if /i "%CMD%"=="intake-auto" goto :intake_auto
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
echo  LIVE_SUBAGENT  = !ORPATH_LIVE_SUBAGENT!  (default 1; set 0 or --no-live-subagent for CI)
echo.
echo  Usage:
echo    orpath.bat menu                ^(preferred control plane^)
echo    orpath.bat doctor
echo    orpath.bat pi                  ^(Pi TUI^)
echo    orpath.bat run-full [args...]  ^(auto-intake + live MA default^)
echo    orpath.bat gui-demo
echo    orpath.bat run [args...]
echo    orpath.bat intake --slug SLUG --in FILE
echo    orpath.bat intake-auto --slug SLUG
echo    orpath.bat gate / gate-t3 / gate-intake / subagent-gate
echo    orpath.bat status --thread-id ID
echo    orpath.bat env
echo.
echo  OpenPi: REMOVED 2026-07-31. See ORPATH.md
echo.
exit /b 0

:openpi_removed
echo.
echo  [REMOVED] OpenPi desktop shell deleted from this install (2026-07-31).
echo  Product control plane:  orpath.bat menu
echo  Lightweight chat:       orpath.bat pi   /  pi.bat
echo  Full graph:             orpath.bat run-full  /  gui-demo
echo  See ORPATH.md
echo.
exit /b 2

:menu
"%PY%" "!ORPATH_HOME!\scripts\orpath_menu.py"
set "EC=!ERRORLEVEL!"
if not "!EC!"=="0" (
  echo.
  echo [ERROR] menu exited with code !EC!
  echo PY=!PY!
  pause
)
exit /b !EC!

:envshow
echo ORPATH_HOME=!ORPATH_HOME!
echo ORPATH_WORKDIR=!ORPATH_WORKDIR!
echo ORPATH_LIVE_SUBAGENT=!ORPATH_LIVE_SUBAGENT!
echo PY=!PY!
exit /b 0

:doctor
"%PY%" "!ORPATH_HOME!\scripts\orpath_doctor.py"
exit /b %ERRORLEVEL%

:isolation
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\t2_multiagent_isolation.py"
exit /b %ERRORLEVEL%

:gate
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\t2_gate.py"
exit /b %ERRORLEVEL%

:gate_t3
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\t3_lg_gate.py"
if errorlevel 1 exit /b %ERRORLEVEL%
"%PY%" "!ORPATH_HOME!\scripts\t3_gate.py"
exit /b %ERRORLEVEL%

:paper
"%PY%" "!ORPATH_HOME!\scripts\orpath_paper.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:paper_gate
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\paper_gate.py"
exit /b %ERRORLEVEL%

:paper_10_gate
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\paper_1_0_gate.py"
exit /b %ERRORLEVEL%

:paper_tube
"%PY%" "!ORPATH_HOME!\scripts\run_tube_cut_paper.py"
exit /b %ERRORLEVEL%

:paper_protocol
"%PY%" "!ORPATH_HOME!\scripts\orpath_paper.py" protocol %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:subagent_gate
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\subagent_gate.py"
exit /b %ERRORLEVEL%

:t2
"%PY%" "!ORPATH_HOME!\orpath\run_t2.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:run
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:run_full
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run --auto-intake --fresh %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:gui_demo
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run --fresh --auto-intake --slug gui-demo --thread-id gui-demo --problem-id shortest_path --solve-mode mock --intake-in "!ORPATH_HOME!\fixtures\intake\ok\source.txt"
echo.
echo  [OR-Path] Evidence:
echo    outputs\gui-demo-intake.json
echo    outputs\.agents\gui-demo\
echo    runs\gui-demo\stages\
exit /b %ERRORLEVEL%

:status
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" status %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:resume
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run --resume %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:list
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" list %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:intake
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" intake %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:intake_auto
"%PY%" "!ORPATH_HOME!\scripts\orpath_intake_auto.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:gate_intake
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\intake_gate.py"
exit /b %ERRORLEVEL%

:pi
if not exist "!ORPATH_HOME!\runtime\node_modules\@earendil-works\pi-coding-agent\dist\cli.js" (
  echo [ERROR] Pi runtime missing under install home.
  exit /b 1
)
call "!ORPATH_HOME!\pi.bat" -a %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%
