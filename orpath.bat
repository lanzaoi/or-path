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















if /i "%CMD%"=="dialogue-gate" (
  set "ORPATH_LIVE_SUBAGENT=0"
  set "ORPATH_PI_SESSION=0"
  set "ORPATH_APPLY_STEER=1"
  "%PY%" "%~dp0scripts\dialogue_steer_gate.py"
  exit /b %ERRORLEVEL%
)
if /i "%CMD%"=="steer-gate" (
  set "ORPATH_LIVE_SUBAGENT=0"
  set "ORPATH_PI_SESSION=0"
  set "ORPATH_APPLY_STEER=1"
  "%PY%" "%~dp0scripts\dialogue_steer_gate.py"
  exit /b %ERRORLEVEL%
)
if /i "%CMD%"=="p4-gate" goto :p4_gate
if /i "%CMD%"=="bench" goto :bench
if /i "%CMD%"=="vrp-baseline" goto :vrp_baseline
if /i "%CMD%"=="doctor" goto :doctor
if /i "%CMD%"=="t1-gate" goto :t1_gate
if /i "%CMD%"=="t2-gate" goto :t2_gate
if /i "%CMD%"=="m0-gate" goto :m0_gate
if /i "%CMD%"=="m1-gate" goto :m1_gate
if /i "%CMD%"=="m2-gate" goto :m2_gate
if /i "%CMD%"=="subagent-gate" goto :subagent_gate
if /i "%CMD%"=="tube-solve" goto :tube_solve
if /i "%CMD%"=="tube-benchmark" goto :tube_benchmark
if /i "%CMD%"=="tube-live-gate" goto :tube_live_gate
if /i "%CMD%"=="tube-collab-gate" goto :tube_collab_gate
if /i "%CMD%"=="tube-redteam-gate" goto :tube_redteam_gate
if /i "%CMD%"=="tube-geometry-gate" goto :tube_geometry_gate
if /i "%CMD%"=="v0-watch-gate" goto :v0_watch_gate
if /i "%CMD%"=="p3-gate" goto :p3_gate
if /i "%CMD%"=="p5-gate" goto :p5_gate
if /i "%CMD%"=="paper-gate" goto :paper_gate
if /i "%CMD%"=="paper-1.0-gate" goto :paper_10_gate
if /i "%CMD%"=="run" goto :run
if /i "%CMD%"=="run-full" goto :run_full
if /i "%CMD%"=="resume" goto :resume
if /i "%CMD%"=="status" goto :status
if /i "%CMD%"=="list" goto :list
if /i "%CMD%"=="t2" goto :t2
if /i "%CMD%"=="watch" goto :watch
if /i "%CMD%"=="watch-run" goto :watch_run
if /i "%CMD%"=="isolation" goto :isolation































if /i "%CMD%"=="memory-search" goto :memory_search































if /i "%CMD%"=="memory-record" goto :memory_record































if /i "%CMD%"=="memory-list" goto :memory_list





if /i "%CMD%"=="knowledge-export" goto :knowledge_export

if /i "%CMD%"=="knowledge-ingest" goto :knowledge_ingest

if /i "%CMD%"=="knowledge-retrieve" goto :knowledge_retrieve

if /i "%CMD%"=="knowledge-smoke" goto :knowledge_smoke

if /i "%CMD%"=="knowledge-rebuild" goto :knowledge_rebuild

if /i "%CMD%"=="knowledge-sync" goto :knowledge_sync
if /i "%CMD%"=="promote-run" goto :promote_run
if /i "%CMD%"=="promote-run-gate" goto :promote_run_gate

if /i "%CMD%"=="knowledge-eval" goto :knowledge_eval

if /i "%CMD%"=="knowledge-lit-materialize" goto :knowledge_lit_materialize

if /i "%CMD%"=="knowledge-mineru" goto :knowledge_mineru

if /i "%CMD%"=="knowledge-preprocess" goto :knowledge_preprocess



if /i "%CMD%"=="phase1-mineru-gate" goto :phase1_mineru_gate

if /i "%CMD%"=="knowledge-phase1-mineru-gate" goto :phase1_mineru_gate

if /i "%CMD%"=="phase1-mineru-cloud-gate" goto :phase1_mineru_cloud_gate

if /i "%CMD%"=="knowledge-phase1-mineru-cloud-gate" goto :phase1_mineru_cloud_gate

if /i "%CMD%"=="phase2-embed-gate" goto :phase2_embed_gate

if /i "%CMD%"=="knowledge-phase2-gate" goto :phase2_embed_gate

if /i "%CMD%"=="phase2-real-corpus-gate" goto :phase2_real_corpus_gate

if /i "%CMD%"=="knowledge-phase2-real-corpus-gate" goto :phase2_real_corpus_gate

if /i "%CMD%"=="phase3-live-default-gate" goto :phase3_live_default_gate

if /i "%CMD%"=="knowledge-phase3-live-default-gate" goto :phase3_live_default_gate

if /i "%CMD%"=="phase3-scale-gate" goto :phase3_scale_gate

if /i "%CMD%"=="knowledge-phase3-scale-gate" goto :phase3_scale_gate

if /i "%CMD%"=="thick-hybrid-gate" goto :thick_hybrid_gate

if /i "%CMD%"=="phase4-thick-gate" goto :thick_hybrid_gate

if /i "%CMD%"=="knowledge-phase4-thick-gate" goto :thick_hybrid_gate

if /i "%CMD%"=="product-research-gate" goto :product_research_gate
if /i "%CMD%"=="phase5-v3-gate" goto :phase5_v3_gate
if /i "%CMD%"=="knowledge-phase5-v3-gate" goto :phase5_v3_gate

if /i "%CMD%"=="phase4-product-research-gate" goto :product_research_gate

if /i "%CMD%"=="knowledge-phase4-product-research-gate" goto :product_research_gate

if /i "%CMD%"=="phase5-thick-gate" goto :phase5_thick_gate

if /i "%CMD%"=="knowledge-phase5-thick-gate" goto :phase5_thick_gate

if /i "%CMD%"=="phase3-hybrid-gate" goto :phase3_hybrid_gate

if /i "%CMD%"=="knowledge-phase3-gate" goto :phase3_hybrid_gate

if /i "%CMD%"=="phase4-knowledge-gate" goto :phase4_knowledge_gate

if /i "%CMD%"=="knowledge-phase4-gate" goto :phase4_knowledge_gate

goto :tools_list
:promote_run



"%PY%" "%~dp0scripts\promote_run_to_skill.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:promote_run_gate



"%PY%" "%~dp0scripts\promote_run_gate.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:tools_list

:phase5_v3_gate







"%PY%" "%~dp0scripts\phase5_v3_knowledge_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:phase5_knowledge_gate

if /i "%CMD%"=="knowledge-phase5-gate" goto :phase5_knowledge_gate



if /i "%CMD%"=="tools-list" goto :tools_list

if /i "%CMD%"=="mcp" goto :mcp

if /i "%CMD%"=="mcp-highs" goto :mcp_highs

if /i "%CMD%"=="mcp-ortools" goto :mcp_ortools

if /i "%CMD%"=="gate" goto :gate

if /i "%CMD%"=="gate-t3" goto :gate_t3

if /i "%CMD%"=="isolation" goto :isolation

if /i "%CMD%"=="pi" goto :pi

if /i "%CMD%"=="doctor" goto :doctor





:memory_search































"%PY%" -m orpath.process_memory search %2 %3 %4 %5 %6 %7 %8 %9































exit /b %ERRORLEVEL%



:memory_record































"%PY%" -m orpath.process_memory record %2 %3 %4 %5 %6 %7 %8 %9































exit /b %ERRORLEVEL%



:memory_list































"%PY%" -m orpath.process_memory list %2 %3 %4 %5 %6 %7 %8 %9































exit /b %ERRORLEVEL%



:knowledge_export







"%PY%" "%~dp0scripts\export_agent_knowledge_corpus.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:knowledge_ingest







"%PY%" -m knowledge_svc.ingest %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:knowledge_retrieve







"%PY%" -m knowledge_svc.retrieve %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:knowledge_smoke







"%PY%" "%~dp0scripts\knowledge_smoke.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:knowledge_rebuild







echo [OR-Path] knowledge-rebuild = export + ingest --clear

"%PY%" "%~dp0scripts\export_agent_knowledge_corpus.py"

if errorlevel 1 exit /b %ERRORLEVEL%

"%PY%" -m knowledge_svc.ingest --clear %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:knowledge_sync







echo [OR-Path] knowledge-sync = allowlist export --clear-exports + ingest --clear

"%PY%" "%~dp0scripts\export_agent_knowledge_corpus.py" --clear-exports

if errorlevel 1 exit /b %ERRORLEVEL%

"%PY%" -m knowledge_svc.ingest --clear %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:knowledge_eval







"%PY%" "%~dp0scripts\knowledge_eval.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:knowledge_lit_materialize







"%PY%" "%~dp0scripts\materialize_or_literature_corpus.py" --top 45 --normalize-existing %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:knowledge_mineru







"%PY%" -m knowledge_svc.mineru_client %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:knowledge_preprocess







echo [OR-Path] knowledge-preprocess = inbox PDF -^> corpus/papers/_from_mineru + manifest

"%PY%" -m knowledge_svc.mineru_client --preprocess --offline-fixture %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:phase1_mineru_gate







"%PY%" "%~dp0scripts\phase1_mineru_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:phase1_mineru_cloud_gate







"%PY%" "%~dp0scripts\phase1_mineru_cloud_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:phase2_embed_gate







"%PY%" "%~dp0scripts\phase2_embed_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:phase2_real_corpus_gate







"%PY%" "%~dp0scripts\phase2_real_corpus_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:phase3_live_default_gate







"%PY%" "%~dp0scripts\phase3_live_default_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:phase3_scale_gate







"%PY%" "%~dp0scripts\phase3_scale_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:thick_hybrid_gate







"%PY%" "%~dp0scripts\phase4_thick_hybrid_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:product_research_gate







"%PY%" "%~dp0scripts\phase4_product_research_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:phase5_thick_gate







"%PY%" "%~dp0scripts\phase5_thick_knowledge_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:phase3_hybrid_gate







"%PY%" "%~dp0scripts\phase3_hybrid_pi_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:phase4_knowledge_gate







"%PY%" "%~dp0scripts\phase4_knowledge_sync_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:phase5_knowledge_gate







"%PY%" "%~dp0scripts\phase5_knowledge_rag_gate.py" %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:tools_list







"%PY%" -m orpath.tool_catalog %2 %3 %4 %5 %6 %7 %8 %9

exit /b %ERRORLEVEL%



:mcp































echo [OR-Path] MCP stdio server — connect host to: "%PY%" -m orpath.mcp_server































"%PY%" -m orpath.mcp_server































exit /b %ERRORLEVEL%



:mcp_ortools































echo [OR-Path] OR-Tools MCP (vendored Jacck/mcp-ortools)































"%PY%" -m mcp_ortools.server































exit /b %ERRORLEVEL%



:bench
echo [OR-Path] Running TSPLIB Benchmark Suite...
echo.
echo ==============================================
echo 1. Running Contract Probe (burma14)
echo ==============================================
"%PY%" "!ORPATH_HOME!\eval_or_bench\contract_probe.py"
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo ==============================================
echo 2. Running Converter Stress Test
echo ==============================================
"%PY%" "!ORPATH_HOME!\eval_or_bench\test_converter_stress.py"
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo ==============================================
echo 3. Running Full TSPLIB Benchmark
echo ==============================================
"%PY%" "!ORPATH_HOME!\eval_or_bench\run_full_benchmark.py"
exit /b %ERRORLEVEL%

:vrp_baseline
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\eval_or_bench\run_cvrp_baseline.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:doctor















"%PY%" "!ORPATH_HOME!\scripts\orpath_doctor.py"















exit /b %ERRORLEVEL%



:gate















set "ORPATH_LIVE_SUBAGENT=0"















"%PY%" "!ORPATH_HOME!\scripts\t2_gate.py"















exit /b %ERRORLEVEL%

:t1_gate

set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\t1_gate.py"
exit /b %ERRORLEVEL%

:t2_gate

set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\t2_gate.py"
exit /b %ERRORLEVEL%



:gate_t3















set "ORPATH_LIVE_SUBAGENT=0"















"%PY%" "!ORPATH_HOME!\scripts\t3_lg_gate.py"















if errorlevel 1 exit /b %ERRORLEVEL%















"%PY%" "!ORPATH_HOME!\scripts\t3_gate.py"















exit /b %ERRORLEVEL%



:isolation















set "ORPATH_LIVE_SUBAGENT=0"















"%PY%" "!ORPATH_HOME!\scripts\t2_multiagent_isolation.py"















exit /b %ERRORLEVEL%



:demo_m0















"%PY%" "!ORPATH_HOME!\scripts\orpath_demo_m0.py" %2 %3 %4 %5 %6 %7 %8 %9















exit /b %ERRORLEVEL%



:demo_seed















"%PY%" "!ORPATH_HOME!\scripts\install_demo_seed.py" %2 %3 %4 %5 %6 %7 %8 %9







exit /b %ERRORLEVEL%



:face







REM One-click product face. Default slug=live-btube when no args.







if "%~2"=="" (







  "%PY%" "!ORPATH_HOME!\scripts\orpath_watch.py" --slug live-btube --thread-id live-btube --host 127.0.0.1 --port 8765







) else (







  "%PY%" "!ORPATH_HOME!\scripts\orpath_watch.py" %2 %3 %4 %5 %6 %7 %8 %9







)







exit /b %ERRORLEVEL%



:gate_intake















set "ORPATH_LIVE_SUBAGENT=0"















"%PY%" "!ORPATH_HOME!\scripts\intake_gate.py"















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



:intake















"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" intake %2 %3 %4 %5 %6 %7 %8 %9















exit /b %ERRORLEVEL%



:intake_auto















"%PY%" "!ORPATH_HOME!\scripts\orpath_intake_auto.py" %2 %3 %4 %5 %6 %7 %8 %9















exit /b %ERRORLEVEL%



:l2_gate















"%PY%" "!ORPATH_HOME!\scripts\l2_release_gate.py" %2 %3 %4 %5 %6 %7 %8 %9







exit /b %ERRORLEVEL%



:list















"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" list %2 %3 %4 %5 %6 %7 %8 %9















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



:pack_release















"%PY%" "!ORPATH_HOME!\scripts\pack_release.py" %2 %3 %4 %5 %6 %7 %8 %9







exit /b %ERRORLEVEL%



:paper















"%PY%" "!ORPATH_HOME!\scripts\orpath_paper.py" %2 %3 %4 %5 %6 %7 %8 %9















exit /b %ERRORLEVEL%



:paper_10_gate















set "ORPATH_LIVE_SUBAGENT=0"















"%PY%" "!ORPATH_HOME!\scripts\paper_1_0_gate.py"















exit /b %ERRORLEVEL%



:paper_gate















set "ORPATH_LIVE_SUBAGENT=0"















"%PY%" "!ORPATH_HOME!\scripts\paper_gate.py"















exit /b %ERRORLEVEL%



:paper_protocol















"%PY%" "!ORPATH_HOME!\scripts\orpath_paper.py" protocol %2 %3 %4 %5 %6 %7 %8 %9















exit /b %ERRORLEVEL%



:paper_tube















"%PY%" "!ORPATH_HOME!\scripts\run_tube_cut_paper.py"















exit /b %ERRORLEVEL%



:resume















"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run --resume %2 %3 %4 %5 %6 %7 %8 %9















exit /b %ERRORLEVEL%



:run















"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run %2 %3 %4 %5 %6 %7 %8 %9















exit /b %ERRORLEVEL%



:run_full















"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" run --auto-intake --fresh %2 %3 %4 %5 %6 %7 %8 %9















exit /b %ERRORLEVEL%



:setup















REM Prefer system Python to create venv when venv missing; bootstrap re-resolves.







where python >nul 2>&1 && set "BOOT_PY=python"







if exist "!ORPATH_HOME!\.venv-314\Scripts\python.exe" set "BOOT_PY=!ORPATH_HOME!\.venv-314\Scripts\python.exe"







if not defined BOOT_PY set "BOOT_PY=%PY%"







"%BOOT_PY%" "!ORPATH_HOME!\scripts\bootstrap_orpath.py" %2 %3 %4 %5 %6 %7 %8 %9







exit /b %ERRORLEVEL%



:status















"%PY%" "!ORPATH_HOME!\orpath\run_orpath.py" status %2 %3 %4 %5 %6 %7 %8 %9















exit /b %ERRORLEVEL%



:subagent_gate















set "ORPATH_LIVE_SUBAGENT=0"















"%PY%" "!ORPATH_HOME!\scripts\subagent_gate.py"















exit /b %ERRORLEVEL%



:t2















"%PY%" "!ORPATH_HOME!\orpath\run_t2.py" %2 %3 %4 %5 %6 %7 %8 %9















exit /b %ERRORLEVEL%



:tube_solve

set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\b_tube_solve.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:tube_benchmark

set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\eval_or_bench\run_tube_synthetic_benchmark.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:tube_live_gate







set "ORPATH_LIVE_SUBAGENT=0"







"%PY%" "!ORPATH_HOME!\scripts\tube_live_gate.py" %2 %3 %4 %5







exit /b %ERRORLEVEL%

:tube_collab_gate
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\tube_collaboration_gate.py"
exit /b %ERRORLEVEL%

:tube_redteam_gate
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\tube_redteam_gate.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

:tube_geometry_gate
set "ORPATH_LIVE_SUBAGENT=0"
"%PY%" "!ORPATH_HOME!\scripts\tube_geometry_stability_gate.py" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%



:v0_watch_gate















set "ORPATH_LIVE_SUBAGENT=0"















"%PY%" "!ORPATH_HOME!\scripts\v0_watch_gate.py"















exit /b %ERRORLEVEL%



:watch















"%PY%" "!ORPATH_HOME!\scripts\orpath_watch.py" %2 %3 %4 %5 %6 %7 %8 %9















exit /b %ERRORLEVEL%



:watch_run















"%PY%" "!ORPATH_HOME!\scripts\orpath_watch_run.py" %2 %3 %4 %5 %6 %7 %8 %9















exit /b %ERRORLEVEL%

