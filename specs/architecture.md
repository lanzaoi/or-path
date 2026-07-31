# Architecture — 架构法

## 口令

**Pi 当脑，LG 当流程，求解器当计算器，gate 当质检章。**

产品一句话形态：**带验证关卡的 Supervisor–Worker 流水线**  
（hierarchical pipeline with tool verifiers）

## 控制面赢家（唯一）

| 层 | 所有者 | 职责 |
|----|--------|------|
| **全局流程** | **LangGraph** + checkpointer | `now→next`、重试、可恢复 run、`HUMAN_REQUIRED` |
| **局部 LLM 隔离** | **Pi + pi-subagents** | 仅在需要隔离的节点内：派工、真子会话、收文件路径 |
| **硬质检** | **代码 / 求解器工具** | schema、solve envelope、validate 重算、R1/R2 脚本 |
| **窄共享状态** | LG `ORPathState` + 磁盘制品 | 字段有 owner；非自由聊天黑板 |

**禁止双方向盘：** Pi 不得在节点完成后继续「聊着跳阶段」；阶段跳转 **只听 LangGraph**。

## 隐喻校准（反误解）

| 说法 | 对/错 |
|------|--------|
| Pi 总 Agent 是 **全局**老板并最终审核数字 | ❌ |
| Pi 是 **节点内包工头**，带 researcher/modeler 班组 | ✅ |
| LG 是总进度与质检流水线 | ✅ |
| 「审核」若指 objective | 必须是 **solve + validate**，不是包工头口述 | ✅ |

```text
LangGraph（阶段老板）
  ├─ [opt 1.1] intake_ocr/parse ──► 工具（+可选短 lead）──► brief + intake.json（无 objective）
  ├─ retrieve / research  ──► Pi 包工头 ──► or-researcher ──► notes/* 路径
  ├─ model                ──► Pi 包工头 ──► or-modeler    ──► schema（无 objective）
  ├─ GATE schema          ──► 代码
  ├─ solve                ──► mock | networkx | ortools | …
  ├─ GATE validate        ──► 重算；可触发调参重解 / 回 model（见 control-plane）
  ├─ explain / paper      ──► Pi 班组 + R1/R2
  └─ provenance           ──► 磁盘
```

## 双路径（故意保留）

| 路径 | 用途 |
|------|------|
| **CI / deterministic** | LG 节点可写固定制品；`t2_gate` 可复现 |
| **Live multi-agent** | Pi CLI / OpenPi + 真 subagent transcripts |
| **Bridge（T2 硬）** | `ORPATH_LIVE_PI=1` 时 LG 节点经 pi-py-sdk/RPC 拉起 Pi；closeout 必须证明至少一次成功 |

CI 默认可不开 live Pi，但 **T2 closeout 不能没有 bridge 成功证据**（grill Q4-A）。

## 栈锁定（摘要）

| 组件 | 选择 |
|------|------|
| Harness | Pi `@earendil-works/pi-coding-agent` via `runtime/` |
| Subagents | `pi-subagents` pin（如 0.37.2） |
| Glue | LangGraph（Python） |
| Solvers | NetworkX、**真** OR-Tools、mock |
| Agent 模型 | **DeepSeek only** |
| Embedding | 硅基 `BAAI/bge-m3` @1024 |
| Preprocess | MinerU **Cloud**（**语料/知识** PDF；**不是** 1.1 竞赛题面主 OCR） |
| L2 | LightRAG + BM25/FTS + RRF |
| L3 | Cognee **Cloud** |
| L4 | 领域种子图 |
| 题面 OCR（1.1） | pdf 文字层 → PaddleOCR/MCP → manual_stub；见 `problem-intake.md` |
| UI | OpenPi 主；Pi TUI 辅 |
| OUT | Graphiti、Teams、Bus 脊柱、Feynman 主壳 |

## 目录职责（逻辑）

| 路径 | 职责 |
|------|------|
| `orpath/` | LG 状态机、节点、runner、pi_bridge |
| `orpath/subagent_dispatch.py` | **子智能体策略权威**（ADR-0005） |
| `orpath/paper_protocol.py` | **论文环权威** `run_from_solution`（ADR-0004） |
| `orpath/control_plane.py` | **控制面权威** build/seed/invoke（ADR-0003） |
| `orpath/nodes.py` | **阶段节点权威**（核心 + bridge + NodeContext wrap，ADR-0001） |
| `orpath/nodes_product.py` | 兼容 shim → `nodes` |
| `orpath/graph_product.py` | 产品图拓扑（边）；经 ControlPlane 编译 |
| `tools/` | solve_* 适配器、**solve_dispatch / solve_envelope**、validate、R1/R2、schema gate、**intake_ocr/parse/gate（1.1）** |
| `contracts/` | JSON Schema 导出（由 pydantic 生成可） |
| `knowledge/` / `knowledge_svc/` | 语料、种子图、摄取与检索（**≠** 题面 intake） |
| `fixtures/t1|t2/` | 金标与冒烟题 |
| `.pi/agents/or-*.md` | 子 Agent 定义 |
| `specs/` | 本法 |
| `docs/` | 活文档导航 `docs/README.md`；历史 `docs/archive/`；带外见 `docs/OUT_OF_BAND.md` |

## 失败模式（设计时必须防）

1. 双编排打架（Pi vs LG）  
2. 假多 Agent（单会话换人设）  
3. LLM 写 objective  
4. 宽黑板共享状态  
5. 流水线中毒无 gate  
6. 过委派空转（必须有上限 → `HUMAN_REQUIRED`）  
7. 知识检索幻觉引用（无 `chunk_id`）  
8. memory 存 authoritative 最优解  
9. 题面 OCR 静默猜数 / intake 写 objective / 只做最简单子问（见 `problem-intake.md`）  

## 参考

- `IDEA.md` 协作拓扑  
- skill `or-path-multi-agent`（导航用；**冲突以 specs 为准**）
