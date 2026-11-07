#!/usr/bin/env bash
# OR-Path Unified CLI & Web Studio Launcher (Linux / macOS / WSL)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ORPATH_HOME="${ORPATH_HOME:-$SCRIPT_DIR}"
export ORPATH_WORKDIR="${ORPATH_WORKDIR:-$ORPATH_HOME}"
cd "$ORPATH_HOME"

if [[ -x "$ORPATH_HOME/.venv-314/Scripts/python.exe" ]]; then
  PY="$ORPATH_HOME/.venv-314/Scripts/python.exe"
elif [[ -x "$ORPATH_HOME/.venv-314/bin/python" ]]; then
  PY="$ORPATH_HOME/.venv-314/bin/python"
elif [[ -x "$ORPATH_HOME/.venv/bin/python" ]]; then
  PY="$ORPATH_HOME/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi
export PYTHONPATH=""
export PYTHONHOME=""
export PYTHONNOUSERSITE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTHONUNBUFFERED=1
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

run_py() {
  exec "$PY" "$@"
}

CMD="${1:-help}"
shift || true

case "$CMD" in
  help|-h|--help)
    cat <<EOF
======================================================================
  OR-Path 运筹优化与智能工作台 · 命令行主控入口
  ORPATH_HOME    = $ORPATH_HOME
  ORPATH_WORKDIR = $ORPATH_WORKDIR
======================================================================
  [1. Web Studio 与实时看板]
    ./START.sh                         一键启动 Web Studio & Live Watch (:8765)
    ./orpath.sh studio                 启动 Web Studio 智能工作台 (:8765)
    ./orpath.sh watch                  启动 Live Watch 服务 (--slug live-btube)
    ./orpath.sh menu                   启动交互式控制台菜单

  [2. 四大核心运筹求解器]
    ./orpath.sh tube-solve             空间异形圆管 3D 展开与四模式共切 DP 求解器
    ./orpath.sh polyomino-solve        多联骨牌 CP-SAT 二维精确覆盖求解器
    ./orpath.sh polyomino-q3           芯片/板材多目标排样与共边最大化求解器
    ./orpath.sh microgrid-solve        园区光储充微电网多时段 LP 与日内滚动 MPC 求解器
    ./orpath.sh routing-solve          最短路 / TSP / CVRP / VRPTW 车辆路径规划求解器
    ./orpath.sh demo-m0                运行 M0 最短路端到端基准演示

  [3. 独立验证器与系统诊断]
    ./orpath.sh validate               独立物理与数学重算验证器 (Numbers Truth)
    ./orpath.sh doctor                 运行 Python 环境、求解器与工作台健康检查
    ./orpath.sh setup                  初始化虚拟环境、释放演示种子并运行 doctor
    ./orpath.sh knowledge-sync         同步本地混合知识库 (BM25 + ONNX bge-m3)

  [4. 核心验证门禁]
    ./orpath.sh workbench-gate         Web Studio 智能做题工作舱契约门禁
    ./orpath.sh v0-watch-gate          Live Watch 实时过程看板门禁
    ./orpath.sh t1-gate | t2-gate      求解器与验证器核心门禁
    ./orpath.sh m1-gate | m2-gate      工作区隔离与骨牌领域端到端门禁
======================================================================
EOF
    ;;
  env)
    echo "ORPATH_HOME=$ORPATH_HOME"
    echo "ORPATH_WORKDIR=$ORPATH_WORKDIR"
    echo "PY=$PY"
    ;;
  studio|web)
    exec "$ORPATH_HOME/START.sh" "$@"
    ;;
  face)
    if [[ $# -eq 0 ]]; then
      run_py scripts/orpath_watch.py --slug live-btube --thread-id live-btube --host 0.0.0.0 --port 8765
    else
      run_py scripts/orpath_watch.py "$@"
    fi
    ;;
  watch)
    if [[ $# -eq 0 ]]; then
      run_py scripts/orpath_watch.py --slug live-btube --thread-id live-btube --host 0.0.0.0 --port 8765
    else
      run_py scripts/orpath_watch.py "$@"
    fi
    ;;
  watch-run)
    run_py scripts/orpath_watch_run.py "$@"
    ;;
  menu)
    run_py scripts/orpath_menu.py "$@"
    ;;
  setup|bootstrap)
    run_py scripts/bootstrap_orpath.py "$@"
    ;;
  doctor)
    run_py scripts/orpath_doctor.py "$@"
    ;;
  demo-seed|seed)
    run_py scripts/install_demo_seed.py "$@"
    ;;
  tube-solve|tube)
    run_py scripts/b_tube_solve.py "$@"
    ;;
  polyomino-solve|polyomino)
    run_py tools/solve_polyomino.py "$@"
    ;;
  polyomino-q3)
    run_py tools/solve_polyomino_q3.py "$@"
    ;;
  microgrid-solve|microgrid)
    run_py tools/solve_microgrid.py "$@"
    ;;
  routing-solve|routing)
    run_py tools/solve_ortools.py "$@"
    ;;
  demo-m0|m0-demo|m0)
    run_py scripts/orpath_demo_m0.py "$@"
    ;;
  validate)
    run_py tools/validate_solution.py "$@"
    ;;
  run)
    run_py orpath/run_orpath.py run "$@"
    ;;
  run-full)
    run_py orpath/run_orpath.py run --auto-intake --fresh "$@"
    ;;
  resume)
    run_py orpath/run_orpath.py run --resume "$@"
    ;;
  intake)
    run_py orpath/run_orpath.py intake "$@"
    ;;
  intake-auto)
    run_py scripts/orpath_intake_auto.py "$@"
    ;;
  status)
    run_py orpath/run_orpath.py status "$@"
    ;;
  list)
    run_py orpath/run_orpath.py list "$@"
    ;;
  gui-demo)
    run_py orpath/run_orpath.py run --fresh --auto-intake --slug gui-demo --thread-id gui-demo --problem-id shortest_path --solve-mode mock --intake-in "$ORPATH_HOME/fixtures/intake/ok/source.txt"
    ;;
  paper)
    run_py scripts/orpath_paper.py "$@"
    ;;
  t2)
    run_py orpath/run_t2.py "$@"
    ;;
  knowledge-sync|knowledge-rebuild)
    echo "[OR-Path] $CMD = allowlist export --clear-exports + ingest --clear"
    "$PY" scripts/export_agent_knowledge_corpus.py --clear-exports
    run_py -m knowledge_svc.ingest --clear "$@"
    ;;
  knowledge-export)
    run_py scripts/export_agent_knowledge_corpus.py "$@"
    ;;
  knowledge-ingest)
    if [[ $# -eq 0 ]]; then
      run_py -m knowledge_svc.ingest --clear
    else
      run_py -m knowledge_svc.ingest "$@"
    fi
    ;;
  knowledge-retrieve)
    run_py -m knowledge_svc.retrieve "$@"
    ;;
  knowledge-smoke)
    run_py scripts/knowledge_smoke.py "$@"
    ;;
  knowledge-eval)
    run_py scripts/knowledge_eval.py "$@"
    ;;
  promote-run)
    run_py scripts/promote_run_to_skill.py "$@"
    ;;
  memory-search)
    run_py -m orpath.process_memory search "$@"
    ;;
  memory-record)
    run_py -m orpath.process_memory record "$@"
    ;;
  memory-list)
    run_py -m orpath.process_memory list "$@"
    ;;
  tools-list)
    run_py -m orpath.tool_catalog "$@"
    ;;
  mcp)
    echo "[OR-Path] MCP stdio: $PY -m orpath.mcp_server"
    run_py -m orpath.mcp_server
    ;;
  mcp-ortools)
    echo "[OR-Path] OR-Tools MCP (vendored Jacck/mcp-ortools)"
    run_py -m mcp_ortools.server
    ;;
  pack-release)
    run_py scripts/pack_release.py "$@"
    ;;
  workbench-gate|problem-workbench-gate)
    run_py scripts/problem_workbench_gate.py "$@"
    ;;
  v0-watch-gate|watch-gate)
    run_py scripts/v0_watch_gate.py "$@"
    ;;
  dialogue-gate|steer-gate)
    export ORPATH_APPLY_STEER=1
    run_py scripts/dialogue_steer_gate.py "$@"
    ;;
  t1-gate)
    run_py scripts/t1_gate.py "$@"
    ;;
  t2-gate|gate)
    run_py scripts/t2_gate.py "$@"
    ;;
  m0-gate)
    run_py scripts/m0_demo_gate.py "$@"
    ;;
  m1-gate)
    run_py scripts/m1_gate.py "$@"
    ;;
  m2-gate)
    run_py scripts/m2_gate.py "$@"
    ;;
  p3-gate)
    run_py scripts/p3_watch_run_gate.py "$@"
    ;;
  p5-gate)
    run_py scripts/p5_polish_gate.py "$@"
    ;;
  tube-geometry-gate)
    run_py scripts/tube_geometry_stability_gate.py "$@"
    ;;
  tube-collab-gate)
    run_py scripts/tube_collaboration_gate.py "$@"
    ;;
  tube-redteam-gate)
    run_py scripts/tube_redteam_gate.py "$@"
    ;;
  tube-live-gate)
    run_py scripts/tube_live_gate.py "$@"
    ;;
  tube-benchmark)
    run_py eval_or_bench/run_tube_synthetic_benchmark.py "$@"
    ;;
  bench)
    "$PY" eval_or_bench/contract_probe.py
    "$PY" eval_or_bench/test_converter_stress.py
    run_py eval_or_bench/run_full_benchmark.py
    ;;
  vrp-baseline)
    run_py eval_or_bench/run_cvrp_baseline.py "$@"
    ;;
  l2-gate)
    run_py scripts/l2_release_gate.py "$@"
    ;;
  promote-run-gate)
    run_py scripts/promote_run_gate.py "$@"
    ;;
  *)
    echo "unknown command: $CMD" >&2
    exit 2
    ;;
esac
