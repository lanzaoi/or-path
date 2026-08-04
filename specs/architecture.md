# Architecture — 架构法（详细）

**对齐：** `product-flow-sdd.md`  
**状态：** LAW 2026-08-01 全册重写波次

---

## 1. 口令

**Pi 当站内脑，LG 当流程，求解器当计算器，gate 当质检章，时间线当脸。**

产品形态名：**带验证关卡的 Supervisor–Worker 流水线**  
（hierarchical pipeline with tool verifiers）

---

## 2. 分层所有权（唯一控制面）

| 层 | 所有者 | 职责 | 禁止 |
|----|--------|------|------|
| **全局流程** | **LangGraph** + checkpointer | now→next、回边、resume、HUMAN | 聊天跳阶段 |
| **局部 LLM 隔离** | **Pi + pi-subagents** | 站内派工、真子会话、收路径 | 全局编排；批 objective |
| **硬质检与计算** | **Python tools** | OCR、schema、solve、validate、R1/R2、timeline 聚合 | 人格扮演 |
| **窄共享状态** | `ORPathState` + 磁盘 | 字段有 owner | 自由黑板 |
| **过程脸** | timeline 制品 + 可选 HTML | 读盘展示 L0–L4 | LLM 编造协作故事 |

**禁止双方向盘：** 阶段跳转只听 LG。

---

## 3. 隐喻校准

| 说法 | 对错 |
|------|------|
| Pi 是全局老板并审核数字 | ❌ |
| Pi 是节点内包工头 | ✅ |
| LG 是总进度与回修机 | ✅ |
| 「审核 objective」= solve+validate | ✅ |
| 看见思考 = 读 sub 轨迹，不是旁白 | ✅ |

```text
LangGraph
  ├─ intake_*     → 工具
  ├─ research     → Pi 工头 → or-researcher → notes/*
  ├─ model        → Pi 工头 → or-modeler → schema
  ├─ GATE schema  → 代码
  ├─ solve        → dispatch adapters
  ├─ GATE validate→ 重算 / 回边
  ├─ paper 站     → Pi ± verifier/reviewer + R1/R2
  ├─ provenance
  └─（并行制品）timeline 聚合器读盘
```

---

## 4. 双路径（故意）

| 路径 | 用途 | LIVE |
|------|------|------|
| **CI / deterministic** | gate 可复现 | 强制 0 |
| **Live multi-agent** | 真 sub 证据 | 产品默认 1 |
| **Bridge** | 可选 LG↔Pi RPC | 历史 T2 硬证；非 M0 阻塞若 harness 已覆盖 |

CI 可无 live；**不得**用 CI 绿宣称 live MA demo 完成。

---

## 5. 栈锁定

| 组件 | 选择 |
|------|------|
| Harness | Pi `@earendil-works/pi-coding-agent` via `runtime/` |
| Subagents | `pi-subagents` pin（如 0.37.2） |
| Glue | LangGraph（Python） |
| Solvers | NetworkX / CP-SAT / HiGHS / OR-Tools Routing / mock / 域 adapter |
| Agent 模型 | **DeepSeek only**（Pi） |
| Embedding | 硅基 bge-m3@1024 |
| 语料预处理 | MinerU Cloud（**≠** 题面主 OCR） |
| 题面 OCR | pdf_text → ppocr → api → rapidocr |
| L2 检索 | LightRAG + BM25/FTS + RRF |
| 程序记忆 | Skill / `.pi/agents/or-*.md`（战法主轴；见 `memory.md`） |
| L2 prefs | pi-memory 可选 |
| L3 图 | Cognee Cloud **smoke 旁路**（非主记忆） |
| UI 主 | `orpath.bat menu` |
| UI 辅 | Pi TUI；timeline md/html |
| OUT | Graphiti、Teams、Bus 脊柱、OpenPi 产品壳、Feynman 主开发 |

---

## 6. 目录职责

| 路径 | 职责 |
|------|------|
| `orpath/control_plane.py` | 建图/seed/invoke |
| `orpath/graph_product.py` | 拓扑边 |
| `orpath/nodes.py` | 阶段节点 |
| `orpath/subagent_dispatch.py` | MA 唯一 import |
| `orpath/subagent_harness.py` | anti-cosplay |
| `orpath/paper_protocol.py` | 论文环 |
| `orpath/pi_launch_law.py` | 启动合法性 |
| `orpath/timeline.py`（目标） | 过程聚合 |
| `tools/` | solve/validate/intake/R* |
| `contracts/` | JSON schema |
| `knowledge*` | 语料检索 |
| `fixtures/` | 金标 |
| `.pi/agents/or-*.md` | 角色 |
| `specs/` | 本法 |
| `outputs/.agents/` | lead 证据 |
| `runs/` | stage 证据 |

---

## 7. 失败模式（设计必防）

1. 双编排打架  
2. 假多 Agent（cosplay）  
3. LLM 写 objective  
4. 宽黑板  
5. 无 gate 流水线中毒  
6. 过委派无上限  
7. 检索幻觉引用  
8. memory 存权威最优  
9. intake 偷解  
10. **时间线用 LLM 编故事**  
11. 假绑 fixture 金标当 intake 成功  

---

## 8. 与 Feynman 的关系

- `vendor/feynman`：**对照** launch/SYSTEM/手递协议  
- **不**迁产品到 Feynman  
- **不**把 Pi monorepo 当必须 git 提交（与 Feynman 官方「Pi 走 npm 依赖」一致）  
- 未来 M3：`pi_launch_product` 对齐 `--system-prompt` 真注入  

---

## 9. 参考

- `product-flow-sdd.md`  
- `process-visibility.md`  
- ADR-0001…0006  
- `docs/archive/design-notes/IDEA.md`（叙事；冲突以 specs 为准）  
