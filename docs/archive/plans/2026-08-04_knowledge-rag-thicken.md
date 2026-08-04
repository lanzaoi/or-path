# OR-Path · RAG 五阶段完成计划（给 Pi 用）

> **状态：** **Phase 1–5 ALL DONE · CLOSED**（2026-08-04）  
> **关单：** `docs/archive/closeouts/knowledge-rag-v1-closeout.md`  
> **日期：** 2026-08-04  
> **消费方：** **Pi**（research 主 / model 辅）——不是人用知识站，不是微调训练  
> **技术脊柱：** 现有 `knowledge_svc`（不换 LlamaIndex / 不上 Cognee 主脑）  

---

## 目标（整包）

把「给 Pi 用的参考书库」做成可重建、可检索、**产品 run 真消费**、可安全灌 skill/lesson 的竖切，并关单。

**不是：** 人用知识站、微调、换新框架、RAG 网页。

---

## 五阶段总览

| 阶段 | 名称 | 核心交付 | 人日 | 状态 |
|------|------|----------|------|------|
| **1** | 书库可重建 | export / ingest / smoke / CLI | 0.5～1 | **DONE** |
| **2** | 语料加厚 | papers 主粮 | 1～2 | **DONE** |
| **3** | Pi 必吃 retrieval | 产品 hybrid 证据 | 1～1.5 | **DONE** |
| **4** | Skill/Lesson 入书规则 | allowlist + sync | 0.5～1 | **DONE** |
| **5** | 验收 · 文档 · 关单 | eval + closeout | 0.5～1 | **DONE** |

---

## 进度快照

| 阶段 | 状态 |
|------|------|
| **Phase 1** | **DONE** |
| **Phase 2** | **DONE**（papers×29） |
| **Phase 3** | **DONE**（`phase3-hybrid-sp`） |
| **Phase 4** | **DONE**（allowlist + knowledge-sync） |
| **Phase 5** | **DONE**（`phase5_knowledge_rag_gate` + closeout） |

---

## Phase 5 — 验收 · 文档 · 关单 · **DONE**

### 做

- [x] `knowledge/eval_queries.md` 12 问 + `scripts/knowledge_eval.py`
- [x] 一键：`knowledge-smoke` + eval + phase3/4 汇总于 `phase5_knowledge_rag_gate`
- [x] `ORPATH.md` · `docs/ARCHITECTURE.md` · specs 指针
- [x] `docs/archive/closeouts/knowledge-rag-v1-closeout.md`
- [x] claim ladder → `notes/knowledge-rag-claim-ladder.json`

### 验收

```bat
orpath.bat phase5-knowledge-gate
```

| 检查 | 标准 |
|------|------|
| Phase 1～4 | 门禁绿 |
| 新人四命令 | sync · eval · phase3 · phase5 |
| 产品 hybrid 证据 | `notes/phase3-hybrid-*` |
| 对外三句话 | closeout 就绪 |

### 命令速查

```bat
orpath.bat knowledge-sync
orpath.bat knowledge-eval
orpath.bat phase3-hybrid-gate
orpath.bat phase5-knowledge-gate
```

---

## 跨阶段硬约束

| 规则 | |
|------|--|
| 框架 | 只加厚 `knowledge_svc` |
| UI | **无** RAG 网页 |
| 训练 | **禁止**对外说 fine-tune |
| 数字 | solution/validate **不进** corpus 权威 |
| Cognee | 旁路 smoke only |
| 默认产品 | Demo 可用 seed；**加强档** hybrid |

---

## 决策记录

| 问题 | 决定 |
|------|------|
| 几个阶段 | **5** |
| 给谁用 | **Pi** |
| 网页 | 不做 |
| 完成标志 | Phase 5 closeout + gate PASS |
| 与七月 T2 | 同一脊柱；本计划 = **加厚到可宣布 RAG v1** |
