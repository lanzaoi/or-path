# M2 · polyomino 域桥（进行中）

**法：** `specs/product-flow-sdd.md` §14 M2 · `specs/solvers-and-validate.md` §8  
**冻结：** 主域 **polyomino**（canonical `polyomino_cover`）；tube 不冒充 M2 主叙事。

## 阶段状态

| 阶段 | 内容 | 状态 |
|------|------|------|
| **1** | 域合同 + schema 白名单 + dispatch 注册 | **PASS**（`m2_phase1_contract_gate`） |
| **2** | solve + validate 数字链 | **PASS**（`m2_phase2_solve_validate_gate`） |
| **3** | 产品入口 workdir 可跑 | **PASS**（`m2_phase3_product_workdir_gate`） |
| **4** | Watch 可见 + M1 CTA | **PASS**（`m2_phase4_watch_cta_gate`） |
| **5** | paper/cite 演示 + `m2-gate` 总装 | **PASS**（`m2_phase5_paper_gate` / `m2_gate`） |

## Phase 1 合同

### problem_class

| 输入 alias | 规范名 |
|------------|--------|
| `polyomino`, `poly`, `polyomino_tiling`, `tiling_cover` | **`polyomino_cover`** |

注册表：`orpath/domain_registry.py`

### schema（modeler）

- **必须：** `problem_id` + `problem_class`（或 alias）
- **结构键至少其一：** `board` / `board_ref` / `rows`+`cols` / `pieces` / `piece_types` / …
- **禁止：** objective / path / tour / routes / placements 等解形状键（`FORBIDDEN_SCHEMA_KEYS`）
- 门禁：`tools/gate_schema.py`

### solve 注册

```text
solve_mode polyomino | polyomino_cover | poly
  → tools/solve_polyomino.py
```

`tools/solve_dispatch.py` · `ADAPTER_SCRIPTS`  
未注册假域：schema **unknown**；intake 无 adapter 仍 **BLOCKED**（既有逻辑）。

### Pi 模型（本里程碑会话约定）

- `orpath.subagent_runtime.DEFAULT_MODEL` = **`deepseek-v4-flash`**
- `.pi/settings.json` → `subagents.defaultModel` = **`deepseek-v4-flash`**
- provider：`deepseek`

## 门禁

```bat
set PYTHONPATH=
python scripts\m2_phase1_contract_gate.py
python scripts\m2_phase2_solve_validate_gate.py
python scripts\m2_phase3_product_workdir_gate.py
python scripts\m2_phase4_watch_cta_gate.py
python scripts\m2_phase5_paper_gate.py
orpath.bat m2-gate
```

## Phase 2 · 数字链

| 步骤 | 入口 |
|------|------|
| solve | `mode=polyomino` → `tools/solve_polyomino.py` |
| validate | 覆盖/不重叠/连通 + `objective==len(placements)` |
| 金标 | `fixtures/t3/polyomino_b_q1` obj=6 |

Validate **不重跑 CP-SAT**。

## Phase 3 · 产品入口 + workdir

```bat
set PYTHONPATH=
orpath.bat run --workdir %TEMP%\orpath-m2-poly --slug m2-poly ^
  --problem-id polyomino_b_q1 --problem-class polyomino_cover ^
  --solve-mode polyomino --no-live-subagent --fresh --force

orpath.bat watch-run --workdir %TEMP%\orpath-m2-poly --slug m2-poly ^
  --problem-id polyomino_b_q1 --problem-class polyomino_cover ^
  --solve-mode polyomino --no-browser
```

产物应在 **workdir** 下：`outputs/*-schema.json` `*-solution.json` `*-validate.json`、`runs/<slug>/stages/`。

## Phase 4 · Watch 可见 + CTA

```bat
orpath.bat watch --workdir %TEMP%\orpath-m2-poly --slug m2-poly
:: 或边跑边看
orpath.bat watch-run --workdir %TEMP%\orpath-m2-poly --slug m2-poly ^
  --problem-id polyomino_b_q1 --problem-class polyomino_cover ^
  --solve-mode polyomino --keep-watch
```

检查：L0 stages · L4 solution/validate/schema · 若 paper HUMAN：红条 + **Next actions**（含 `--workdir` + `--solve-mode polyomino`，**不**自动 resume）。

## Claim ladder（Phase 1–5）

| 可说 | 不可说 |
|------|--------|
| polyomino **M2 域桥**全五段 + paper R1/R2 烟 | M3/M4；竞赛全卷已交 |
| Watch + CTA + workdir | 自动 resume / LIVE 必绿 |

## 下一步

M3（SYSTEM launch）或其它 epic — 仅用户批准后开。关单见 `docs/m2-closeout.md`。
