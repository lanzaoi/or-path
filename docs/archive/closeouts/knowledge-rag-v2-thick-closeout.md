# Knowledge / RAG v2 thick closeout（给 Pi 用 · 最厚目标收口）

> **状态：CLOSED — PASS**  
> **日期：** 2026-08-04  
> **计划：** `docs/archive/plans/2026-08-04_knowledge-rag-v2-thick.md`  
> **承接 v1：** `docs/archive/closeouts/knowledge-rag-v1-closeout.md`  
> **法条：** `specs/knowledge-and-retrieval.md` · `specs/memory.md` §4.5  

---

## 一句话

OR-Path 厚栈已具备：**PDF/文本预处理 → chunk → LightRAG 语义(live/stub) ∥ BM25/FTS → RRF → research 消费**，规模主粮 + 产品 hybrid 证据齐全；**optima 仍只信 solve+validate**。  
不是人用知识站、不是 fine-tune、不是完整企业图数据库。

---

## 对外三句话（就绪）

1. **PDF/文本经预处理进 Pi 参考书库**（`inbox_pdf` → `knowledge-preprocess` → `corpus/papers`）。  
2. **hybrid = 真语义（有硅基 key 则 live bge-m3，否则 stub）+ BM25/FTS + RRF**。  
3. **数字仍只来自 solve+validate**；RAG 不得冒充 L0 权威。

---

## Phase 完成表（v2）

| Phase | 名称 | 状态 | 主证据 |
|-------|------|------|--------|
| 1 | MinerU 预处理闭环 | **PASS** | `phase1-mineru-gate` · `notes/mineru-last.json` |
| 2 | 真语义 embed | **PASS** | `phase2-embed-gate` · `embed_mode` live/stub |
| 3 | 规模主粮 | **PASS** | papers≥40 · `_from_mineru`≥10 · `phase3-scale-gate` |
| 4 | 产品厚路径 | **PASS** | `thick-hybrid-gate` · slug `thick-hybrid-sp` |
| 5 | 验收关单 | **PASS** | `phase5-thick-gate` · **本文件** |

---

## 完成度表（对照七月最厚 · 诚实）

| 厚栈块 | 关单估计 | 说明 |
|--------|----------|------|
| MinerU 闭环 | **~85%** | 产品命令+offline/sidecar 硬绿；云 API 仍 best-effort |
| chunk / BM25 / FTS / RRF | **~95%** | 稳定 |
| LightRAG 真语义 | **~75–80%** | live=bge-m3 文件向量；非完整 LightRAG 图运行时 |
| 规模主粮 | **~75%** | papers 63 + mineru 形态 12；非全量学术 PDF 库 |
| research 消费 | **~90%** | thick-hybrid 引用 papers/_from_mineru |
| **整条最厚目标** | **~80–85%** | 可达关单上限；余量在云 MinerU 硬化与真 PDF 规模 |

---

## 文档放哪（新人）

| 内容 | 路径 |
|------|------|
| md/txt 主粮 | `knowledge/corpus/papers/` |
| PDF | `knowledge/inbox_pdf/` → `orpath.bat knowledge-preprocess` |
| 预处理产出 | `knowledge/corpus/papers/_from_mineru/` |
| skill 白名单 | `knowledge/export_allowlist.txt` + `knowledge-sync` |
| lesson | `knowledge/lessons/*.json`（`orpath.lesson.v1`） |

---

## 命令（厚路径）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONPATH=
set PYTHONNOUSERSITE=1

orpath.bat knowledge-preprocess
orpath.bat knowledge-sync
orpath.bat knowledge-eval
orpath.bat phase1-mineru-gate
orpath.bat phase2-embed-gate
orpath.bat phase3-scale-gate
orpath.bat thick-hybrid-gate
orpath.bat phase5-thick-gate
```

真 embed：

```bat
set ORPATH_KNOWLEDGE_EMBED=live
orpath.bat knowledge-sync
orpath.bat phase2-embed-gate
```

---

## 交付物清单（v2 增量）

| 路径 | 作用 |
|------|------|
| `knowledge_svc/mineru_client.py` | PDF→md→corpus |
| `knowledge/inbox_pdf/` | PDF 投放 |
| `ORPATH_KNOWLEDGE_EMBED` | live/stub/auto |
| `scripts/phase1_mineru_gate.py` … `phase4_thick_hybrid_gate.py` | 分阶段门禁 |
| `scripts/phase5_thick_knowledge_gate.py` | 总门禁 |
| `notes/thick-hybrid-evidence.md` | 产品厚证据 |
| `notes/phase5-thick-evidence.md` | 本关单证据板 |
| `notes/knowledge-rag-v2-claim-ladder.json` | claim ladder |

---

## Claim ladder 自检

| 项 | 结论 |
|----|------|
| 消费者 = Pi research | 是 |
| 禁止 fine-tune 话术 | 是 |
| optima = solve+validate | 是 |
| PDF 须预处理 | 是 |
| embed_mode 诚实 | 是 |
| 无 RAG 网页 | 是 |
| Cognee 非主脑 | 是 |

---

## 边界（诚实）

| 有 | 没有 |
|----|------|
| 预处理产品命令 + fixture 门禁 | 本地 GPU MinerU 重部署 |
| live bge-m3（有 key） | 完整 LightRAG 图+LLM 工作区默认开箱 |
| 规模策展 + mineru 形态 md | 全网论文爬取 / BEIR SOTA |
| 产品 hybrid 厚证据 | LIVE 默认必开 hybrid |
| stub 可 CI | 无 key 却宣称真语义生产就绪 |

---

## 非目标（本 closeout）

- RAG Web UI / 人用知识站  
- LlamaIndex / Cognee 替换主路径  
- M4 记忆史诗  
- 宣称「用论文 fine-tune / 训练了模型」

---

## 回归

```bat
orpath.bat phase5-thick-gate
```

期望：`PASS phase5_thick_knowledge_gate`
