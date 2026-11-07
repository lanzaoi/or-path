#!/usr/bin/env bash
# OR-Path Unified Launcher: One command to launch Web Studio & Live Watch.
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PORT="${1:-8765}"
SLUG="${2:-live-btube}"
THREAD="${3:-$SLUG}"

URL="http://127.0.0.1:${PORT}/?slug=${SLUG}&thread=${THREAD}"

PY="python3"
if [ -f "$DIR/.venv/bin/python" ]; then
  PY="$DIR/.venv/bin/python"
elif [ -f "$DIR/.venv-314/bin/python" ]; then
  PY="$DIR/.venv-314/bin/python"
fi

echo "======================================================================"
echo "  OR-Path 运筹优化与智能工作台 · Web Studio & Live Watch"
echo "----------------------------------------------------------------------"
echo "  [智能工作舱] 题面文件夹拖拽导入 + 本地混合知识检索 (RAG) + 深度建模"
echo "  [四大求解器]"
echo "    * Tube      : 空间异形圆管 3D 展开与四模式激光共切动态规划"
echo "    * Polyomino : 多联骨牌 CP-SAT 精确覆盖与芯片多目标共边排样"
echo "    * Microgrid : 园区光储充微电网多时段 LP 与日内滚动时域 MPC"
echo "    * Routing   : 最短路 / TSP / CVRP / VRPTW 车辆路径规划"
echo "  [独立验证器] 零信任物理与数学独立重算 (Numbers Truth)"
echo "----------------------------------------------------------------------"
echo "  访问地址: ${URL}"
echo "  退出服务: 请按 Ctrl+C"
echo "======================================================================"

# Try to open browser if in desktop environment
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
  open "$URL" >/dev/null 2>&1 &
fi

exec "$PY" "$DIR/scripts/orpath_watch.py" --slug "$SLUG" --thread-id "$THREAD" --host 0.0.0.0 --port "$PORT" --no-browser
