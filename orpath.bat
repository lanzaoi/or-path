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

REM Isolate from host PYTHONPATH (e.g. Hermes) which can break venv native wheels.

set "PYTHONPATH="

set "PYTHONHOME="

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

if /i "%CMD%"=="setup" goto :setup

if /i "%CMD%"=="bootstrap" goto :setup

if /i "%CMD%"=="demo-seed" goto :demo_seed

if /i "%CMD%"=="seed" goto :demo_seed

if /i "%CMD%"=="l2-gate" goto :l2_gate

if /i "%CMD%"=="pack-release" goto :pack_release

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

if /i "%CMD%"=="demo-m0" goto :demo_m0

if /i "%CMD%"=="m0" goto :demo_m0

if /i "%CMD%"=="watch" goto :watch
if /i "%CMD%"=="face" goto :face
if /i "%CMD%"=="start-watch" goto :face

if /i "%CMD%"=="watch-run" goto :watch_run

if /i "%CMD%"=="watchrun" goto :watch_run

if /i "%CMD%"=="p3" goto :watch_run

if /i "%CMD%"=="v0-watch-gate" goto :v0_watch_gate

if /i "%CMD%"=="gate-v0-watch" goto :v0_watch_gate

if /i "%CMD%"=="watch-gate" goto :v0_watch_gate

if /i "%CMD%"=="p3-gate" goto :p3_gate

if /i "%CMD%"=="gate-p3" goto :p3_gate

if /i "%CMD%"=="watch-run-gate" goto :p3_gate

if /i "%CMD%"=="p4-gate" goto :p4_gate

if /i "%CMD%"=="gate-p4" goto :p4_gate

if /i "%CMD%"=="session-gate" goto :p4_gate

if /i "%CMD%"=="p5-gate" goto :p5_gate

if /i "%CMD%"=="gate-p5" goto :p5_gate

if /i "%CMD%"=="polish-gate" goto :p5_gate

if /i "%CMD%"=="m0-gate" goto :m0_gate
if /i "%CMD%"=="m1-gate" goto :m1_gate
if /i "%CMD%"=="m2-gate" goto :m2_gate
if /i "%CMD%"=="gate-m2" goto :m2_gate
if /i "%CMD%"=="gate-m1" goto :m1_gate

if /i "%CMD%"=="tube-live-gate" goto :tube_live_gate

if /i "%CMD%"=="gate-tube-live" goto :tube_live_gate

if /i "%CMD%"=="gate-m0" goto :m0_gate

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

echo    orpath.bat setup               ^(L1: venv + npm Pi + demo seed + doctor^)

echo    orpath.bat doctor

echo    orpath.bat demo-seed           ^(copy demo/seed into workdir^)

echo    orpath.bat menu                ^(preferred control plane^)

echo    orpath.bat watch [--slug SLUG] [--thread-id ID] [--port N] [--no-browser]
echo    orpath.bat face                 ^(one-click Watch, default live-btube seed^)
echo    START-WATCH.bat                 ^(double-click same; run setup first on fresh machine^)

echo    orpath.bat pack-release        ^(L2 zip under dist/^)

echo    orpath.bat l2-gate --zip PATH

echo    orpath.bat watch-run [--slug SLUG] [--workdir DIR] [--live] [--keep-watch]   ^(P3/M1^)

echo    orpath.bat demo-m0 [--slug m0] [--live]

echo    orpath.bat v0-watch-gate

echo    orpath.bat p3-gate

echo    orpath.bat p4-gate

echo    orpath.bat p5-gate

echo    orpath.bat m0-gate
echo    orpath.bat m1-gate
echo    orpath.bat m2-gate

echo    orpath.bat tube-live-gate

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

echo  Live process face: orpath.bat watch   ^(not folder browse^)

echo  P3 watch+run:      orpath.bat watch-run

echo  M0 demo:           orpath.bat demo-m0 ^(mock numbers + evidence^)

echo  OpenPi: REMOVED 2026-07-31. See ORPATH.md

echo.

exit /b 0

:openpi_removed

echo.

echo  [REMOVED] OpenPi desktop shell deleted from this install (2026-07-31).

echo  Product control plane:  orpath.bat menu

echo  Lightweight chat:       orpath.bat pi   /  pi.bat

echo  Full graph:             orpath.bat run-full  /  gui-demo

echo  Live face:              orpath.bat watch

echo  P3 watch+run:           orpath.bat watch-run

echo  See ORPATH.md

echo.

exit /b 2

:setup

REM Prefer system Python to create venv when venv missing; bootstrap re-resolves.
where python >nul 2>&1 && set "BOOT_PY=python"
if exist "!ORPATH_HOME!\.venv-314\Scripts\python.exe" set "BOOT_PY=!ORPATH_HOME!\.venv-314\Scripts\python.exe"
if not defined BOOT_PY set "BOOT_PY=%PY%"
"%BOOT_PY%" "!ORPATH_HOME!\scripts\bootstrap_orpath.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:demo_seed

"%PY%" "!ORPATH_HOME!\scripts\install_demo_seed.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:pack_release

"%PY%" "!ORPATH_HOME!\scripts\pack_release.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:l2_gate

"%PY%" "!ORPATH_HOME!\scripts\l2_release_gate.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

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

echo PYTHONPATH=!PYTHONPATH!

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

:v0_watch_gate

set "ORPATH_LIVE_SUBAGENT=0"

"%PY%" "!ORPATH_HOME!\scripts\v0_watch_gate.py"

exit /b %ERRORLEVEL%

:m0_gate
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\m0_demo_gate.py"
exit /b %ERRORLEVEL%


:m1_gate
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\m1_gate.py"
exit /b %ERRORLEVEL%


:m2_gate
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\m2_gate.py"
exit /b %ERRORLEVEL%

:tube_live_gate
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\tube_live_gate.py" %2 %3 %4 %5
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

:watch

"%PY%" "!ORPATH_HOME!\scripts\orpath_watch.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%


:face
REM One-click product face. Default slug=live-btube when no args.
if "%~2"=="" (
  "%PY%" "!ORPATH_HOME!\scripts\orpath_watch.py" --slug live-btube --thread-id live-btube --host 127.0.0.1 --port 8765
) else (
  "%PY%" "!ORPATH_HOME!\scripts\orpath_watch.py" %2 %3 %4 %5 %6 %7 %8 %9
)
exit /b %ERRORLEVEL%

:watch_run

"%PY%" "!ORPATH_HOME!\scripts\orpath_watch_run.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%

:p3_gate

set "ORPATH_LIVE_SUBAGENT=0"

"%PY%" "!ORPATH_HOME!\scripts\p3_watch_run_gate.py"

exit /b %ERRORLEVEL%

:p4_gate

set "ORPATH_LIVE_SUBAGENT=0"

set "ORPATH_PI_SESSION=0"

"%PY%" "!ORPATH_HOME!\scripts\p4_session_gate.py"

exit /b %ERRORLEVEL%

:p5_gate

set "ORPATH_LIVE_SUBAGENT=0"

set "ORPATH_PI_SESSION=0"

set "ORPATH_LANGFUSE=0"

"%PY%" "!ORPATH_HOME!\scripts\p5_polish_gate.py"

exit /b %ERRORLEVEL%

:demo_m0

"%PY%" "!ORPATH_HOME!\scripts\orpath_demo_m0.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%

:gui_demo

"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run --fresh --auto-intake --slug gui-demo --thread-id gui-demo --problem-id shortest_path --solve-mode mock --intake-in "!ORPATH_HOME!\fixtures\intake\ok\source.txt"

echo.

echo  [OR-Path] Evidence:

echo    outputs\gui-demo-intake.json

echo    outputs\.agents\gui-demo\

echo    runs\gui-demo\stages\

echo    Live face: orpath.bat watch --slug gui-demo

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



