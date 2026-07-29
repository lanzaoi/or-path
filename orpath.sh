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

CMD="${1:-help}"
shift || true

case "$CMD" in
  help|-h|--help)
    cat <<EOF
OR-Path launcher (relocatable)
  ORPATH_HOME    = $ORPATH_HOME
  ORPATH_WORKDIR = $ORPATH_WORKDIR

  orpath.sh doctor | isolation | gate | t2 | pi | openpi | env
EOF
    ;;
  env)
    echo "ORPATH_HOME=$ORPATH_HOME"
    echo "ORPATH_WORKDIR=$ORPATH_WORKDIR"
    echo "PY=$PY"
    ;;
  doctor)
    exec "$PY" "$ORPATH_HOME/scripts/orpath_doctor.py"
    ;;
  isolation)
    exec "$PY" "$ORPATH_HOME/scripts/t2_multiagent_isolation.py"
    ;;
  gate)
    exec "$PY" "$ORPATH_HOME/scripts/t2_gate.py"
    ;;
  t2)
    exec "$PY" "$ORPATH_HOME/orpath/run_t2.py" "$@"
    ;;
  pi)
    exec "$ORPATH_HOME/pi.sh" -a "$@" 2>/dev/null || exec cmd.exe //c "pi.bat -a $*"
    ;;
  openpi)
    "$PY" "$ORPATH_HOME/scripts/orpath_doctor.py"
    exec "$ORPATH_HOME/openpi.sh" "$@" 2>/dev/null || exec cmd.exe //c "openpi.bat"
    ;;
  *)
    echo "unknown command: $CMD" >&2
    exit 2
    ;;
esac
