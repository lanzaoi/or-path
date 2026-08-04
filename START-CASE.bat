@echo off
REM ============================================================
REM  OR-Path Path-A: local case folder + Watch
REM  Double-click friendly. ASCII-safe prompts for cmd.exe.
REM ============================================================
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
if errorlevel 1 (
  echo [ERROR] cannot cd to install root
  pause
  exit /b 1
)

title OR-Path Path-A
chcp 65001 >nul 2>&1

set "PYTHONPATH="
set "PYTHONHOME="
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"

set "PY="
if exist "%~dp0.venv-314\Scripts\python.exe" set "PY=%~dp0.venv-314\Scripts\python.exe"
if not defined PY if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [ERROR] Python not found. Create .venv-314 first.
  pause
  exit /b 1
)

echo.
echo  ========================================
echo   OR-Path Path-A  local case folder
echo  ----------------------------------------
echo   Install: %CD%
echo   Artifacts go into YOUR case folder.
echo   Watch must use the SAME folder + slug.
echo  ========================================
echo.
echo   [1] Watch only  - view existing run
echo   [2] watch-run   - run + open browser  [default]
echo   [3] Exit
echo.
set "MODE="
set /p MODE=Choose 1/2/3 [Enter=2]: 
if "!MODE!"=="" set "MODE=2"
if "!MODE!"=="3" exit /b 0
if not "!MODE!"=="1" if not "!MODE!"=="2" (
  echo [WARN] invalid choice, use 2
  set "MODE=2"
)

set "DEFAULT_CASE=%USERPROFILE%\Documents\orpath-cases\demo1"
echo.
echo  Default case folder:
echo    !DEFAULT_CASE!
echo.
echo  Tip: paste path WITHOUT quotes. Example:
echo    C:\Users\Lanzao\Desktop\test
echo.
set "CASE="
set /p CASE=Case folder [Enter=default]: 
if "!CASE!"=="" set "CASE=!DEFAULT_CASE!"
set "CASE=!CASE:"=!"

if not exist "!CASE!" (
  echo  Creating folder: !CASE!
  mkdir "!CASE!" 2>nul
)
if not exist "!CASE!" (
  echo [ERROR] cannot create case folder: !CASE!
  pause
  exit /b 1
)

set "SLUG="
set /p SLUG=Slug name [Enter=demo1]: 
if "!SLUG!"=="" set "SLUG=demo1"
set "SLUG=!SLUG:"=!"
set "THREAD=!SLUG!"
set "PORT=8765"

echo.
echo  ----------------------------------------
echo   workdir = !CASE!
echo   slug    = !SLUG!
echo   thread  = !THREAD!
echo  ----------------------------------------
echo.

if "!MODE!"=="1" goto :watch_only

echo  Optional problem file PDF/image/txt.
echo  Enter = no intake [recommended first try].
echo.
set "INTAKE="
set /p INTAKE=Problem file full path [optional]: 
set "INTAKE=!INTAKE:"=!"

echo.
echo  LIVE multi-agent? Usually N for stable demo.
set "LIVEQ="
set /p LIVEQ=LIVE y/N [Enter=N]: 
set "LIVE_FLAG="
if /i "!LIVEQ!"=="y" set "LIVE_FLAG=--live"
if /i "!LIVEQ!"=="yes" set "LIVE_FLAG=--live"

echo.
echo  Starting watch-run ...
echo  Browser should open. Stop with Ctrl+C
echo.

if "!INTAKE!"=="" (
  "%PY%" "%~dp0scripts\orpath_watch_run.py" --workdir "!CASE!" --slug "!SLUG!" --thread-id "!THREAD!" --port !PORT! --keep-watch !LIVE_FLAG!
) else (
  if not exist "!INTAKE!" (
    echo [ERROR] problem file not found:
    echo   !INTAKE!
    pause
    exit /b 1
  )
  REM Detect domain from filename via helper [UTF-8 safe]
  set "PC_FLAG="
  set "SM_FLAG="
  set "PID_FLAG=--problem-id adhoc-intake"
  set "DOM="
  for /f "usebackq delims=" %%D in (`"%PY%" "%~dp0scripts\guess_intake_domain.py" "!INTAKE!"`) do set "DOM=%%D"
  if /i "!DOM!"=="poly" (
    set "PC_FLAG=--problem-class polyomino_cover"
    set "SM_FLAG=--solve-mode polyomino"
    set "PID_FLAG=--problem-id polyomino_b_q1"
  )
  if /i "!DOM!"=="tube" (
    set "PC_FLAG=--problem-class tube_cut"
    set "SM_FLAG=--solve-mode tube"
    set "PID_FLAG=--problem-id tube-live"
  )
  echo  domain guess: [!DOM!] !PC_FLAG! !SM_FLAG!
  "%PY%" "%~dp0scripts\orpath_watch_run.py" --workdir "!CASE!" --slug "!SLUG!" --thread-id "!THREAD!" --port !PORT! --keep-watch --auto-intake --intake-in "!INTAKE!" !PID_FLAG! !PC_FLAG! !SM_FLAG! !LIVE_FLAG!
)
set "EC=!ERRORLEVEL!"
goto :end

:watch_only
echo  Opening Watch only ...
echo.
"%PY%" "%~dp0scripts\orpath_watch.py" --workdir "!CASE!" --slug "!SLUG!" --thread-id "!THREAD!" --host 127.0.0.1 --port !PORT!
set "EC=!ERRORLEVEL!"

:end
echo.
if not "!EC!"=="0" (
  echo [ERROR] exit code !EC!
) else (
  echo [OK] finished
)
echo  Artifacts:
echo    !CASE!\outputs\
echo    !CASE!\runs\!SLUG!\
echo.
echo  Open face later:
echo    orpath.bat watch --workdir "!CASE!" --slug !SLUG!
echo.
pause
exit /b !EC!
