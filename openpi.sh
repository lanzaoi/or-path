#!/usr/bin/env bash
# Launch OpenPi desktop (Electron) from this repo.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/openpi"
cd "$APP"
if [[ ! -f package.json ]]; then
  echo "[ERROR] openpi/package.json missing"
  exit 1
fi
if [[ ! -d node_modules ]]; then
  echo "[ERROR] run: cd openpi && npm ci"
  exit 1
fi
echo ""
echo " ========================================"
echo "  OpenPi  (desktop workbench for Pi)"
echo "  Stop: close window or Ctrl+C"
echo " ========================================"
echo ""
exec npm run dev "$@"
