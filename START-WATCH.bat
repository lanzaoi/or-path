@echo off
REM ============================================================
REM  OR-Path 一键启动 · 实时过程台（Watch）
REM  双击本文件即可：清环境 → 起服务 → 打开浏览器
REM  默认 slug=live-btube（依赖 demo seed；新机器先 orpath.bat setup）
REM  用法：
REM    START-WATCH.bat
REM    START-WATCH.bat my-slug
REM    START-WATCH.bat my-slug my-thread
REM  结束：在本窗口按 Ctrl+C，再按任意键关闭
REM ============================================================
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
if errorlevel 1 (
  echo [ERROR] 无法进入安装目录
  pause
  exit /b 1
)

title OR-Path 实时过程台
chcp 65001 >nul 2>&1

REM 隔离宿主 PYTHONPATH（Hermes 等）避免污染 venv
set "PYTHONPATH="
set "PYTHONHOME="
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"

set "SLUG=%~1"
if "!SLUG!"=="" set "SLUG=live-btube"
set "THREAD=%~2"
if "!THREAD!"=="" set "THREAD=!SLUG!"
set "PORT=%~3"
if "!PORT!"=="" set "PORT=8765"

set "PY="
if exist "%~dp0.venv-314\Scripts\python.exe" set "PY=%~dp0.venv-314\Scripts\python.exe"
if not defined PY if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [ERROR] 找不到 Python。请先: orpath.bat setup
  pause
  exit /b 1
)
if not exist "%~dp0outputs\live-btube-solution.json" (
  if /i "!SLUG!"=="live-btube" (
    echo [WARN] 未找到 live-btube 演示数据。新机器请先: orpath.bat setup
    echo        或: orpath.bat demo-seed
  )
)

if not exist "%~dp0scripts\orpath_watch.py" (
  echo [ERROR] 缺少 scripts\orpath_watch.py
  pause
  exit /b 1
)
if not exist "%~dp0orpath\web\watch.html" (
  echo [ERROR] 缺少 orpath\web\watch.html
  pause
  exit /b 1
)

echo.
echo  ========================================
echo   OR-Path 实时过程台（一键启动）
echo  ----------------------------------------
echo   目录:  %CD%
echo   任务:  !SLUG!
echo   线程:  !THREAD!
echo   端口:  !PORT!
echo   地址:  http://127.0.0.1:!PORT!/?slug=!SLUG!^&thread=!THREAD!
echo  ----------------------------------------
echo   浏览器会自动打开；关掉服务请 Ctrl+C
echo   若页面是旧样式请 Ctrl+F5 强制刷新
echo  ========================================
echo.

"%PY%" "%~dp0scripts\orpath_watch.py" --slug "!SLUG!" --thread-id "!THREAD!" --host 127.0.0.1 --port !PORT!
set "EC=!ERRORLEVEL!"

echo.
if not "!EC!"=="0" (
  echo [ERROR] Watch 退出码 !EC!
) else (
  echo [OK] Watch 已结束
)
echo.
pause
exit /b !EC!

