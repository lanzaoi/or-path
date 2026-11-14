# Verification and DoD — 验证与完成定义

**对齐：** `product-flow-sdd.md`  
**状态：** v1.0.0 更新  
**原则：** 全仓验证统一使用 `.venv/bin/pytest tools/ -q -p no:langsmith` 与 `./orpath.sh test`；历史 `scripts/*_gate.py` 脚手架及归档文档已退休清理。

---

## 0. 验证总原则

1. 单测非 0 → 不得宣称 PASS  
2. CI / 离线回归：**强制** `ORPATH_LIVE_SUBAGENT=0`（或显式 `live_subagent=False`）  
3. `HUMAN_REQUIRED` 是可证路径，不是静默成功  
4. 仅回归绿 ≠ 真实数据端到端交付（Flagship live 交付需真 LLM API + `tools/validate_solution.py` 数值验证）

```bash
.venv/bin/pytest tools/ -q -p no:langsmith
./orpath.sh test
```

---

## 1. 当前产品主路径：Web Studio + Watch + 4-Agent

权威：`product-flow-sdd.md` + `docs/ARCHITECTURE.md`。

| 层级 | 内容 |
|------|------|
| **Web Studio** | `START.sh` / `START.bat` 启动一体化工作台与 Live Watch |
| **CLI / Watch** | `orpath.sh watch` / `orpath.bat watch` + `scripts/orpath_watch_run.py` |
| **Core Tests** | `tools/test_phase0_truth_and_assets.py`、`tools/test_phase1_fast_mode.py`、`tools/test_lean_cartridges_and_graph.py`、`tools/test_task51_dimo_mutator.py` |

---

## 2. 历史阶段收口说明（已归档）

原 T1 / T2 / T3 / Subagent / Paper / Intake 阶段的独立 `scripts/*_gate.py`、`run_t1`/`run_t2`、OpenPi 截图壳与 `.pi-subagents/` transcript 门禁已随 v1.0.0 精简移除，相关核心校验已并入 `tools/test_*.py` 单元测试套件。

---

## 3. 产品默认 vs CI

| 项 | 产品 | CI/离线测试 |
|----|------|-------------|
| LIVE subagent | 默认 ON | 强制 OFF |
| Intake | 有源才开 | 可选 / fixture 驱动 |
| 控制面 | `orpath/graph_product.py` | `pytest tools/` |

---

## 4. 失败语义

| 现象 | 解释 |
|------|------|
| exit != 0 | run 失败如实上报 |
| HUMAN_REQUIRED | 重试预算耗尽，需人工介入 |
| BLOCKED solution | 无可用求解器或必需源数据缺失时诚实停止 |

---

## 5. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-08-01 | 全册重写：M0 置顶；OpenPi 截图退役；与总流程对齐 |
| 2026-11-14 | 同步 v1.0.0 清理：退休旧 `*_gate.py` / `.pi-subagents` / 已删归档路径引用，统一为 `pytest tools/` 验证 |
