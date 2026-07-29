# Feynman 工作流深度研究 → OR-Path 1.0 急需补齐清单

**日期：** 2026-07-29  
**范围：** `vendor/feynman`（本地 vendored 源）vs OR-Path 现有论文环/知识环  
**目的：** 找出 Feynman **大优势**且 OR-Path **1.0 原型急需**的能力（尤其论文撰写与打回、知识处理）。  
**不是：** 把 OR-Path 做成第二个通用科研 CLI；OR 数字真相/求解门禁仍是我们的主轴。

---

## 0. 一句话对照

| | **Feynman** | **OR-Path 今天** |
|--|-------------|------------------|
| 产品定位 | AI **researcher**：发现→读→证→综合→可审计文稿 | AI **OR 求解工作台**：NL→模型→**求解/校验**→薄论文环 |
| 论文环 | **工作流一等公民**（`/draft` `/review` `/deepresearch` `/lit`） | 图上有节点，但大量是 **确定性 stand-in + 脚本门** |
| 打回 | FATAL→修→**再审**；磁盘校验补丁真落地 | revise≤2 有，但是 **薄**；少「修完再 verify on-disk」 |
| 知识 | 外网+alphaXiv+HF+**读后才写**；证据表强制 URL | 本地 seed/hybrid/RRF **竖切有**；缺 Feynman 级 **检索-读-证据表-coverage** 纪律 |
| 最大优势 | **可执行协议 + 诚实 provenance** | **数字不能瞎编（solve+validate+R2）** |

**学什么：** Feynman 的「协议厚度」与「证据-写作-打回闭环」。  
**不学什么：** 把它的生命科学/算力/通用 deep research 产品面整包搬进来压垮 OR 主轴。

---

## 1. Feynman 论文/知识工作流（从源码还原）

### 1.1 角色（`.feynman/agents/`）

| Agent | 核心契约 |
|-------|----------|
| **researcher** | 只采证；**URL or it didn't happen**；evidence table；Coverage Status；禁止未读先总结 |
| **writer** | **只根据已有 research 文件写**；不写 Sources/inline cite（留给 verifier）；claim sweep + result-provenance sweep |
| **verifier** | 锚定引用、**活链检查**、删无源声明、**Result provenance audit**（数字/表/图必须有来源） |
| **reviewer** | FATAL/MAJOR/MINOR + **Inline Annotations 逐段引用** + Revision Plan；可切换 adversarial auditor 模式 |

OR-Path 有 `or-*` 六个角色，**提示词已对齐 claim ladder**，但 **默认 LG 节点并未真正跑完整 Feynman 式多阶段**（B 题 demo 是手工 `run_pi_stage`）。

### 1.2 命令级协议（真正的护城河）

| 命令 | 强制磁盘产物 | 打回逻辑 |
|------|--------------|----------|
| **`/deepresearch`** | plan → drafts → cited → final + **provenance** | 计划可先确认；FATAL 修后再审；**edit 失败不许宣称已修**；`rg` 验旧词消失 |
| **`/draft`** | plan 大纲 → writer → verifier → `papers/<slug>.md` | 写前 claim/figure 清单 |
| **`/review`** | review-plan + review-evidence + final review | 解不出 PDF 也要 **BLOCKED review 落盘** |
| **`/lit`** | researcher → verifier → reviewer → outputs + provenance | 文献轨迹/corpus 专门模式 |

共性纪律（`AGENTS.md` + deepresearch 尾部）：

1. **Slug 前缀**，禁止 `research.md` 撞车  
2. **Plan = 外置工作记忆**（task ledger + verification log + decision log）  
3. **CHANGELOG.md lab notebook**（长跑续跑）  
4. **Provenance sidecar 强制**（sources consulted/accepted/rejected + Verification PASS|NOTES|BLOCKED）  
5. **file handoff**，子代理不把全文灌回 parent  
6. **Scale 决策**：窄问题禁止滥 spawn 子代理  
7. **Verifier 与 Reviewer 禁止并行**（先 cite 再审）  
8. **修完必须 on-disk 二次验证**  

### 1.3 知识处理优势（相对 OR-Path）

| 能力 | Feynman | OR-Path |
|------|---------|---------|
| 外网/论文发现 | web_search + alphaXiv 工具链 | 主要本地 corpus；在线 R1 分轨 |
| 「先读后写」 | researcher 硬法 | research 节点常 stand-in |
| 证据表 | `# \| Source \| URL \| claim \| type \| conf` | 有结构，但不强制 URL/覆盖率 |
| Coverage Status | 查了什么/不确定什么 | 弱 |
| 死链/假文献 | verifier 拉 URL，死则删 claim | R1 多是 **whitelist 字符串**，不验「源是否支撑句意」 |
| 语义支撑 | 「citation 主题沾边不够，必须支撑具体数字/结论」 | R2 管数字⊆solution；**不管叙事是否被文献支撑** |
| 图表 provenance | 无 artifact 则 TODO，禁止装饰图 | 基本无 figure 协议 |
| 知识入库 | 偏实时检索综合 | MinerU→chunk→LightRAG/BM25/RRF **管道更工程**（这是我们优势） |

**判断：**  
- **入库/混合检索管道**：OR-Path 不落后，甚至更「产品化」。  
- **检索结果如何变成不可造假的研究笔记与论文**：**Feynman 明显更厚**——这是 1.0 要补的。

### 1.4 论文撰写与打回优势

| 环节 | Feynman | OR-Path 现状 |
|------|---------|--------------|
| 写前大纲 | `/draft` 强制 plan：章节、关键 claims、verification log | 少 |
| 叙事弧 | `paper-narrative` skill：claim→证据链→图序 | 无 |
| 草稿分层 | `.drafts/<slug>-draft.md` → cited → revised | 常直接 `papers/<slug>.md` |
| 引用阶段 | **独立 verifier 阶段**，可活检 | R1 白名单脚本 + 可选 LLM verifier |
| 对抗审 | inline 逐句批注 + Revision Plan | review_pack 偏 **R1/R2 脚本 FATAL 列表** |
| 打回执行 | FATAL 修 → **再 review**；大改写整文件 | `revise_count≤2` 路由有，**缺「修完证明」协议** |
| 交付门槛 | 缺文件不许宣称完成 | LG 绿即可，文稿质量不设 Feynman 级门槛 |
| 诚实标签 | verified/unverified/blocked/inferred | 有 human_required，缺细粒度证据标签 |

---

## 2. OR-Path 已有、不必推倒重来

这些是 **我们的优势**，1.0 应保留并让 Feynman 式文稿环 **挂在上面**：

1. **数字真相**：solve_* + validate + R2（objective/tour/routes ⊆ solution）  
2. **Schema 门**：modeler 禁止最优值  
3. **LG 产品骨架**：checkpoint / resume / dirty hash / stage map  
4. **知识入库竖切**：MinerU Cloud、chunk_id、RRF、seed graph  
5. **OR 专用 claim ladder**：精确轨 vs 启发式轨  

Feynman **没有** OR 求解门禁；它不会替你证 polyomino=33。  
1.0 = **OR 硬核 + Feynman 文稿/证据协议**，不是二选一。

---

## 3. 差距优先级（1.0 急需）

### P0 — 没有就不配叫「论文工作流 1.0」

| ID | 缺口 | 状态（2026-07-29 厚做） |
|----|------|------------------------|
| **P0-1** | Paper 阶段机 draft→cite→review→revise | **DONE** 图节点 `cite_pack`；15 节点 PRODUCT |
| **P0-2** | claim 映射语义/可追溯 | **DONE** `tools/r1_claim_map.py` |
| **P0-3** | FATAL→修→再门禁→磁盘证明 | **DONE** `revise-proof.md` + re-cite |
| **P0-4** | provenance 模板 | **DONE** PASS/BLOCKED + gate_claim_ok |
| **P0-5** | research 证据硬门 | **DONE** gate_research（P1 已接） |

验收：`orpath.bat paper-gate` → `P0_PAPER_GATE_PASS`；`t3_lg_gate` PASS。

**2026-07-29 源码深复验：** 见 `docs/feynman-p0p1-deep-reverify.md`。  
补：`orpath/claim_ledger.py`（Claim: 标记 + claimId + checks 合并）、`*-verification.md`、final candidate 提升。

### P1 — 1.0 强烈建议（作品集/可用感）

| ID | 缺口 | 建议 |
|----|------|------|
| **P1-1** | **Paper narrative / 章节模板** | 移植精简 `paper-narrative`：OR 论文固定弧（问题→模型→精确结果→validate→局限）；数模/作品集两种模板 |
| **P1-2** | **Reviewer inline annotations** | 现在 review 多为门列表；补「引用原文段落」批注（Feynman Part 2） |
| **P1-3** | **Plan ledger 真驱动** | `outputs/.plans/<slug>.md` 在 LG 每阶段 append verification log（非一次性） |
| **P1-4** | **知识：retrieve → research 强制消费** | specs 已写；实现上 hybrid 时 research stand-in 仍可能不读 retrieval.json → **硬 assert 引用 chunk_id** |
| **P1-5** | **Draft 分层目录** | `outputs/.drafts/<slug>-{draft,cited,revised}.md` 与 Feynman 对齐，避免直接覆盖 papers/ |
| **P1-6** | **命令入口** | `orpath.bat paper --slug ...` / `orpath.bat lit-or ...` 对标 `/draft` `/review`（不必抄 slash UX） |

### P2 — 产品/连续性加深（已做 1.0 子集）

| ID | 项 | 状态 |
|----|-----|------|
| P2-A | artifact 版本链 sha256+parent | **DONE** `orpath/artifact_versions.py` |
| P2-C | ResearchRun 迷你 manifest | **DONE** `orpath/research_run.py` |
| P2-D | annotations-lite | **DONE** `orpath/annotations_lite.py` |
| P2-E | lab CHANGELOG | **DONE** `outputs/.lab/CHANGELOG.md` |
| P2-F | solution figure (mermaid) | **DONE** |
| P2-1..5 原「可后置」alphaXiv/UI/HF | 仍后置 | 见 `docs/paper-1.0-closeout.md` |

### P3 — 1.0 收口

| ID | 项 | 状态 |
|----|-----|------|
| P3-1 | `paper_1_0_gate` 统一门 | **DONE** |
| P3-2 | provenance 声明 P0+P1+P2+P3 | **DONE** |
| P3-3 | closeout 文档 | **DONE** `docs/paper-1.0-closeout.md` |

```bat
orpath.bat paper-1.0-gate
```

---

## 4. 「论文」专项：Feynman 大优势拆解

结合你们 **网页 DS 数模论文 vs 精确解** 的教训：

| 失败模式 | Feynman 如何挡 | OR-Path 1.0 应对 |
|----------|----------------|------------------|
| 假证明（Q1.2 染色） | reviewer adversarial + verifier 要源 | **R_logic？** 或 reviewer 清单强制「证明步骤↔solver/枚举产物」；无 solver 支持的证明不得 FATAL 放行 |
| 假文献 | URL fetch + 无 URL 不写 | research gate + R1；**禁止**无 whitelist 的「张三 2023」 |
| 面积不可能（31 块盖 132） | result provenance + 数字审计 | **已有 R2**；扩展：块数×max_size ≥ cells 的结构检查（OR 文可加 `r2_or_structure`） |
| 次优当最优 | N/A（Feynman 不求解） | **已有 exact meta**；writer 必须读 `proven_optimal` |
| 一次成文无打回 | draft→cite→review→fix 循环 | **P0-1/P0-3** |
| 装饰性图表 | 无数据不制图 | 同左 |

**结论：** 论文 1.0 的急缺不是「更会写」，而是 **Feynman 式：分层草稿 + 引用审计 + 对抗打回 + 落盘 provenance**，再叠我们的 **R2/精确求解**。

---

## 5. 「知识处理」专项

### Feynman 强在「知识消费协议」

```text
search → fetch/read → evidence table → findings[n] → coverage
         → writer only from files
         → verifier anchors + live URL
         → reviewer kills zombies
```

### OR-Path 强在「知识供给管道」

```text
PDF → MinerU → chunks → LightRAG + BM25/FTS → RRF → retrieval.json
(+ seed graph, Cognee smoke)
```

### 1.0 融合形态（推荐）

```text
[供给] 现有 hybrid retrieve（保持）
    ↓
[消费-P0] gate_research：必须引用 chunk_id/seed_id；Coverage Status
    ↓
[写作-P0] drafts: draft → cited(R1+语义表) → review → revised
    ↓
[数字-已有] R2 + solution/validate 绑定
    ↓
[交付-P0] papers/<slug>.md + provenance
```

**不要**为了学 Feynman 重写 LightRAG；**要**学它怎么防止「检索了等于读了、写了等于证了」。

---

## 6. 建议的 1.0 DoD（论文+知识切片）

可写进 `specs/gates-and-dod.md` 的候选：

1. **任意 fixture 题（如 tsp_n8）**：  
   `retrieve(hybrid|seed) → research(gate 绿) → model → solve(exact|ortools) → validate →`  
   `draft → cite → R1+R2 → review(inline) → revise? → provenance`  
   全部路径落盘，**无 HUMAN_REQUIRED**（或明确 blocked 原因）。  
2. **research.md** 含 ≥N 行 evidence（本地 path 可代替 URL）+ Coverage Status。  
3. **FATAL 注入测试**：文中写入 whitelist 外 URL 或 solution 外 objective → R1/R2 红 → revise 去掉 → 再绿。  
4. **provenance** 含：solver status/exact flags、R1/R2 exit、sources accepted/rejected。  
5. **与 Feynman 对齐的目录**：`.plans/` `.drafts/` `papers/` `notes/`。  
6. **不要求**：alphaXiv、figure-composer、用户确认门、顶会级文笔。

---

## 7. 实施切片建议（别一次吞完）

| 切片 | 内容 | 预估 |
|------|------|------|
| **S1** | 目录约定 + provenance 模板 + plan ledger 写入 LG 钩子 | 小 |
| **S2** | `gate_research.py` + research 模板；hybrid 强制读 retrieval | 中 |
| **S3** | paper 子图：draft→cited→review_pack→revise（再跑 R1/R2） | 中大 |
| **S4** | reviewer inline + revision plan 真正驱动 revise 提示 | 中 |
| **S5** | `orpath paper` CLI + 一门 `t1_paper_gate`/`paper_gate` | 中 |
| **S6** | （可选）paper-narrative OR 模板 + 数模模板 | 小 |

**今天深度研究停在规格级；实现从 S1–S3 开 1.0。**

---

## 8. 反模式（学歪）

1. 把 Feynman 的 `/deepresearch` 用户确认搬进来卡死自动化 gate。  
2. 用 LLM reviewer **替代** R2（数字门必须仍是代码）。  
3. 为了「像论文」关闭 exact claim ladder。  
4. 并行 verifier+reviewer 抢同一 draft。  
5. 宣称「已对标 Feynman」但只有提示词、没有强制落盘协议。

---

## 9. 总结：大优势 & 急需

### Feynman 真正值得学的大优势

1. **可执行的多阶段文稿协议**（draft/cite/review/fix/deliver）  
2. **证据与写作分离**（researcher 不写最终腔；writer 不编源）  
3. **Verifier 的结果溯源审计**（比纯白名单狠）  
4. **Reviewer 的 inline 打回 + 再验证**  
5. **Provenance / BLOCKED 诚实学**  
6. **Plan 外置记忆 + slug 产物纪律**

### OR-Path 1.0 最急需补的（排序）

1. Paper **cite→review→fix→re-gate** 真闭环（P0-1, P0-3）  
2. Research **证据表 + coverage gate**（P0-5）  
3. **Provenance 强制**（P0-4）  
4. Verifier **超越 whitelist 的 claim↔source 映射**（P0-2）  
5. 知识 **retrieve 强制被 research 消费**（P1-4）  
6. 叙事模板（P1-1）— 有了 1–5 再补皮  

### 一句话

> **Feynman 教「怎么把知识写成不可抵赖的稿并打回」；OR-Path 已经会「怎么把 OR 数字算对」。1.0 = 两套协议焊死在同一张 LG 图上。**

---

## 10. 源码锚点（便于开工）

| 主题 | 路径 |
|------|------|
| 角色 | `vendor/feynman/.feynman/agents/{researcher,writer,verifier,reviewer}.md` |
| deepresearch 全协议 | `vendor/feynman/prompts/deepresearch.md` |
| draft/review/lit | `vendor/feynman/prompts/{draft,review,lit}.md` |
| 仓库法 | `vendor/feynman/AGENTS.md` |
| OR 论文法 | `specs/paper-and-review.md` |
| OR 知识法 | `specs/knowledge-and-retrieval.md` |
| OR 门 | `tools/r1_cite_check.py`, `tools/r2_numeric_check.py` |
| OR 图 | `orpath/graph_product.py` draft→review→revise |
