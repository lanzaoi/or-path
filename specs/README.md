# OR-Path `specs/` — 规范索引（SDD 全册）

**地位：** 本目录是产品与工程的 **硬法（living law）**。  
**全册重写日：** 2026-08-01（与总流程主合同对齐；旧零散文已并入分册）。

---

## 1. 冲突优先级

```text
1. 可运行代码 + 门禁真实输出（t1_gate / t2_gate / t2_gate_cloud / intake_gate / subagent_gate / paper_* …）
2. specs/product-flow-sdd.md     ← 总流程 · Demo M0 · 控制面隐喻 · 非目标 · 优先级
3. specs/process-visibility.md   ← 过程 / sub 思考可视化合同（与总流程配套）
4. specs/** 其它分册             ← 字段、阈值、adapter、历史 DoD；不得推翻 (2)(3)
5. AGENTS.md
6. docs/archive/plans/*（历史施工单；可过期）
7. docs/**（活文档 docs/README.md；历史 docs/archive/）
8. IDEA.md / README 叙事
9. 聊天记录
```
（`.hermes/` 整棵本机-only，见 `docs/repo-surface.md`。）

Hermes `MEMORY.md` **不是**产品法。

---

## 2. 文件地图（按主题）

| 文件 | 主题 | 何时必读 |
|------|------|----------|
| **`product-flow-sdd.md`** | ★ 总项目流程主合同 | **任何实现前** |
| **`process-visibility.md`** | ★ **实时过程台硬底线**（在哪看 / L0–L4 / 假交付） | **任何宣称「能看见」之前** |
| `product-scope.md` | 范围、claim ladder、里程碑状态 | 改范围/对外话术前 |
| `architecture.md` | LG/Pi/脚本分层、双路径、失败模式 | 改拓扑前 |
| `control-plane.md` | 阶段图、回修计数、字段 owner、CLI | 改图/边/计数器前 |
| `multi-agent.md` | 真 MA、角色、harness、dispatch | 改 subagent 前 |
| `solvers-and-validate.md` | 求解轨、validate、调参白名单 | 改求解前 |
| `paper-and-review.md` | 论文环 A/B、R1/R2、revise | 改论文前 |
| `problem-intake.md` | 1.1 OCR/审读/禁键 | 改读题前 |
| `memory.md` | L0–L1 必须；Skill 战法主轴；Cognee 旁路；禁权威 optima | 改记忆前 |
| `knowledge-and-retrieval.md` | MinerU/LighRAG/BM25/Cognee | 改知识前 |
| `contracts.md` | JSON 契约形状 | 改 schema/solution 前 |
| `gates-and-dod.md` | 历史 T1–1.2 DoD + 回归命令 | 关单/回归前 |
| `t3-lg-skeleton.md` | 产品图骨架 freeze | 改 checkpointer/resume 前 |
| `t3-vrp-tw.md` | CVRPTW 叶 | 改 TW 前 |
| `openpi-boot-ma-ocr.md` | menu 主控；OpenPi 已删 | 改入口/OCR 默认前 |
| `1.2-architecture-soak.md` | soak 与 BLOCKED 诚实 | 真题无 adapter 前 |
| `coding-conventions.md` | 编码约定 | 写代码时 |
| `git-and-ai-hygiene.md` | git/密钥/AI 卫生 | 提交前 |

---

## 3. 阅读顺序（新人 / 新会话）

```text
0. **`product-flow-sdd.md` — ★ 总项目流程主合同**（LG 翻页 / Pi 站内 / 打回 / **V0+M0**）  
1. **`process-visibility.md` — ★ 实时过程台硬底线**（在哪看、L0–L4、禁止假交付）  
2. `architecture.md` — LG / Pi / gate / 双路径  
3. `control-plane.md` — 阶段图、字段 owner、回修阶梯  
4. `multi-agent.md` — 角色与 harness  
5. `solvers-and-validate.md` — 求解与校验  
6. `paper-and-review.md` — R1/R2  
7. `problem-intake.md` — 1.1  
8. `contracts.md` — JSON  
9. `memory.md` + `knowledge-and-retrieval.md`  
10. `product-scope.md` + `gates-and-dod.md`  
11. `t3-*` / `openpi-*` / `1.2-*`（按需）  
12. `coding-conventions.md` + `git-and-ai-hygiene.md`  


---

## 4. 与其它层分工

| 层 | 路径 | 内容 |
|----|------|------|
| **Specs** | `specs/` | 稳定约束、DoD、非目标 |
| **Plans** | `docs/archive/plans/` | 历史切片（可过期）；新计划本地写完再归档 |
| **Docs** | `docs/` | smoke / ADR / closeout；上传边界 `repo-surface.md` |
| **Code** | `orpath/` `tools/` `knowledge_svc/` | 实现 |
| **Harness 元** | 不建仓库 `.agents/` 当 T2 法（产物在 `outputs/.agents`） | — |

---

## 5. SDD 循环

```text
读 product-flow §9（M0）→ 只做缺口
  → 路径白名单实现
  → 真命令验收（记录路径/exit）
  → 行为变：先改 specs 再改代码叙事
  → M0 PASS 前禁止记忆/MCP/大域桥史诗
```

Task 自检：

- [ ] 未越权非目标  
- [ ] 未第二「正式入口」  
- [ ] 数字非 LLM  
- [ ] 真 MA 有 toolCall 证据  
- [ ] 无密钥 / 无盲目 `git add -A`  

---

## 6. 维护

- 小行为：改对应分册 + 必要时总流程 §13 缺口表  
- 大重冻：先改 `product-flow-sdd.md` → 分册 → plan  
- **禁止**在 skill 复制大段产品法；skill 只指针到 `specs/`  
