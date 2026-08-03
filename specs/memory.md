# Memory — 记忆分层（详细）

**对齐：** `product-flow-sdd.md`  
**状态：** LAW 2026-08-03（运筹长期战法：Skill 主轴；Cognee 降为旁路 smoke）  
**M0：** 只强制 L0+L1；L2 prefs / L3 图 / Skill 库加强 **均不挡** Demo  
**开闸：** V0+M0 PASS 前不新开「记忆大脑 / Cognee 生产化」史诗

---

## 0. 选型总则（运筹域）

**OR-Path 产品记忆 ≠ Hermes MEMORY.md**

运筹要跨任务保留的，优先是 **稳定战法**（怎么建模、怎么验收、角色纪律），不是越长越大的云端关系图。  
正确性来自 **solve + validate**，不来自图回忆。

| 优先级 | 载体 | 运筹用途 |
|--------|------|----------|
| **P0** | **L0 磁盘制品** | 本题过程与数字真源 |
| **P0** | **L1 checkpointer** | 阶段、回修计数、resume |
| **P1** | **Skill / agent 手册**（程序记忆） | 题型套路、检查单、禁区、solver 选用启发式 |
| **P2** | **L4 种子图 + 语料检索** | 领域结构与文献 chunk（见 `knowledge-and-retrieval.md`） |
| **P3** | **L2 pi-memory** | 短 prefs / 个人流程教训 |
| **P4** | **L3 Cognee Cloud** | 跨任务图 **smoke / 作品集一句**；**非**主长期记忆 |
| — | Hermes MEMORY | 仅导航 Agent；**非产品** |
| — | Hindsight 等与 L3 重叠物 | **非目标** |

**一句话：**  
**Skill（程序记忆）> L0/L1 真相 > 种子图/检索 > pi-memory prefs ≫ Cognee 图。**  
用 Skill **承接「会解题的套路」**；Cognee **不删除、不升级为主轴**。

Skill ≠ 自动 episodic 记忆：流水账仍在 L0；**可复用教训经人/流程提炼后** 升格为 Skill 或种子图边，禁止把完整 solution 当 Skill 标准答案库。

---

## 1. 分层表

| 层 | 归属 | 内容 | M0 | 以后 |
|----|------|------|----|------|
| **L0 工作记忆** | `outputs/` `notes/` `papers/` plan ledger | 过程与制品真相 | **必须** | 必须 |
| **L1 Run** | LG checkpointer `runs/` | 阶段、计数器、路径 | **必须** | 必须 |
| **Skill（程序）** | 仓内 skills / `.pi/agents/or-*.md` / 固化检查单 | 稳定战法、角色纪律、建模/验收步骤 | 不挡；已有角色 md | **主加强轴**（战法沉淀） |
| **L2 prefs** | `@samfp/pi-memory` · `.pi/memory/` | 习惯、短教训 | 可选 | 轻量加强 |
| **L3 图** | Cognee Cloud | 跨任务图 smoke | 可选 | **保持 smoke**；不设生产主记忆 |
| **L4** | 种子图 | ProblemClass–Constraint–Solver–Case | 已有 | 维护 |
| — | Hermes MEMORY | 导航 Agent | 非产品 | — |
| — | Hindsight 等 | 与 L3 重叠 | 非目标 | — |

---

## 2. 禁止写入（非 L0 solution 权威）

下列 **不得** 作为 Skill / L2 / L3 / 检索摘要的 **权威答案**：

- objective / optimal_*  
- 最终 path/tour/routes 当「标准答案库」  
- 完整 solution 当唯一真相  

若讨论提到数字，必须同时指向 **磁盘 solution 路径**（L0）+ validate。  
时间线 / watch **不**从 memory 或 Skill 读 objective。

---

## 3. Pi Session

- compaction **不可靠**保存精确坐标/容量  
- 关键数进 schema/solution/state  
- 思维链若进 session，**可视化以 process-visibility 日志为准**，不以 compact 摘要为准  

---

## 4. Skill（程序记忆 · 运筹主加强轴）

### 4.1 定位

- **是：** 按需加载的领域手册与步骤（对齐 LCC s07 Skill Loading 心智）  
- **不是：** 替代 L0/L1；不是自动把每次 run 灌进云图  

### 4.2 宜写入

- 题型纪律（如 VRP 必须多车/容量字段）  
- schema 禁键、手递路径约定、anti-cosplay 要点  
- validate / 回修阶梯的检查单（指向 specs，不复制数字）  
- solver 选用启发式（精确轨 vs Routing 诚实话术）  
- 角色边界：`or-modeler` 不写 optima 等  

### 4.3 不宜写入

- 某次 run 的 objective / 最优 tour  
- 竞赛整卷标准答  
- 未经验证的「此题一定用 X」教条（可写候选与门禁，不写假保证）  

### 4.4 与角色文件

- `.pi/agents/or-*.md` = 站内角色薄设定（Skill 族近亲）  
- 仓级 OR skills（若有）与 specs 冲突时以 **specs** 为准  

### 4.5 沉淀流程（理想）

```text
run 落 L0/L1
  → 可复用教训被识别
  → 升格 Skill 或 agent md / 种子图边（人工或受控流程）
  → 下次 research/model 按需加载
```

---

## 5. pi-memory（L2）

- path：`.pi/memory/`（gitignore）  
- 用途：**短**偏好与流程教训（「解释默认中文」「某环境 LIVE 默认」）  
- 与 Skill 分工：prefs 易变、个人化 → L2；稳定战法 → Skill  
- consolidation 模型：DeepSeek  
- smoke 不得断言数字最优  
- **不**承担跨任务图谱、**不**替代 Skill 库  

---

## 6. Cognee（L3 · 旁路）

- 详见 `knowledge-and-retrieval.md` §7  
- **定位：** Cloud Free **smoke** + 作品集「有图记忆实验」话术；**非**运筹长期记忆主轴  
- 与 pi-memory：图探索 vs 会话 prefs  
- 与 Skill：**不互相替代**；战法不靠 Cognee 存储  
- 与 L4 种子图 / LightRAG：允许概念重叠；**生产检索与领域结构以知识轨 + L4 为准**  
- 503 → LOCAL_FALLBACK 可接受 smoke  
- **禁止** objective dump 入库；禁止双写权威解  
- **禁止**立项「Cognee 生产化 / 替换 Skill」抢 V0+M0  
- 以后默认：**保持可选 smoke**，不升「必须加强为产品记性」  

---

## 7. 与可视化

- 时间线 / watch **不**从 memory、Skill、Cognee 读 objective  
- L0/L1 是过程可视主源（L0–L4 可视层见 `process-visibility.md`，勿与记忆 L0–L4 混名时以上下文区分）  

---

## 8. 检查清单

- [ ] 不声称 Hermes 为产品记忆  
- [ ] 不声称 Cognee 为 OR 主长期记忆  
- [ ] 稳定战法优先落 Skill / agent md / specs，而非只进云图  
- [ ] memory / Cognee / Skill smoke 无权威 optima  
- [ ] provenance 指向 solution 文件  
- [ ] M0 不依赖 L2/L3/Skill 加强才绿  
- [ ] V0+M0 前无「记忆大脑」史诗  

---

## 9. 分期与展望

| 阶段 | 记忆相关 |
|------|----------|
| **现在 → M0** | 守 L0+L1；角色 md 可用；不扩 Cognee |
| **M0 后** | 战法沉淀 → Skill；prefs 可 menu 查看（可选） |
| **M4 级叙事** | 「有程序记忆 + 可选图 smoke」；仍禁记忆覆盖 solve |
| **永不** | 记忆/Skill/图 覆盖 validate；Cognee 当标准答案库 |

跨 slug 教训检索：优先 **Skill 库 + notes 模板 + L4**；不以 Cognee 为唯一方案。

---

## 10. 参考

- `product-flow-sdd.md` §11  
- `knowledge-and-retrieval.md`  
- `process-visibility.md`（可视 L 层 ≠ 记忆 L 层）  
- `docs/harness-ideal-on-lcc-skeleton.md` s07/s09 讲法  
