@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion

REM OR-Path Unified CLI & Web Studio Launcher (Windows + WSL cross-environment)
REM NOTE: never use "shift" + "%*" together; on Windows %* ignores shift.

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

if not defined ORPATH_HOME (
    set "ORPATH_HOME=!RAW_HOME!"
)
if "!ORPATH_HOME:~-1!"=="\" set "ORPATH_HOME=!ORPATH_HOME:~0,-1!"
if not defined ORPATH_WORKDIR set "ORPATH_WORKDIR=!ORPATH_HOME!"
set "WSL_RAW_WORKDIR=!ORPATH_WORKDIR:\=/!"

set "ALL_ARGS=%*"
set "SUB_ARGS="
if defined ALL_ARGS (
    for /f "tokens=1,* delims= " %%A in ("!ALL_ARGS!") do set "SUB_ARGS=%%B"
)

set "PUSHD_OK=0"
pushd "!ORPATH_HOME!" 2>nul && set "PUSHD_OK=1"
if "!PUSHD_OK!"=="0" if "!IS_WSL_UNC!"=="0" (
    echo [ERROR] cannot cd/pushd to ORPATH_HOME=!ORPATH_HOME!
    exit /b 1
)

set "PYTHONPATH="
set "PYTHONHOME="
set "PYTHONNOUSERSITE=1"
set "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1"
set "PYTHONUNBUFFERED=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "CMD=%~1"
if "!CMD!"=="" set "CMD=studio"

if /i "!CMD!"=="help" goto :help
if /i "!CMD!"=="-h" goto :help
if /i "!CMD!"=="--help" goto :help

REM 1. Prefer Windows native virtualenv (.venv-314 or .venv)
set "PY="
if exist "!RAW_HOME!\.venv-314\Scripts\python.exe" set "PY=!RAW_HOME!\.venv-314\Scripts\python.exe"
if not defined PY if exist "!RAW_HOME!\.venv\Scripts\python.exe" set "PY=!RAW_HOME!\.venv\Scripts\python.exe"
if not defined PY if exist "!ORPATH_HOME!\.venv-314\Scripts\python.exe" set "PY=!ORPATH_HOME!\.venv-314\Scripts\python.exe"
if not defined PY if exist "!ORPATH_HOME!\.venv\Scripts\python.exe" set "PY=!ORPATH_HOME!\.venv\Scripts\python.exe"
if not defined PY if exist ".venv-314\Scripts\python.exe" set "PY=%CD%\.venv-314\Scripts\python.exe"
if not defined PY if exist ".venv\Scripts\python.exe" set "PY=%CD%\.venv\Scripts\python.exe"

REM 2. If no Windows virtualenv exists, check for WSL virtualenv (.venv/bin/python)
if not defined PY (
    set "HAS_WSL_VENV=0"
    if exist "!RAW_HOME!\.venv\bin\activate" set "HAS_WSL_VENV=1"
    if exist "!RAW_HOME!\.venv\pyvenv.cfg" set "HAS_WSL_VENV=1"
    if exist "!RAW_HOME!\.venv\bin\python" set "HAS_WSL_VENV=1"
    if exist ".venv\bin\activate" set "HAS_WSL_VENV=1"
    if exist ".venv\pyvenv.cfg" set "HAS_WSL_VENV=1"
    if exist ".venv\bin\python" set "HAS_WSL_VENV=1"
    if "!IS_WSL_UNC!"=="1" set "HAS_WSL_VENV=1"
    if "!HAS_WSL_VENV!"=="1" goto :wsl_dispatch
)

REM 3. Check system Python (excluding WindowsApps Store stub)
if not defined PY (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if not defined PY (
            echo "%%P" | findstr /i "WindowsApps" >nul || (
                if /i "!CMD!"=="setup" (
                    "%%P" -c "import sys" >nul 2>&1 && set "PY=%%P"
                ) else if /i "!CMD!"=="bootstrap" (
                    "%%P" -c "import sys" >nul 2>&1 && set "PY=%%P"
                ) else (
                    "%%P" -c "import langgraph, ortools" >nul 2>&1 && set "PY=%%P"
                )
            )
        )
    )
)

if not defined PY (
    echo [ERROR] Python virtualenv not found ^(.venv\Scripts\python.exe or WSL .venv/bin/python^).
    echo         Run: orpath.bat setup
    if "!PUSHD_OK!"=="1" popd
    exit /b 1
)

if /i "%CMD%"=="studio" goto :studio
if /i "%CMD%"=="web" goto :studio
if /i "%CMD%"=="face" goto :face
if /i "%CMD%"=="watch" goto :watch
if /i "%CMD%"=="watch-run" goto :watch_run
if /i "%CMD%"=="menu" goto :menu
if /i "%CMD%"=="setup" goto :setup
if /i "%CMD%"=="bootstrap" goto :setup
if /i "%CMD%"=="doctor" goto :doctor
if /i "%CMD%"=="demo-seed" goto :demo_seed
if /i "%CMD%"=="seed" goto :demo_seed

REM --- 4 Core OR Solvers & Independent Validator ---
if /i "%CMD%"=="tube-solve" goto :tube_solve
if /i "%CMD%"=="tube" goto :tube_solve
if /i "%CMD%"=="polyomino-solve" goto :polyomino_solve
if /i "%CMD%"=="polyomino" goto :polyomino_solve
if /i "%CMD%"=="polyomino-q3" goto :polyomino_q3
if /i "%CMD%"=="microgrid-solve" goto :microgrid_solve
if /i "%CMD%"=="microgrid" goto :microgrid_solve
if /i "%CMD%"=="routing-solve" goto :routing_solve
if /i "%CMD%"=="routing" goto :routing_solve
if /i "%CMD%"=="demo-m0" goto :demo_m0
if /i "%CMD%"=="m0-demo" goto :demo_m0
if /i "%CMD%"=="m0" goto :demo_m0
if /i "%CMD%"=="validate" goto :validate

REM --- Pipeline & Knowledge RAG ---
if /i "%CMD%"=="run" goto :run
if /i "%CMD%"=="run-full" goto :run_full
if /i "%CMD%"=="resume" goto :resume
if /i "%CMD%"=="intake" goto :intake
if /i "%CMD%"=="intake-auto" goto :intake_auto
if /i "%CMD%"=="status" goto :status
if /i "%CMD%"=="list" goto :list
if /i "%CMD%"=="gui-demo" goto :gui_demo
if /i "%CMD%"=="paper" goto :paper
if /i "%CMD%"=="t2" goto :t2
if /i "%CMD%"=="knowledge-sync" goto :knowledge_sync
if /i "%CMD%"=="knowledge-rebuild" goto :knowledge_rebuild
if /i "%CMD%"=="knowledge-export" goto :knowledge_export
if /i "%CMD%"=="knowledge-ingest" goto :knowledge_ingest
if /i "%CMD%"=="knowledge-retrieve" goto :knowledge_retrieve
if /i "%CMD%"=="knowledge-smoke" goto :knowledge_smoke
if /i "%CMD%"=="knowledge-eval" goto :knowledge_eval
if /i "%CMD%"=="promote-run" goto :promote_run
if /i "%CMD%"=="memory-search" goto :memory_search
if /i "%CMD%"=="memory-record" goto :memory_record
if /i "%CMD%"=="memory-list" goto :memory_list
if /i "%CMD%"=="tools-list" goto :tools_list
if /i "%CMD%"=="mcp" goto :mcp
if /i "%CMD%"=="mcp-ortools" goto :mcp_ortools
if /i "%CMD%"=="pack-release" goto :pack_release

REM --- Verification Gates & Benchmarks ---
if /i "%CMD%"=="workbench-gate" goto :workbench_gate
if /i "%CMD%"=="problem-workbench-gate" goto :workbench_gate
if /i "%CMD%"=="v0-watch-gate" goto :v0_watch_gate
if /i "%CMD%"=="watch-gate" goto :v0_watch_gate
if /i "%CMD%"=="dialogue-gate" goto :dialogue_gate
if /i "%CMD%"=="steer-gate" goto :dialogue_gate
if /i "%CMD%"=="t1-gate" goto :t1_gate
if /i "%CMD%"=="t2-gate" goto :t2_gate
if /i "%CMD%"=="gate" goto :t2_gate
if /i "%CMD%"=="m0-gate" goto :m0_gate
if /i "%CMD%"=="m1-gate" goto :m1_gate
if /i "%CMD%"=="m2-gate" goto :m2_gate
if /i "%CMD%"=="p3-gate" goto :p3_gate
if /i "%CMD%"=="p5-gate" goto :p5_gate
if /i "%CMD%"=="tube-geometry-gate" goto :tube_geometry_gate
if /i "%CMD%"=="tube-collab-gate" goto :tube_collab_gate
if /i "%CMD%"=="tube-redteam-gate" goto :tube_redteam_gate
if /i "%CMD%"=="tube-live-gate" goto :tube_live_gate
if /i "%CMD%"=="tube-benchmark" goto :tube_benchmark
if /i "%CMD%"=="bench" goto :bench
if /i "%CMD%"=="vrp-baseline" goto :vrp_baseline
if /i "%CMD%"=="l2-gate" goto :l2_gate
if /i "%CMD%"=="promote-run-gate" goto :promote_run_gate

goto :help

:wsl_dispatch
if /i "!CMD!"=="studio" goto :wsl_studio
if /i "!CMD!"=="web" goto :wsl_studio
if /i "!CMD!"=="face" (
    if "%~2"=="" goto :wsl_studio
)
if /i "!CMD!"=="watch" (
    if "%~2"=="" goto :wsl_studio
)
if defined WSL_DISTRO (
    wsl.exe -d "!WSL_DISTRO!" bash -lc "IFS=; D=$(wslpath -u $1 2>/dev/null || echo $2); W=$(wslpath -u $3 2>/dev/null || echo $D); export ORPATH_HOME=$D; export ORPATH_WORKDIR=$W; shift 3; cd $D && exec ./orpath.sh $*" -- "!WSL_RAW_HOME!" "!WSL_LINUX_DIR!" "!WSL_RAW_WORKDIR!" !CMD! !SUB_ARGS!
) else (
    wsl.exe bash -lc "IFS=; D=$(wslpath -u $1 2>/dev/null || echo $2); W=$(wslpath -u $3 2>/dev/null || echo $D); export ORPATH_HOME=$D; export ORPATH_WORKDIR=$W; shift 3; cd $D && exec ./orpath.sh $*" -- "!WSL_RAW_HOME!" "!WSL_LINUX_DIR!" "!WSL_RAW_WORKDIR!" !CMD! !SUB_ARGS!
)
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:wsl_studio
set "PORT=%~2"
if "!PORT!"=="" set "PORT=8765"
set "SLUG=%~3"
if "!SLUG!"=="" set "SLUG=live-btube"
set "THREAD=%~4"
if "!THREAD!"=="" set "THREAD=!SLUG!"
set "URL=http://127.0.0.1:!PORT!/?slug=!SLUG!^&thread=!THREAD!"
echo.
echo ======================================================================
echo   OR-Path 运筹优化与智能工作台 · Web Studio ^& Live Watch (WSL 模式)
echo   四大核心求解器: Tube 异形圆管 ^| Polyomino 多联骨牌 ^| Microgrid 微电网 ^| Routing 路径规划
echo   访问地址: http://127.0.0.1:!PORT!/?slug=!SLUG!^&thread=!THREAD!
echo   退出服务: 请按 Ctrl+C
echo ======================================================================
echo.
start "" "!URL!"
if defined WSL_DISTRO (
    wsl.exe -d "!WSL_DISTRO!" bash -lc "IFS=; D=$(wslpath -u $1 2>/dev/null || echo $2); cd $D && exec .venv/bin/python scripts/orpath_watch.py --slug $3 --thread-id $4 --host 0.0.0.0 --port $5 --no-browser" -- "!WSL_RAW_HOME!" "!WSL_LINUX_DIR!" "!SLUG!" "!THREAD!" "!PORT!"
) else (
    wsl.exe bash -lc "IFS=; D=$(wslpath -u $1 2>/dev/null || echo $2); cd $D && exec .venv/bin/python scripts/orpath_watch.py --slug $3 --thread-id $4 --host 0.0.0.0 --port $5 --no-browser" -- "!WSL_RAW_HOME!" "!WSL_LINUX_DIR!" "!SLUG!" "!THREAD!" "!PORT!"
)
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:help
echo ======================================================================
echo   OR-Path 运筹优化与智能工作台 · 命令行主控入口
echo ======================================================================
echo   [1. Web Studio 与实时看板]
echo     START.bat                      一键启动 Web Studio ^& Live Watch (:8765)
echo     orpath.bat studio              启动 Web Studio 智能工作台并打开浏览器
echo     orpath.bat watch               启动 Live Watch 服务 (--slug live-btube)
echo     orpath.bat menu                启动交互式控制台菜单
echo.
echo   [2. 四大核心运筹求解器]
echo     orpath.bat tube-solve          空间异形圆管 3D 展开与四模式共切 DP 求解器
echo     orpath.bat polyomino-solve     多联骨牌 CP-SAT 二维精确覆盖求解器
echo     orpath.bat polyomino-q3        芯片/板材多目标排样与共边最大化求解器
echo     orpath.bat microgrid-solve     园区光储充微电网多时段 LP 与日内滚动 MPC 求解器
echo     orpath.bat routing-solve       最短路 / TSP / CVRP / VRPTW 车辆路径规划求解器
echo     orpath.bat demo-m0             运行 M0 最短路端到端基准演示
echo.
echo   [3. 独立验证器与系统诊断]
echo     orpath.bat validate            独立物理与数学重算验证器 (Numbers Truth)
echo     orpath.bat doctor              运行 Python 环境、求解器与工作台健康检查
echo     orpath.bat setup               初始化虚拟环境、释放演示种子并运行 doctor
echo     orpath.bat knowledge-sync      同步本地混合知识库 (BM25 + ONNX bge-m3)
echo.
echo   [4. 核心验证门禁]
echo     orpath.bat workbench-gate      Web Studio 智能做题工作舱契约门禁
echo     orpath.bat v0-watch-gate       Live Watch 实时过程看板门禁
echo     orpath.bat t1-gate / t2-gate   求解器与验证器核心门禁
echo     orpath.bat m1-gate / m2-gate   工作区隔离与骨牌领域端到端门禁
echo ======================================================================
if "!PUSHD_OK!"=="1" popd
exit /b 0

:studio
set "PORT=%~2"
if "!PORT!"=="" set "PORT=8765"
set "SLUG=%~3"
if "!SLUG!"=="" set "SLUG=live-btube"
set "THREAD=%~4"
if "!THREAD!"=="" set "THREAD=!SLUG!"
set "URL=http://127.0.0.1:!PORT!/?slug=!SLUG!^&thread=!THREAD!"
start "" "!URL!"
"%PY%" "!ORPATH_HOME!\scripts\orpath_watch.py" --slug "!SLUG!" --thread-id "!THREAD!" --host 127.0.0.1 --port !PORT! --no-browser
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:face
if "%~2"=="" (
    "%PY%" "!ORPATH_HOME!\scripts\orpath_watch.py" --slug live-btube --thread-id live-btube --host 127.0.0.1 --port 8765
) else (
    "%PY%" "!ORPATH_HOME!\scripts\orpath_watch.py" !SUB_ARGS!
)
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:watch
if "%~2"=="" (
    "%PY%" "!ORPATH_HOME!\scripts\orpath_watch.py" --slug live-btube --thread-id live-btube --host 127.0.0.1 --port 8765
) else (
    "%PY%" "!ORPATH_HOME!\scripts\orpath_watch.py" !SUB_ARGS!
)
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:watch_run
"%PY%" "!ORPATH_HOME!\scripts\orpath_watch_run.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:menu
"%PY%" "!ORPATH_HOME!\scripts\orpath_menu.py"
set "EC=!ERRORLEVEL!"
if not "!EC!"=="0" (
    echo.
    echo [ERROR] menu exited with code !EC!
    pause
)
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:setup
set "BOOT_PY=%PY%"
if exist "!ORPATH_HOME!\.venv-314\Scripts\python.exe" set "BOOT_PY=!ORPATH_HOME!\.venv-314\Scripts\python.exe"
"%BOOT_PY%" "!ORPATH_HOME!\scripts\bootstrap_orpath.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:doctor
"%PY%" "!ORPATH_HOME!\scripts\orpath_doctor.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:demo_seed
"%PY%" "!ORPATH_HOME!\scripts\install_demo_seed.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:tube_solve
"%PY%" "!ORPATH_HOME!\scripts\b_tube_solve.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:polyomino_solve
"%PY%" "!ORPATH_HOME!\tools\solve_polyomino.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:polyomino_q3
"%PY%" "!ORPATH_HOME!\tools\solve_polyomino_q3.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:microgrid_solve
"%PY%" "!ORPATH_HOME!\tools\solve_microgrid.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:routing_solve
"%PY%" "!ORPATH_HOME!\tools\solve_ortools.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:demo_m0
"%PY%" "!ORPATH_HOME!\scripts\orpath_demo_m0.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:validate
"%PY%" "!ORPATH_HOME!\tools\validate_solution.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:run
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:run_full
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run --auto-intake --fresh !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:resume
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run --resume !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:intake
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" intake !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:intake_auto
"%PY%" "!ORPATH_HOME!\scripts\orpath_intake_auto.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:status
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" status !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:list
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" list !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:gui_demo
"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run --fresh --auto-intake --slug gui-demo --thread-id gui-demo --problem-id shortest_path --solve-mode mock --intake-in "!ORPATH_HOME!\fixtures\intake\ok\source.txt"
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:paper
"%PY%" "!ORPATH_HOME!\scripts\orpath_paper.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:t2
"%PY%" "!ORPATH_HOME!\orpath\run_t2.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:knowledge_sync
echo [OR-Path] knowledge-sync = allowlist export --clear-exports + ingest --clear
"%PY%" "!ORPATH_HOME!\scripts\export_agent_knowledge_corpus.py" --clear-exports
if errorlevel 1 (
    set "EC=!ERRORLEVEL!"
    if "!PUSHD_OK!"=="1" popd
    exit /b !EC!
)
"%PY%" -m knowledge_svc.ingest --clear !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:knowledge_rebuild
echo [OR-Path] knowledge-rebuild = export + ingest --clear
"%PY%" "!ORPATH_HOME!\scripts\export_agent_knowledge_corpus.py"
if errorlevel 1 (
    set "EC=!ERRORLEVEL!"
    if "!PUSHD_OK!"=="1" popd
    exit /b !EC!
)
"%PY%" -m knowledge_svc.ingest --clear !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:knowledge_export
"%PY%" "!ORPATH_HOME!\scripts\export_agent_knowledge_corpus.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:knowledge_ingest
"%PY%" -m knowledge_svc.ingest !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:knowledge_retrieve
"%PY%" -m knowledge_svc.retrieve !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:knowledge_smoke
"%PY%" "!ORPATH_HOME!\scripts\knowledge_smoke.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:knowledge_eval
"%PY%" "!ORPATH_HOME!\scripts\knowledge_eval.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:promote_run
"%PY%" "!ORPATH_HOME!\scripts\promote_run_to_skill.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:memory_search
"%PY%" -m orpath.process_memory search !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:memory_record
"%PY%" -m orpath.process_memory record !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:memory_list
"%PY%" -m orpath.process_memory list !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:tools_list
"%PY%" -m orpath.tool_catalog !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:mcp
echo [OR-Path] MCP stdio server — connect host to: "%PY%" -m orpath.mcp_server
"%PY%" -m orpath.mcp_server
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:mcp_ortools
echo [OR-Path] OR-Tools MCP (vendored Jacck/mcp-ortools)
"%PY%" -m mcp_ortools.server
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:pack_release
"%PY%" "!ORPATH_HOME!\scripts\pack_release.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:workbench_gate
"%PY%" "!ORPATH_HOME!\scripts\problem_workbench_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:v0_watch_gate
"%PY%" "!ORPATH_HOME!\scripts\v0_watch_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:dialogue_gate
set "ORPATH_APPLY_STEER=1"
"%PY%" "!ORPATH_HOME!\scripts\dialogue_steer_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:t1_gate
"%PY%" "!ORPATH_HOME!\scripts\t1_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:t2_gate
"%PY%" "!ORPATH_HOME!\scripts\t2_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:m0_gate
"%PY%" "!ORPATH_HOME!\scripts\m0_demo_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:m1_gate
"%PY%" "!ORPATH_HOME!\scripts\m1_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:m2_gate
"%PY%" "!ORPATH_HOME!\scripts\m2_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:p3_gate
"%PY%" "!ORPATH_HOME!\scripts\p3_watch_run_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:p5_gate
"%PY%" "!ORPATH_HOME!\scripts\p5_polish_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:tube_geometry_gate
"%PY%" "!ORPATH_HOME!\scripts\tube_geometry_stability_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:tube_collab_gate
"%PY%" "!ORPATH_HOME!\scripts\tube_collaboration_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:tube_redteam_gate
"%PY%" "!ORPATH_HOME!\scripts\tube_redteam_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:tube_live_gate
"%PY%" "!ORPATH_HOME!\scripts\tube_live_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:tube_benchmark
"%PY%" "!ORPATH_HOME!\eval_or_bench\run_tube_synthetic_benchmark.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:bench
echo [OR-Path] Running TSPLIB Benchmark Suite...
"%PY%" "!ORPATH_HOME!\eval_or_bench\contract_probe.py"
if errorlevel 1 (
    set "EC=!ERRORLEVEL!"
    if "!PUSHD_OK!"=="1" popd
    exit /b !EC!
)
"%PY%" "!ORPATH_HOME!\eval_or_bench\test_converter_stress.py"
if errorlevel 1 (
    set "EC=!ERRORLEVEL!"
    if "!PUSHD_OK!"=="1" popd
    exit /b !EC!
)
"%PY%" "!ORPATH_HOME!\eval_or_bench\run_full_benchmark.py"
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:vrp_baseline
"%PY%" "!ORPATH_HOME!\eval_or_bench\run_cvrp_baseline.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:l2_gate
"%PY%" "!ORPATH_HOME!\scripts\l2_release_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!

:promote_run_gate
"%PY%" "!ORPATH_HOME!\scripts\promote_run_gate.py" !SUB_ARGS!
set "EC=!ERRORLEVEL!"
if "!PUSHD_OK!"=="1" popd
exit /b !EC!
