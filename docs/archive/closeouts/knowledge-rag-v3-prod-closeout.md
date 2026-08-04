# Knowledge / RAG v3 prod closeout（给 Pi 用 · 真 PDF / live 研究档）

> **状态：CLOSED — PASS**  
> **日期：** 2026-08-04  
> **计划：** `docs/archive/plans/2026-08-04_knowledge-rag-v3-prod.md`  
> **承接：** v1 `knowledge-rag-v1-closeout.md` · v2 `knowledge-rag-v2-thick-closeout.md`  
> **法条：** `specs/knowledge-and-retrieval.md` · `specs/memory.md` §4.5  

---

## 一句话

OR-Path 厚栈 v3 已具备：**真 PDF 预处理管线（云 MinerU 硬化）→ 真文献 shortlist 主粮 → research 档默认 live embed + 增量 ingest → 产品 slug `thick-research-sp` 吃真主粮**；**optima 仍只信 solve+validate**。  
不是人用知识站、不是 fine-tune、不是全量学术 PDF 库。

---

## 对外三句话（就绪）

1. **真 PDF/文献可进 Pi 书库**（`inbox_pdf` 预处理 或 shortlist md / `lit`·`lit_abs`）。  
2. **研究档 hybrid 优先 live 语义**（有硅基 key）+ BM25/FTS + RRF；增量 ingest 指纹跳过。  
3. **数字仍只来自 solve+validate**；RAG 不得冒充 L0 权威。

---

## Phase 完成表（v3）

| Phase | 名称 | 状态 | 主证据 |
|-------|------|------|--------|
| 1 | 云 MinerU 真 PDF 硬化 | **PASS** | `phase1-mineru-cloud-gate` · submit/upload/poll DONE（CDN zip 可 SKIP） |
| 2 | 真文献主粮流水线 | **PASS** | `phase2-real-corpus-gate` · lit shortlist · title/source |
| 3 | live 研究默认 + 增量 | **PASS** | `phase3-live-default-gate` · fingerprint skip · profile=research |
| 4 | 产品研究档体验 | **PASS** | `product-research-gate` · slug `thick-research-sp` |
| 5 | 验收关单 | **PASS** | `phase5-v3-gate` · **本文件** |

---

## 完成度表（对照七月最厚 · 诚实）

| 厚栈块 | v2 关单 | **v3 关单** | 说明 |
|--------|---------|-------------|------|
| MinerU 闭环 | ~85% | **~90–92%** | 云 submit→upload→poll 通；CDN zip 本环境 SSL 可降级 |
| chunk/BM25/FTS/RRF | ~95% | **~95%** | 稳；FTS clear 改为 DELETE 防 Win 锁 |
| 真语义 | ~75–80% | **~85%** | research+auto→live；全库 live 重嵌非默认门禁 |
| 规模主粮 | ~75% | **~85%** | shortlist lit + lit_abs；真 PDF 预处理条数仍可加 |
| research 消费 | ~90% | **~93%** | thick-research-sp 引用 lit_abs |
| **整条最厚目标** | ~80–85% | **~88–92%** | 诚实上限；无全网爬取 / 无完整 LightRAG 图引擎 |

---

## 文档放哪（新人）

| 内容 | 路径 |
|------|------|
| md 主粮 | `knowledge/corpus/papers/` |
| 文献 shortlist 笔记 | `knowledge/corpus/papers/lit/` · `lit_abs/` |
| PDF | `knowledge/inbox_pdf/` → `knowledge-preprocess` |
| 预处理产出 | `knowledge/corpus/papers/_from_mineru/` |
| skill 白名单 | `knowledge/export_allowlist.txt` + `knowledge-sync` |
| lesson | `knowledge/lessons/*.json`（`orpath.lesson.v1`） |

---

## 命令（v3 厚路径）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONPATH=
set PYTHONNOUSERSITE=1

:: 上游 PDF
orpath.bat knowledge-preprocess
orpath.bat phase1-mineru-cloud-gate

:: 文献 shortlist
orpath.bat knowledge-lit-materialize
orpath.bat phase2-real-corpus-gate

:: 研究档
set ORPATH_KNOWLEDGE_PROFILE=research
set ORPATH_KNOWLEDGE_EMBED=auto
orpath.bat knowledge-sync
orpath.bat phase3-live-default-gate
orpath.bat product-research-gate

:: 总门禁
orpath.bat phase5-v3-gate
```

---

## Claim ladder 自检

| 项 | 结论 |
|----|------|
| 消费者 = Pi research | 是 |
| 禁止 fine-tune 话术 | 是 |
| optima = solve+validate | 是 |
| PDF 须预处理 | 是 |
| embed_mode 诚实 | 是 |
| profile research→live | 有 key 时是 |
| 无 RAG 网页 | 是 |
| Cognee 非主脑 | 是 |

---

## 边界（诚实）

| 有 | 没有 |
|----|------|
| 云 MinerU 任务闭环 + offline 回落 | 本环境保证 CDN zip 必下 |
| shortlist 书目/摘要笔记 | 全量付费 PDF 镜像 |
| research 默认 live 查询 embed | 默认对 1 万+ chunk 全量 live 重嵌 |
| 产品 slug thick-research-sp | LIVE 默认全开 hybrid |
| 增量指纹 skip | 换机器指纹自动迁移云端 |

---

## 非目标（本 closeout）

- RAG Web UI / 人用知识站  
- LlamaIndex / Cognee 替换主路径  
- M3 launch / M4 记忆史诗  
- 宣称「用论文 fine-tune / 训练了模型」

---

## 回归

```bat
orpath.bat phase5-v3-gate
```

期望：`PASS phase5_v3_knowledge_gate`
