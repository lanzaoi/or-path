# Agent 扩展层技术栈调研：MCP · Skills · Tools · Memory

**日期：** 2026-08-04  
**类型：** 研究 / 选型笔记（**非法条**；冲突以 `specs/` 为准）  
**范围：** OR-Path 在 V0+M0 之后可接的 M3/M4 向部件  
**硬约束（已有法）：** V0+M0 前不新开记忆/MCP 史诗；数字权威永远是 solve+validate；**Cognee Cloud 不升主长期记忆**。

---

## 0. 先把四个词拆开（本次纠偏）

此前口语里容易把「长期用 Skill 代替 Cognee」听成 **Memory = Skill**。  
**这是错的。**

| 概念 | 是什么 | 不是什么 | OR-Path 现有落点 |
|------|--------|----------|------------------|
| **Tools** | 可调用的**动作/计算**（输入→结构化输出） | 说明书、回忆 | `tools/solve_*` `validate_*` intake OCR R1/R2 |
| **Skills** | **怎么解题**的程序手册（步骤、禁区、检查单、角色纪律） | 「上次那题怎么过的」流水账 | `.pi/agents/or-*.md`；将来仓内 `skills/` |
| **Memory** | **记住你以前怎么解、哪些关键点有效**（跨 run 过程/教训） | 标准答案库；也不是战法手册本体 | 今日缺口：只有 L0 本题盘 + 可选 pi-memory prefs；**缺跨题 process memory** |
| **MCP** | **外设接入协议**（把别人的 tool/resource 接到 host） | 编排器；不是记忆库 | M4「1 个 MCP」叙事；Pi 核心无原生 MCP |

### 0.1 正确分工一句话

```text
Tools     = 做（算 / 读 / 写制品）
Skills    = 教怎么做（可复用解题程序）
Memory    = 记得以前怎么做、卡在哪、哪条路径管用（过程与关键点）
MCP       = 用标准插头接外部能力（可选）
Knowledge = 领域语料/文献/种子图（≠ Memory；见 knowledge-and-retrieval.md）
```

### 0.2 Skill 与 Memory 的关系（有桥，不相等）

```text
一次 run 落盘（L0 notes/outputs/runs）
        │
        ▼
  Memory：提炼「本题流程 + 关键决策点」
  （如：VRP 先锁容量维 → Routing；某 OCR 坑；回修阶梯哪条奏效）
        │
        │  同一模式重复 N 次、且稳定
        ▼
  Skill：升格为通用解题程序（检查单 / agent md）
        │
        ✗  禁止把 objective / 最优 tour 当 Memory 或 Skill 的权威答案
```

- **Skill 里可以有「解题 skill」**（这是主用途）。  
- **Memory 不是 skill 文件本身**，而是对历史解题过程的可检索记录。  
- 法条 `specs/memory.md` 里把 Skill 标成「程序记忆」在认知科学上叫 *procedural*；用户口中的 Memory 更接近 **process / episodic lessons**。  
  **产品命名建议：** 文档里写清  
  - *procedural playbook* → **Skill**  
  - *process memory / lesson store* → **Memory**  
  避免再把二者绑成一个词。

### 0.3 与 Cognee

| | |
|--|--|
| **决定** | **长期放弃 Cognee Cloud 作主记忆**（与现行 `memory.md` / product-scope OUT 一致） |
| **可保留** | 可选 smoke / 作品集一句「图实验」；**不**挡主路径、不进 gate |
| **不替代方案** | 不是「全改 Skill」；主长期记忆走 **磁盘 process cards + 检索**（见 §4） |

---

## 1. 现状快照（本仓）

| 层 | 已有 | 缺口 |
|----|------|------|
| **Tools** | 厚：solve 多后端、validate、intake、gate、R1/R2 | 对外统一 registry / 可选 MCP 暴露；工具描述 token 纪律 |
| **Skills** | 角色薄设定 `.pi/agents/or-*.md`；Hermes/vendor 有参考 skill | 仓内 Agent Skills（`SKILL.md`）族未产品化；按站按需加载未硬化 |
| **Memory** | L0 本题制品；L1 LG checkpointer；可选 `@samfp/pi-memory` prefs | **跨 slug 的「上次怎么解」过程库**未建；Cognee 仅旁路且非主轴 |
| **MCP** | 导航侧可有 OCR MCP；产品 Pi **无**内置 MCP | M4「1 MCP」未做；接入策略未钉 |
| **Knowledge** | seed 图 + hybrid（LightRAG/BM25/FTS/RRF）+ MinerU 语料 | ≠ Memory；勿混 |

**栈锁定（architecture.md）：** Pi + pi-subagents · LangGraph · DeepSeek-only agent · OR-Tools/NetworkX/CP-SAT/HiGHS · pydantic · 硅基 bge-m3 · （知识）LightRAG+BM25。

---

## 2. Tools — 技术栈

### 2.1 产品内（主路径，已锁定）

| 用途 | 推荐 | 理由 |
|------|------|------|
| 求解 | NetworkX / CP-SAT / HiGHS / OR-Tools Routing / 域 adapter | 数字真源；claim ladder 已定 |
| 校验 | `validate_solution.py` 统一重算 | 禁散文最优 |
| 契约 | pydantic v2 → `contracts/` | schema 门 |
| 调度 | `solve_dispatch` + LG nodes | 单一计算面 |
| 调用形态 | **Python CLI / 子进程 JSON**（Pi bash/read 或 harness 直接调） | Pi 哲学：CLI > 堆 MCP tool schema |

### 2.2 设计原则（行业共识 + Pi 立场）

1. **少而尖的 tool 面**：solve / validate / intake / gate / 写约定路径。  
2. **大结果落盘，返回路径**（Feynman / Pi file-handoff）。  
3. **描述要短**：避免 MCP 式「一次 list 吃掉 1 万 token」。  
4. **确定性工具不进 LLM 人格**（architecture：硬质检与计算属 Python tools）。

### 2.3 可选扩展（非主路径）

| 选项 | 何时 | 栈 |
|------|------|-----|
| 工具注册表 | 多 adapter / 外部插件 | 内存 dict + JSON schema；或 OpenAPI 子集 |
| LangChain tool 包装 | 仅当 LG 节点内要 StructuredTool | `langchain-core` tools；**不要**把 LG 改成「只有 LangChain tools」 |
| MCP 暴露本仓 tools | M4 对外互操作 / 作品集 | 见 §5：`mcp` Python SDK / FastMCP 包一层 **只读或白名单** |

**不推荐：** 为已有 `tools/*.py` 再造一套平行「Agent Tools 框架」重写求解链。

---

## 3. Skills — 技术栈（解题程序，不是 Memory）

### 3.1 标准形态

| 项 | 选择 |
|----|------|
| 格式 | **Agent Skills 开放标准**：目录 + `SKILL.md`（YAML: `name`/`description` + Markdown 正文） |
| 规范源 | [agentskills.io/specification](https://agentskills.io/specification)（Anthropic 发起，跨 Claude Code / Codex / 多 client） |
| 渐进披露 | L1 仅 name+description 常驻；触发后再读正文；references/scripts 再按需 |
| OR 内容 | 题型解题 skill（VRP 建模检查单、TSP 精确轨选用、polyomino 约束纪律、anti-cosplay、论文 cite 阶梯…） |
| 权威冲突 | **specs > skill**；skill 不复制大段法条（coding-conventions） |

### 3.2 运行时加载（OR-Path / Pi）

| 选项 | 栈 | 评价 |
|------|-----|------|
| **A. 仓内 skills + 启动注入描述目录**（推荐主） | `skills/or-*/SKILL.md`；harness / `pi_launch_law` 按 stage 选择 skill 名列表 | 与 s07 Skill Loading 对齐；不依赖 MCP |
| **B. `.pi/agents/or-*.md` 继续作角色薄 skill** | 已有 | 保留；与 A 互补（角色 vs 题型） |
| **C. Pi packages 自带 skills** | npm 包 manifest | 适合可分发扩展，非核心必需 |
| **D. 把 skill 当 MCP prompt/resource** | 过度 | M4 前不做；skill 应是文件，不是协议 |

### 3.3 不宜塞进 Skill 的

- 某次 run 的 objective / 最优解  
- 完整竞赛标准答  
- 未经验证的「此题必用 X」假保证  
- **Memory 流水账**（那是 §4）

### 3.4 与「解题 skill」示例边界

| Skill 示例 | Memory 示例（不同） |
|------------|---------------------|
| `or-vrp-model`：必须字段、禁 objective、validate 阶梯 | 「slug=case-07：先失败在缺 distance_matrix，补 schema 后 Routing 绿」 |
| `or-tsp-exact`：n≤20 走 CP-SAT 宣传轨 | 「n=12 时 HiGHS 对照慢 3×，下次直接 cpsat」 |
| `or-polyomino-bridge`：adapter 入口与 schema 形 | 「Q3 30×30 用了 solve_polyomino_q3，笔记路径 …」 |

---

## 4. Memory — 技术栈（记住以前怎么解 / 关键点）

### 4.1 认知分层（产品要用的）

| 类型 | 含义 | OR 载体建议 |
|------|------|-------------|
| **Working** | 本题进行中 | L0 `outputs/ notes/ papers/` + Watch |
| **Run state** | 阶段/resume | L1 LangGraph checkpointer（`runs/`，sqlite 类） |
| **Process / episodic lessons** | **上次怎么解、关键节点** | **新建：Lesson / Process Card 库**（主加强，替代 Cognee 主叙事） |
| **Prefs** | 个人习惯、环境默认 | `@samfp/pi-memory`（已装，保持轻） |
| **Procedural playbooks** | 稳定怎么解 | **Skill**（§3）— **不算 Memory 本体** |
| **Semantic domain** | 文献/领域结构 | Knowledge hybrid + L4 种子图 |
| **Graph cloud** | 跨任务关系图 | Cognee **旁路 only / 可弃主叙事** |

### 4.2 推荐主方案：**Process Memory = 结构化卡片 + 本地检索**（无 Cognee）

目标：research/model 站开跑前，能问：

> 「类似 VRP / 类似题面，我们以前怎么建模、踩过什么坑、哪条回修有效？」

返回的是 **流程与关键点**，并 **带 L0 路径 provenance**；**不**返回权威 objective。

#### 4.2.1 存储（P0 极简，可先做）

| 组件 | 选择 | 说明 |
|------|------|------|
| 真源 | Markdown / JSON 卡片 | 例如 `knowledge/lessons/` 或 `memory/lessons/`（gitignore 大数据；可提交模板+少量种子） |
| 卡片字段（建议） | `id, slug, problem_class, created, summary, key_decisions[], pitfalls[], skills_used[], artifact_paths[], tags[]` | **禁止** `objective` / `optimal_*` 作权威字段；若提及数字必须 `source_path` |
| 写入时机 | run 成功/失败后 **受控提炼**（脚本或可选 LLM 总结） | 禁止全量 transcript 灌库当记忆 |
| 人审 | 可选 queue：自动 draft → 人工/门禁升格 | 防垃圾记忆污染 |

#### 4.2.2 检索（P1）

| 层 | 栈 | 说明 |
|----|-----|------|
| 词法 | **SQLite FTS5** 或现有 `knowledge_svc` BM25/FTS | 本仓已有 FTS/BM25 模式，可复用 |
| 向量（可选） | 硅基 **bge-m3@1024**（已锁定 embedding） | 与知识轨同 embed，索引隔离 `lessons_*` |
| 融合 | 现成 **RRF**（`knowledge_svc/rrf_fuse.py`） | 少造轮子 |
| API | `retrieve_lessons(query, problem_class, k)` → 路径列表 | research 节点读路径，不进数字权威 |

#### 4.2.3 运行时注入

| 站 | 行为 |
|----|------|
| research / model | 按 class+题面摘要检索 top-k lessons → 写入 `notes/<slug>-lessons.md` 或 system 短摘要 |
| explain / paper | 可引用「过程教训」路径，不引用记忆数字 |
| Watch | **不**从 Memory 读 objective（法条） |

#### 4.2.4 Prefs 辅线（已有）

| | |
|--|--|
| 包 | `@samfp/pi-memory` → `.pi/memory/` |
| 用途 | 「解释默认中文」「LIVE 默认」等 **短 prefs** |
| 不做 | 跨任务图谱；解题过程主库；objective |

#### 4.2.5 明确不采用 / 降级

| 方案 | 态度 | 原因 |
|------|------|------|
| **Cognee Cloud 主记忆** | **放弃主轴** | 非数字权威、额度/503、与 Skill/过程库职责重叠；法条已 OUT 生产化 |
| Mem0 / Zep / Graphiti 云脑 | OUT 主路径 | 重、偏对话 CRM；OR 要可审计文件 |
| Hindsight 等 | 非目标（已有 vendor 仅参考） | 与 L3 重叠 |
| 只用 Skill 顶替 Memory | **否** | 用户纠偏：Skill=解题程序；Memory=过程关键点 |
| 向量库当唯一记忆 | 不够 | 缺结构化「关键决策」字段与 provenance |
| 把完整 solution JSON 当记忆 | **禁止** | 易变相标准答案库 |

### 4.3 学术对齐（选型理由，非依赖）

- 程序记忆（procedural）≈ Skills / prompts / tools 定义。  
- 情节/过程记忆（episodic）≈ 跨会话事件与决策轨迹 → **Lesson cards**。  
- 语义记忆（semantic）≈ 知识库/种子图 → **Knowledge**。  
OR 正确性仍绑定 **tool verify**，记忆只改善 **起步质量与避坑**，不签发最优。

### 4.4 Memory 技术栈总表（建议冻结候选）

| 层级 | 技术 | 优先级 |
|------|------|--------|
| 工作记忆 | 磁盘 L0 + Watch | 已有 P0 |
| Run | LangGraph checkpointer（sqlite） | 已有 P0 |
| **Process memory** | **MD/JSON lessons + FTS5/BM25 ± bge-m3 + RRF** | **M4 主推** |
| Prefs | pi-memory | 可选 P3 |
| 升格 | 重复 lesson → 人工/脚本 → Skill | 流程 P1 |
| 图实验 | Cognee smoke | P4 可关 |

---

## 5. MCP — 技术栈

### 5.1 MCP 是什么、不是什么

| 是 | 不是 |
|----|------|
| Host↔Server 协议：Tools / Resources / Prompts | LangGraph 替代品 |
| 互操作插头（IDE、其它 agent、云 OCR…） | 记忆系统 |
| 可选外设层 | V0/M0 阻塞项 |

Spec 演进（2025–2026）：stdio · Streamable HTTP；list 结果可缓存；会话模型趋无无状态核心等。实现以官方 SDK 为准。

### 5.2 Pi 生态现实（关键）

- Pi **核心不内置 MCP**（作者立场：多数场景 CLI/skills 更省 token）。  
- 社区路径：  
  - **mcporter**：CLI/TS 调 MCP，agent 当 bash 用  
  - **pi-mcp-adapter**：单 proxy tool 按需发现，避免 tools/list 炸上下文  
- OpenClaw 等也倾向 **MCP → CLI** 或懒加载。

### 5.3 OR-Path 推荐策略（M4：先 1 个再扩）

**原则：MCP 可选外壳；主链仍 Python tools + 文件。**

| 模式 | 技术栈 | 适用 |
|------|--------|------|
| **M4-A 对外暴露（推荐第一个）** | Python **`mcp` SDK / FastMCP**，stdio 或 streamable-http；白名单包装 `validate` / `doctor` / `timeline 只读` / `retrieve_lessons` | 作品集：其它 Host 可调 OR 能力；**禁止**暴露「无 validate 的假 solve 权威」 |
| **M4-B 对内消费** | 仅当外部能力无稳定 CLI 时：mcporter 或 pi-mcp-adapter | 例：某云 OCR 只提供 MCP |
| **默认** | **不**把 solve 主链改成「全 MCP 化」 | 保 CI、token、门禁简单 |

### 5.4 MCP vs Skills vs Tools（决策树）

```text
需要稳定计算且本仓已有实现？ → tools/*.py（主）
需要教模型「怎么做」？         → Skill（SKILL.md / agent md）
需要记住「以前怎么做」？       → Memory lessons（§4）
需要给外部 Host 用 / 接无 CLI 的外设？ → 考虑 MCP
既要省 token 又要 MCP？        → proxy/meta-tool 或 mcporter CLI，禁止全量 tools/list 常驻
```

### 5.5 LangGraph 关系

- LG = 编排 + checkpointer。  
- MCP = 工具插头。  
- 可用 `langchain-mcp-adapters` 把 MCP tool 嵌进 LG 节点——**OR 非必须**；节点继续调本仓 Python 更清晰。

---

## 6. 总览架构（目标态，非当前已实现）

```text
                    ┌──────────── Watch / menu ────────────┐
                    │         读盘 · 无 LLM 编故事            │
                    └─────────────────┬────────────────────┘
                                      │
 LangGraph (阶段 · resume · 回修)
    │
    ├─ nodes → Pi lead + pi-subagents（真 MA）
    │              │
    │              ├─ Skills（解题程序，按需）
    │              ├─ Memory lessons（过程关键点检索）
    │              └─ bash/read → 路径手递
    │
    ├─ Tools（solve / validate / intake / R*）  ←── 数字权威
    │
    ├─ Knowledge（语料 hybrid + 种子图）         ←── 文献/领域 ≠ Memory
    │
    └─ （可选）MCP Server 白名单外壳
              或 mcporter 调外部 MCP
```

---

## 7. 分期建议（对齐 specs 里程碑）

| 阶段 | 做 | 不做 |
|------|----|------|
| **现在 → V0+M0** | 守 L0/L1、真 sub、Watch；角色 md 可用 | 记忆史诗、MCP 市场、Cognee 生产化 |
| **M0 后 / 并行薄** | 起草 lesson 卡片 schema；1–2 个解题 Skill 样例；写入规范 | 自动全量灌记忆 |
| **M3** | launch SYSTEM 真注入（可带 skill 列表 + lessons 检索摘要） | — |
| **M4** | **Memory 叙事**（lessons 检索可演示）+ **1 MCP**（只读或白名单） | 多 MCP 市场；Cognee 主记忆；Memory=Skill 混谈 |
| **永不** | 记忆/Skill/MCP 覆盖 validate；objective 权威进记忆 | |

---

## 8. 依赖候选清单（按层，实施时再 pin）

### 已在主链

- `langgraph`, `pydantic`, `httpx`, `networkx`, `ortools`, `highspy`, `rank-bm25`, embedding 硅基 bge-m3  
- Pi runtime + `pi-subagents` + 可选 `@samfp/pi-memory`

### Skills

- **无强制新 runtime 依赖**；约定目录 + Markdown  
- 可选：与 agentskills 校验器/linter（若生态有 CLI 再引入）

### Memory（process）

- stdlib + **SQLite FTS5**（或复用 `knowledge_svc`）  
- 可选向量：现有 embed 客户端  
- 提炼：可选 DeepSeek（与 Pi 同模型族）；**环境安装类仍不走 DeepSeek 通道**

### MCP（M4）

- Server：`mcp`（官方 Python SDK）或 FastMCP  
- Client（仅必要时）：mcporter / pi-mcp-adapter  
- **不要**为 M4 引入完整 LangChain agent 运行时替代 Pi

### 明确不进主 requirements

- Cognee 生产依赖  
- Graphiti / Mem0 / 企业记忆云  
- 第二套求解框架

---

## 9. 风险与反模式

| 反模式 | 后果 | 正确做法 |
|--------|------|----------|
| Memory = Skill | 过程库与战法手册搅在一起，无法检索「上次」 | 分库分文案 |
| Skill 塞标准答 | 假权威、 mag 数字 | 只写程序与门禁 |
| Lesson 塞 objective 无路径 | 记忆覆盖 validate | 禁权威字段；强制 provenance |
| 全工具 MCP 化 | token 爆、CI 脆、双路径 | 本仓 CLI/Python 主；MCP 外壳 |
| V0 前开 M4 | 脸与 Demo 再次延期 | 守 specs 闸门 |
| Cognee 回流主叙事 | 与「放弃云图脑」冲突 | smoke only 或删除叙事 |

---

## 10. 建议的下一步（研究后，仍属计划非开工）

1. **改法条措辞（可选小 PR）：** `memory.md` 增加一节「Skill ≠ Process Memory」表，避免再混。  
2. **冻结 lesson 卡片 schema**（contracts 级草稿）。  
3. **选 1 个解题 Skill 样例**（如 `or-model-discipline`）验证 s07 加载。  
4. **M4 MCP 第一个工具候选：** `orpath_doctor` 或 `retrieve_lessons` 只读 — 比暴露 solve 更安全。  
5. **实现闸门：** 仍以 V0+M0 体验 PASS 为前置。

---

## 11. 参考（调研源类型）

- 本仓：`specs/memory.md` `knowledge-and-retrieval.md` `product-flow-sdd.md` §11 `architecture.md` `docs/archive/design-notes/harness-ideal-on-lcc-skeleton.md` s07/s09/s19  
- Agent Skills：agentskills.io specification；Anthropic engineering on skills  
- MCP：modelcontextprotocol.io；Python SDK / FastMCP；2026-07-28 spec 方向  
- Pi：无内置 MCP；mcporter；pi-mcp-adapter；Skills/CLI 优先论述  
- 记忆分类：procedural vs episodic vs semantic（行业综述与 CoALA 式划分）  
- 本仓知识轨：可复用 FTS/BM25/RRF/bge-m3 作 lessons 检索，避免新云脑  

---

## 12. 结论（可对外说的短版）

1. **Tools**：继续本仓 Python/求解器；少而尖；大结果落盘。  
2. **Skills**：Agent Skills（`SKILL.md`）+ 现有 `or-*.md` = **解题程序**；按需加载。  
3. **Memory**：**不是 Skill**；用 **过程/关键点卡片 + 本地 FTS/向量** 记住「以前怎么解」；**放弃 Cognee 主轴**；prefs 仍 pi-memory。  
4. **MCP**：M4 用官方 Python SDK **白名单 1 个**外壳或 mcporter 接外设；**不**替代主工具链。  
5. **开干顺序**：V0+M0 →（薄）lesson schema + 1 skill → M3 launch 注入 → M4 memory 演示 + 1 MCP。
