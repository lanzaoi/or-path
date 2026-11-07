# OR-Path：运筹优化与智能工作台主控指南

主工作台入口：**双击 `START.bat`（Linux / macOS / WSL 使用 `./START.sh`）**；命令行控制面：**`orpath.bat` / `./orpath.sh`**。  
历史 `pi` CLI 包装层（`pi.bat` / `.pi/` / `runtime/`）已全面剥离，系统采用纯 Python 原生架构直连 `.env` 大模型 API 与底层运筹求解器。

## 一键启动（推荐）

| 方式 | 功能说明 |
|------|--------|
| **双击 `START.bat`** / **`./START.sh`** | **主入口**：一键启动 Web Studio 智能做题工作舱与 Live Watch 看板（`http://127.0.0.1:8765`），支持拖拽题面、大模型深度研判、调用运筹求解器与下载验证报告 |
| **`orpath.bat setup`** | 初始化 Python 虚拟环境、安装依赖、释放演示种子并运行 `doctor` |
| **`orpath.bat doctor`** | 检查 Python 环境、运筹求解器（OR-Tools / HiGHS / NetworkX）、独立验证器与 Web Studio 状态 |
| **`orpath.bat demo-m0`** | 运行 M0 最短路基准演示并生成完整验证证据链 (`--slug m0`) |
| **`orpath.bat tube-solve`** | 运行 2026 B 题空间异形圆管激光下料优化求解器 |
| **`orpath.bat pack-release`** | 打包发布压缩包至 `dist/` |

---

## 核心工程资产概览

1. **Web Studio 智能做题舱 (`START.bat`, `START.sh`, `orpath/web/`, `orpath/studio_analyzer.py`)**
   - 原生支持 `.env` 配置的讯飞星火 `spark-x2.6` 与 DeepSeek 模型，配合本地 ONNX `bge-m3` + FTS5 混合知识检索（`knowledge_svc/`）。
   - 支持拖拽导入题面文件夹/PDF/Markdown/文本、三视角并发机理拆解、交互式反问对齐与一键求解（以实时 Live Watch 看板为准，不以静态文件夹作为假交付）。
2. **硬核运筹求解器矩阵 (`tools/` & `scripts/`)**
   - **图与路径规划**：`tools/solve_ortools.py`, `tools/solve_highs.py`, `tools/solve_networkx.py`
   - **多联骨牌精确覆盖与芯片多目标布局**：`tools/solve_polyomino.py`, `tools/solve_polyomino_q3.py`
   - **异形圆管 3D 展开与共切动态规划**：`scripts/b_tube_solve.py`, `scripts/b_tube_geometry.py`, `tools/solve_tube_cut_b2026.py`, `tools/tube_optimization.py`
   - **园区光储充微电网多时段规划与滚动 MPC**：`tools/solve_microgrid.py`, `tools/microgrid_reporting.py`
3. **独立物理与数学验证器 (`tools/validate_solution.py` & `tools/validators/`)**
   - 所有求解结果必须通过确定性验证器的独立重算校验（Numbers Truth）。
4. **单元测试与门禁验证体系 (`tools/test_*.py` & `scripts/*_gate.py`)**
   - `pytest tools/ -q -p no:langsmith`
   - `python scripts/problem_workbench_gate.py`
   - `python scripts/v0_watch_gate.py`

---

## 常用命令行工作流

```bat
:: 1. 启动 Web Studio 与实时看板
START.bat
orpath.bat studio
orpath.bat watch --slug live-btube

:: 2. 四大核心运筹求解器与独立验证器
orpath.bat tube-solve --fast
orpath.bat polyomino-solve polyomino_b_q1
orpath.bat polyomino-q3 --rows 12 --cols 11 --time-limit-s 10
orpath.bat microgrid-solve
orpath.bat routing-solve shortest_path
orpath.bat validate --problem-id tube_cut_b2026 --solution outputs/live-btube-solution.json

:: 3. 知识库检索与同步
orpath.bat knowledge-sync
orpath.bat knowledge-retrieve --query "polyomino CP-SAT" --mode hybrid --topk 5
orpath.bat promote-run --slug <slug>

:: 4. 核心门禁验证
orpath.bat workbench-gate
orpath.bat v0-watch-gate
orpath.bat t1-gate
orpath.bat t2-gate
orpath.bat m1-gate
orpath.bat m2-gate
```
