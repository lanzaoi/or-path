@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion

REM Preserve original script path BEFORE pushd (pushd maps UNC paths like \\wsl.localhost\... to Z:\)
set "RAW_HOME=%~dp0"
if "!RAW_HOME:~-1!"=="\" set "RAW_HOME=!RAW_HOME:~0,-1!"
set "WSL_RAW_HOME=!RAW_HOME:\=/!"

set "WSL_DISTRO="
set "WSL_LINUX_DIR=/home/lanzao/antigravity/dazzling-bell"
set "IS_WSL_UNC=0"
if /i "!RAW_HOME:~0,16!"=="\\wsl.localhost\" (
  set "IS_WSL_UNC=1"
  for /f "tokens=1,2,* delims=\" %%A in ("!RAW_HOME!") do (
    set "WSL_DISTRO=%%B"
    set "WSL_LINUX_DIR=/%%C"
  )
) else if /i "!RAW_HOME:~0,7!"=="\\wsl$\" (
  set "IS_WSL_UNC=1"
  for /f "tokens=1,2,* delims=\" %%A in ("!RAW_HOME!") do (
    set "WSL_DISTRO=%%B"
    set "WSL_LINUX_DIR=/%%C"
  )
)
set "WSL_LINUX_DIR=!WSL_LINUX_DIR:\=/!"

set "PUSHD_OK=0"
pushd "!RAW_HOME!" 2>nul && set "PUSHD_OK=1"
if "!PUSHD_OK!"=="0" if "!IS_WSL_UNC!"=="0" (
  echo [ERROR] 无法定位安装目录: !RAW_HOME!
  pause
  exit /b 1
)

title OR-Path 运筹优化与智能工作台 · Web Studio ^& Live Watch

set "PORT=%~1"
if "!PORT!"=="" set "PORT=8765"
set "SLUG=%~2"
if "!SLUG!"=="" set "SLUG=live-btube"
set "THREAD=%~3"
if "!THREAD!"=="" set "THREAD=!SLUG!"

set "URL=http://127.0.0.1:!PORT!/?slug=!SLUG!^&thread=!THREAD!"

echo.
echo ======================================================================
echo   OR-Path 运筹优化与智能工作台 · Web Studio ^& Live Watch
echo ----------------------------------------------------------------------
echo   [智能工作舱] 题面文件夹拖拽导入 + 本地混合知识检索 (RAG) + 深度建模
echo   [四大求解器]
echo     * Tube      : 空间异形圆管 3D 展开与四模式激光共切动态规划
echo     * Polyomino : 多联骨牌 CP-SAT 精确覆盖与芯片多目标共边排样
echo     * Microgrid : 园区光储充微电网多时段 LP 与日内滚动时域 MPC
echo     * Routing   : 最短路 / TSP / CVRP / VRPTW 车辆路径规划
echo   [独立验证器] 零信任物理与数学独立重算 (Numbers Truth)
echo ----------------------------------------------------------------------
echo   访问地址: http://127.0.0.1:!PORT!/?slug=!SLUG!^&thread=!THREAD!
echo   退出服务: 请按 Ctrl+C
echo ======================================================================
echo.

REM 1. 优先检查 Windows 原生 Python 虚拟环境 (.venv / .venv-314)
set "PY="
if exist "!RAW_HOME!\.venv-314\Scripts\python.exe" set "PY=!RAW_HOME!\.venv-314\Scripts\python.exe"
if not defined PY if exist "!RAW_HOME!\.venv\Scripts\python.exe" set "PY=!RAW_HOME!\.venv\Scripts\python.exe"
if not defined PY if exist ".venv-314\Scripts\python.exe" set "PY=%CD%\.venv-314\Scripts\python.exe"
if not defined PY if exist ".venv\Scripts\python.exe" set "PY=%CD%\.venv\Scripts\python.exe"
if defined PY goto :win_start

REM 2. 若无 Windows 虚拟环境但存在 WSL 虚拟环境 (.venv/bin/python)，自动通过 WSL 启动并打开 Windows 浏览器
set "HAS_WSL_VENV=0"
if exist "!RAW_HOME!\.venv\bin\activate" set "HAS_WSL_VENV=1"
if exist "!RAW_HOME!\.venv\pyvenv.cfg" set "HAS_WSL_VENV=1"
if exist "!RAW_HOME!\.venv\bin\python" set "HAS_WSL_VENV=1"
if exist ".venv\bin\activate" set "HAS_WSL_VENV=1"
if exist ".venv\pyvenv.cfg" set "HAS_WSL_VENV=1"
if exist ".venv\bin\python" set "HAS_WSL_VENV=1"
if "!IS_WSL_UNC!"=="1" set "HAS_WSL_VENV=1"
if "!HAS_WSL_VENV!"=="1" goto :wsl_start
if not defined ORPATH_HOST set "ORPATH_HOST=127.0.0.1"

REM 3. 检查系统 Python（排除 WindowsApps 商店占位程序，且需具备核心依赖）
for /f "delims=" %%P in ('where python 2^>nul') do (
  if not defined PY (
    echo "%%P" | findstr /i "WindowsApps" >nul || (
      "%%P" -c "import langgraph, ortools" >nul 2>&1 && set "PY=%%P"
    )
  )
)
if defined PY goto :win_start

echo [ERROR] 未检测到可用的 Python 虚拟环境 (.venv\Scripts\python.exe 或 WSL .venv/bin/python)。
echo         请先运行: orpath.bat setup
pause
if "!PUSHD_OK!"=="1" popd
exit /b 1

:wsl_start
if not defined ORPATH_HOST set "ORPATH_HOST=127.0.0.1"
echo [INFO] 检测到 WSL 虚拟环境 (.venv/bin/python)，正在通过 WSL 启动服务并打开浏览器...
start "" "!URL!"
if defined WSL_DISTRO (
  wsl.exe -d "!WSL_DISTRO!" bash -lc "IFS=; D=$(wslpath -u $1 2>/dev/null || echo $2); cd $D && exec .venv/bin/python scripts/orpath_watch.py --slug $3 --thread-id $4 --host $6 --port $5 --no-browser" -- "!WSL_RAW_HOME!" "!WSL_LINUX_DIR!" "!SLUG!" "!THREAD!" "!PORT!" "!ORPATH_HOST!"
) else (
  wsl.exe bash -lc "IFS=; D=$(wslpath -u $1 2>/dev/null || echo $2); cd $D && exec .venv/bin/python scripts/orpath_watch.py --slug $3 --thread-id $4 --host $6 --port $5 --no-browser" -- "!WSL_RAW_HOME!" "!WSL_LINUX_DIR!" "!SLUG!" "!THREAD!" "!PORT!" "!ORPATH_HOST!"
)
set "EC=!ERRORLEVEL!"
if not "!EC!"=="0" (
  echo.
  echo [ERROR] WSL 服务异常退出 (!EC!)。
  pause
)
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:win_start
echo [INFO] 使用 Windows Python 环境: !PY!
start "" "!URL!"
"!PY!" "!RAW_HOME!\scripts\orpath_watch.py" --slug "!SLUG!" --thread-id "!THREAD!" --host 127.0.0.1 --port !PORT! --no-browser
set "EC=!ERRORLEVEL!"
if not "!EC!"=="0" (
  echo.
  echo [ERROR] Web Studio 服务异常退出 (!EC!)。
  pause
)
if "!PUSHD_OK!"=="1" popd
exit /b !EC!
