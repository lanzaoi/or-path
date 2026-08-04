#!/usr/bin/env bash
# OR-Path product launcher (relocatable) — git-bash / macOS / Linux
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
export PYTHONNOUSERSITE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

run_py() {
  exec "$PY" "$@"
}

CMD="${1:-help}"
shift || true

case "$CMD" in
  help|-h|--help)
    cat <<EOF
OR-Path launcher (relocatable)
  ORPATH_HOME    = $ORPATH_HOME
  ORPATH_WORKDIR = $ORPATH_WORKDIR

  orpath.sh setup | doctor | demo-seed | menu | pack-release | l2-gate
  orpath.sh isolation | gate | t2 | pi | env
  orpath.sh memory-search | memory-record | memory-list | tools-list | mcp
  orpath.sh knowledge-export | knowledge-ingest | knowledge-retrieve | knowledge-smoke
  orpath.sh knowledge-rebuild | knowledge-sync | knowledge-eval
  orpath.sh knowledge-mineru | knowledge-preprocess | phase1-mineru-gate | phase1-mineru-cloud-gate
    orpath.sh phase2-embed-gate | phase3-scale-gate | thick-hybrid-gate | phase5-thick-gate
        orpath.sh phase3-hybrid-gate | phase4-knowledge-gate | phase5-knowledge-gate

EOF
    ;;
  env)
    echo "ORPATH_HOME=$ORPATH_HOME"
    echo "ORPATH_WORKDIR=$ORPATH_WORKDIR"
    echo "PY=$PY"
    ;;
  setup|bootstrap)
    run_py scripts/bootstrap_orpath.py "$@"
    ;;
  demo-seed|seed)
    run_py scripts/install_demo_seed.py "$@"
    ;;
  pack-release)
    run_py scripts/pack_release.py "$@"
    ;;
  l2-gate)
    run_py scripts/l2_release_gate.py "$@"
    ;;
  doctor)
    run_py scripts/orpath_doctor.py
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
  knowledge-rebuild|knowledge-sync)
    echo "[OR-Path] $CMD = allowlist export --clear-exports + ingest --clear"
    "$PY" scripts/export_agent_knowledge_corpus.py --clear-exports
    run_py -m knowledge_svc.ingest --clear
    ;;
  promote-run)
    run_py scripts/promote_run_to_skill.py "$@"
    ;;
  promote-run-gate)
    run_py scripts/promote_run_gate.py "$@"
    ;;
  knowledge-eval)
    run_py scripts/knowledge_eval.py "$@"
    ;;
  knowledge-lit-materialize)
    run_py scripts/materialize_or_literature_corpus.py --top 45 --normalize-existing "$@"
    ;;
  knowledge-mineru)
    run_py -m knowledge_svc.mineru_client "$@"
    ;;
  knowledge-preprocess)
    echo "[OR-Path] knowledge-preprocess = inbox PDF -> corpus/papers/_from_mineru + manifest"
    run_py -m knowledge_svc.mineru_client --preprocess --offline-fixture "$@"
    ;;
  phase1-mineru-gate|knowledge-phase1-mineru-gate)
    run_py scripts/phase1_mineru_gate.py "$@"
    ;;
  phase1-mineru-cloud-gate|knowledge-phase1-mineru-cloud-gate)
    run_py scripts/phase1_mineru_cloud_gate.py "$@"
    ;;
  phase2-embed-gate|knowledge-phase2-gate)
    run_py scripts/phase2_embed_gate.py "$@"
    ;;
  phase2-real-corpus-gate|knowledge-phase2-real-corpus-gate)
    run_py scripts/phase2_real_corpus_gate.py "$@"
    ;;
  phase3-live-default-gate|knowledge-phase3-live-default-gate)
    run_py scripts/phase3_live_default_gate.py "$@"
    ;;
  phase3-scale-gate|knowledge-phase3-scale-gate)
    run_py scripts/phase3_scale_gate.py "$@"
    ;;
  thick-hybrid-gate|phase4-thick-gate|knowledge-phase4-thick-gate)
    run_py scripts/phase4_thick_hybrid_gate.py "$@"
    ;;
  product-research-gate|phase4-product-research-gate|knowledge-phase4-product-research-gate)
    run_py scripts/phase4_product_research_gate.py "$@"
    ;;
  phase5-v3-gate|knowledge-phase5-v3-gate)
    run_py scripts/phase5_v3_knowledge_gate.py "$@"
    ;;
  phase5-thick-gate|knowledge-phase5-thick-gate)
    run_py scripts/phase5_thick_knowledge_gate.py "$@"
    ;;
  phase3-hybrid-gate|knowledge-phase3-gate)
    run_py scripts/phase3_hybrid_pi_gate.py "$@"
    ;;
  phase4-knowledge-gate|knowledge-phase4-gate)
    run_py scripts/phase4_knowledge_sync_gate.py "$@"
    ;;
  phase5-knowledge-gate|knowledge-phase5-gate)
    run_py scripts/phase5_knowledge_rag_gate.py "$@"
    ;;
  tools-list)
    run_py -m orpath.tool_catalog "$@"
    ;;
  mcp)
    echo "[OR-Path] MCP stdio: $PY -m orpath.mcp_server"
    run_py -m orpath.mcp_server
    ;;
  mcp-highs)
    HM="third_party/highs-mcp/node_modules/highs-mcp/dist/index.js"
    if [[ ! -f "$HM" ]]; then
      echo "[ERROR] highs-mcp missing. (cd third_party/highs-mcp && npm install highs-mcp@0.3.2)" >&2
      exit 1
    fi
    echo "[OR-Path] HiGHS MCP (npm highs-mcp)"
    exec node "$HM"
    ;;
  mcp-ortools)
    echo "[OR-Path] OR-Tools MCP (vendored Jacck/mcp-ortools)"
    run_py -m mcp_ortools.server
    ;;
  isolation)
    run_py scripts/t2_multiagent_isolation.py
    ;;
  gate)
    run_py scripts/t2_gate.py
    ;;
  t2)
    run_py orpath/run_t2.py "$@"
    ;;
  pi)
    exec "$ORPATH_HOME/pi.sh" -a "$@" 2>/dev/null || exec cmd.exe //c "pi.bat -a $*"
    ;;
  openpi)
    echo "[REMOVED] OpenPi deleted. Use: orpath.sh menu | pi | run via orpath.bat" >&2
    exit 2
    ;;
  menu)
    run_py scripts/orpath_menu.py
    ;;
  *)
    echo "unknown command: $CMD" >&2
    exit 2
    ;;
esac
