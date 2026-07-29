#!/usr/bin/env bash
# Launch Pi (OR-Path runtime) in this terminal (Git Bash).
# Usage:
#   ./pi.sh
#   ./pi.sh -p "hello"
#   ./pi.sh --mode rpc
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PI_BIN="$ROOT/runtime/node_modules/.bin/pi"
if [[ ! -x "$PI_BIN" && ! -f "$PI_BIN" ]]; then
  echo "[ERROR] Pi CLI not found at runtime/node_modules/.bin/pi"
  echo "Run: cd runtime && npm install --ignore-scripts @earendil-works/pi-coding-agent@0.82.1 pi-subagents@0.37.2"
  exit 1
fi
cd "$ROOT"
exec "$PI_BIN" "$@"
