# OR-Path `specs/` — 规范索引（SDD 全册）

**地位：** 本目录是产品与工程的 **硬法（living law）**。  
**索引更新：** 2026-08-09（+ human-steer / Pi 引导插件规格）

---

## 1. 冲突优先级

```text
1. 可运行代码 + 门禁真实输出
2. specs/product-flow-sdd.md     ← 总流程 · Demo M0
3. specs/process-visibility.md   ← 过程 / sub 可视化
4. specs/** 其它分册
5. AGENTS.md
6. docs/archive/plans/*（历史；可过期）
7. docs/**（活文档 + archive）
8. 聊天记录
```

Hermes MEMORY **不是**产品法。`.hermes/` 本机-only → `docs/repo-surface.md`。

---

## 2. 文件地图

| 文件 | 主题 | 何时必读 |
|------|------|----------|
| **`product-flow-sdd.md`** | ★ 总流程主合同 | **任何实现前** |
| **`process-visibility.md`** | ★ 实时过程台硬底线 | **宣称「能看见」前** |
| `product-scope.md` | 范围、claim ladder、里程碑 | 改范围/话术前 |
| `architecture.md` | LG/Pi 分层、双路径、**启动/OCR 默认** | 改拓扑/入口前 |
| `control-plane.md` | 阶段图、回修、字段 owner | 改图/边前 |
| `multi-agent.md` | 真 MA、harness | 改 subagent 前 |
| `solvers-and-validate.md` | 求解轨、validate、**CVRPTW 叶** | 改求解前 |
| `paper-and-review.md` | 论文环、R1/R2、claim_map | 改论文前 |
| `problem-intake.md` | 1.1 OCR/审读/禁键 | 改读题前 |
| `memory.md` | L0–L1；Skill 战法；禁权威 optima | 改记忆前 |
| `knowledge-and-retrieval.md` | MinerU / hybrid / RAG 给 Pi | 改知识前 |
| `contracts.md` | JSON 契约 | 改 schema/solution 前 |
| `gates-and-dod.md` | 历史 DoD + 回归命令 | 关单前 |
| `t3-lg-skeleton.md` | 产品图骨架 freeze | 改 checkpointer 前 |
| `1.2-architecture-soak.md` | soak 与 BLOCKED 诚实 | 真题无 adapter 前 |
| **`engineering-hygiene.md`** | 编码 + Git + AI 卫生 | 写代码/提交前 |
| **`human-steer-and-pi-guidance.md`** | Watch 对话层 · LG/Pi 人导分流 · Pi 社区引导插件 | 做人导/对话框/装 Pi 插件前 |

**已合并删除（2026-08-04）：**  
`coding-conventions.md` · `git-and-ai-hygiene.md` → `engineering-hygiene.md`  
`openpi-boot-ma-ocr.md` → `architecture.md` §10  
`t3-vrp-tw.md` → `solvers-and-validate.md` §11  

---

## 3. 阅读顺序（新人 / 新会话）

```text
0. product-flow-sdd.md
1. process-visibility.md
2. architecture.md
3. control-plane.md · multi-agent.md
4. solvers-and-validate.md · paper-and-review.md
5. problem-intake.md · contracts.md
6. memory.md · knowledge-and-retrieval.md
7. product-scope.md · gates-and-dod.md
8. engineering-hygiene.md
9. human-steer-and-pi-guidance.md（人导/Pi 插件）
10. t3-lg-skeleton / 1.2-soak（按需）
```

---

## 4. 与其它层

| 层 | 路径 |
|----|------|
| Specs | `specs/` |
| Plans | `docs/archive/plans/` |
| Docs | `docs/` · 架构 `docs/ARCHITECTURE.md` |
| Code | `orpath/` `tools/` `knowledge_svc/` `scripts/` |

---

## 5. 维护

- 小行为：改对应分册  
- 大重冻：先 `product-flow-sdd.md`  
- skill **禁止**复制大段法条；只指针到本目录  
