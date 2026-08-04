# OR-Path 架构（当前）

> 活文档。历史长文见 `docs/archive/`。法条以 **`specs/`** 为准。

## 一句话

自然语言 / 题面 → 检索研究 → 建模（schema **无**最优值）→ **求解器出数字** → validate 重算 → 解释 / 论文。  
**LangGraph 管阶段 · Pi 子 Agent 管隔离 · gate 管质检 · Watch 读盘做过程脸。**

## 拓扑

```
用户
  ├─ START-CASE / START-WATCH / orpath.bat   ← 产品入口（非 Hermes）
  └─ 案例目录 ORPATH_WORKDIR
         outputs/  runs/<slug>/  papers/  notes/

安装根 ORPATH_HOME（本仓库）
  ├─ orpath/          LG 节点 · watch · control_plane
  ├─ tools/           solve_* · validate · intake OCR
  ├─ scripts/         doctor · gates · pack · watch-run
  ├─ .pi/agents/      角色定义（Pi 读这里）
  ├─ demo/seed/       默认脸回放数据
  ├─ fixtures/        金标 / 冒烟
  ├─ specs/           硬法
  └─ docs/            活文档 + archive/
```

## 关键合同

| 概念 | 含义 |
|------|------|
| **HOME ≠ WORKDIR** | 代码/agent 定义在安装根；产物只写案例目录 |
| **数字真理** | `objective` 等只来自 `solve_*` + `validate` JSON |
| **真多 Agent** | 磁盘 `outputs/.agents/<slug>/` 有 sub 轨迹；裸 `pi -p` 不算 |
| **Watch** | 无 LLM 聚合；读 workdir 快照；默认 seed = **回放** |
| **schema 门** | 模型 JSON 禁止 objective/解形状键 |

## 主链路（节点）

```
(intake?) → orchestrate → retrieve → research → model → gate_schema
  → solve → gate_validate → explain → draft_paper → cite → review → end
```

失败可 repair（tune / 改 schema）；耗尽 → `HUMAN_REQUIRED`（见 specs）。

## 域

| 域 | 状态 | 入口 |
|----|------|------|
| shortest_path / TSP / VRP | T1–T2 金标 | fixtures + solve_dispatch |
| **polyomino** | M2 主域桥 | `docs/m2-polyomino.md` |
| tube_cut | 旁路演示 | seed `live-btube` obj=99000 FEASIBLE |

## 发布层

| 层 | 内容 |
|----|------|
| **L1** | `git clone` + `orpath.bat setup` |
| **L2** | GitHub Release 半肥 zip（预装 Pi + seed）· `docs/install.md` |

## 明确不做（当前）

- Hermes / OpenPi 当产品壳  
- M3 真 launch 注入、M4 记忆/MCP 史诗（未开）  
- Docker 主路径（可选后置）  
- 把 contest PDF / `.hermes/` / `.env` 推进 public git  

## 延伸阅读

- 法：`specs/product-flow-sdd.md` · `specs/process-visibility.md`  
- ADR：`docs/adr/`  
- 上传边界：`docs/repo-surface.md`  
- 操作：`ORPATH.md`
