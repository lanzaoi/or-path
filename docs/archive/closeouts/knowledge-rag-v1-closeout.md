# Knowledge / RAG v1 closeout（给 Pi 用）

> **状态：CLOSED — PASS**  
> **日期：** 2026-08-04  
> **计划：** `docs/archive/plans/2026-08-04_knowledge-rag-thicken.md`  
> **法条：** `specs/knowledge-and-retrieval.md` · `specs/memory.md` §4.5  

---

## 一句话

OR-Path 已具备 **给 Pi 的 hybrid 参考书库**：论文短笔记 + 白名单 skill/lesson 副本 → BM25/FTS/RRF → research 消费；**数字权威仍只在 solve+validate**。  
不是人用知识站，不是微调训练，不是 RAG Web UI。

---

## 对外三句话（就绪）

1. **给 Pi 的 hybrid 参考书**（runtime retrieval，不是 fine-tune）。  
2. **语料 = 论文/笔记 + 筛选战法/教训副本**（allowlist + lesson schema 过滤）。  
3. **optima 只来自 solve+validate**；RAG/skill/memory 不得冒充 L0 数字。

---

## Phase 完成表

| Phase | 名称 | 状态 | 主证据 |
|-------|------|------|--------|
| 1 | 书库可重建 | **PASS** | `knowledge-rebuild` / smoke |
| 2 | 语料加厚 | **PASS** | `knowledge/corpus/papers`×29 · `CORPUS.md` |
| 3 | Pi 必吃 retrieval | **PASS** | `phase3-hybrid-gate` · `notes/phase3-hybrid-*` |
| 4 | Skill/Lesson 规则 | **PASS** | allowlist · `knowledge-sync` · `phase4-knowledge-gate` |
| 5 | 验收关单 | **PASS** | `phase5-knowledge-gate` · 本文件 |

---

## 交付物清单

| 路径 | 作用 |
|------|------|
| `knowledge_svc/*` | hybrid 脊柱（T2 + 加厚） |
| `knowledge/corpus/` | papers + skills/lessons 副本 |
| `knowledge/export_allowlist.txt` | skill 入 RAG 白名单 |
| `knowledge/eval_queries.md` | 12 条固定查询 |
| `knowledge/CORPUS.md` | 索引 |
| `scripts/export_agent_knowledge_corpus.py` | 安全导出 |
| `scripts/knowledge_eval.py` | 查询烟雾 |
| `scripts/phase3_hybrid_pi_gate.py` | 产品 hybrid run |
| `scripts/phase4_knowledge_sync_gate.py` | sync 策略 |
| `scripts/phase5_knowledge_rag_gate.py` | 总门禁 |
| `orpath.bat` knowledge-* / phase*-gate | 入口 |
| `notes/phase3-hybrid-evidence.md` | Pi 吃书证据 |
| `notes/knowledge-eval-last.json` | eval 最近一次 |
| `notes/knowledge-rag-claim-ladder.json` | claim ladder |

---

## 命令（新人四步）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONPATH=
set PYTHONNOUSERSITE=1

orpath.bat knowledge-sync
orpath.bat knowledge-eval
orpath.bat phase3-hybrid-gate
orpath.bat phase5-knowledge-gate
```

产品 run 开 hybrid：

```bat
.venv-314\Scripts\python.exe orpath\run_t2.py --problem-id shortest_path --knowledge-mode hybrid --solve-mode mock --no-live-subagent --fresh --force --slug my-hybrid
```

---

## Claim ladder 自检

| 项 | 结论 |
|----|------|
| RAG 消费者 = Pi research | 是 |
| 禁止 fine-tune 话术 | 是 |
| optima 只 solve+validate | 是 |
| corpus 无 solution JSON | 是 |
| skill 运行时 = `.pi/skills` | 是 |
| RAG 副本 = `corpus/skills|lessons` | 是 |
| 无 RAG 网页 | 是 |
| Cognee 非主脑 | 是 |
| stub embed 可演示 | 是 |

---

## 边界（诚实）

| 有 | 没有 |
|----|------|
| 可重建索引 + hybrid 命中 | 公开 IR 基准 SOTA / MRR |
| 产品 mock hybrid 证据链 | LIVE 默认必开 hybrid |
| 策展短笔记 corpus | 全量学术 PDF 库 |
| allowlist skill 副本 | 自动把每次 run log 灌库 |
| stub 语义 | 强制硅基云 embed 才能绿 |

---

## 非目标（本 closeout 明确不做）

- RAG Web UI / 人用知识站  
- LlamaIndex / Cognee 替换主路径  
- M4 记忆史诗 / 自动 skill 量产  
- 宣称「用论文 fine-tune / 训练了模型」（**禁止**）

---

## 回归

```bat
orpath.bat phase5-knowledge-gate
```

期望：`PASS phase5_knowledge_rag_gate`
