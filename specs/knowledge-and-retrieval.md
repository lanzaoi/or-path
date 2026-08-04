# Knowledge and Retrieval — 知识与检索（详细）

**对齐：** `product-flow-sdd.md`  
**状态：** LAW 2026-08-01  
**边界：** 本文件 = **语料/检索**；题面 OCR = `problem-intake.md`（分离）

---

## 1. 管道总图

```text
docs/papers
  → MinerU Cloud 预处理（语料）
  → chunks (chunk_id)
       ├─ LightRAG / semantic stub
       └─ BM25 / FTS5
  → RRF 融合 → research 消费
  + 领域种子图 + Cognee（可选 smoke，非主记忆）
```

---

## 2. 模式

| knowledge_mode | 行为 |
|----------------|------|
| off | 无检索；research scale 可 off |
| seed | 种子图查询 |
| hybrid | semantic + lexical + RRF |

### 2.1 embed_mode（v2 Phase 2）

### 2.2 knowledge profile + incremental（v3 Phase 3）

| 变量 | 含义 |
|------|------|
| `ORPATH_KNOWLEDGE_PROFILE=demo\|research` | `research` 时 embed 默认 auto→live（有 key） |
| 增量 ingest | corpus 指纹未变则 skip；`--clear` 全量 |
| 制品 | `index_fingerprint` · `profile` 可出现在 retrieval JSON |

验证：`orpath.bat phase3-live-default-gate`。

### 2.1 embed_mode（v2 Phase 2）

| `ORPATH_KNOWLEDGE_EMBED` | 行为 |
|--------------------------|------|
| `auto`（默认） | 有 `SILICONFLOW_API_KEY` → **live** bge-m3；否则 **stub** |
| `live` | 真 embed；无 key 时降级 stub 并在 meta 标明 |
| `stub` | MockEmbedder / 哈希向量（CI 与无网） |

retrieval / ingest 制品字段：`embed_mode` · `embed_meta` · `semantic_mode`。  
验证：`orpath.bat phase2-embed-gate`。  
**无 key 不得宣称「真语义生产就绪」。**

Research **必须能读** retrieval 制品路径（mode≠off 时）。

---

## 3. Claim ladder（知识）

| 可 | 不可 |
|----|------|
| hybrid on preprocessed chunks | LightRAG 直接精通生 PDF 数学 |
| smoke 级 Cognee（旁路） | 生产级企业搜索 / Cognee 主记忆已完成 |
| 空 hits 保持 [] | 伪造 cite |

RRF 默认权重类：`w_semantic` / `w_lexical`（实现默认以代码为准，变更写本文件）。

---

## 4. 种子图（L4）

- ProblemClass – Constraint – Solver – Case  
- 数量门禁以 knowledge smoke / t2 为准  
- 边字段兼容 from/to 与 source/target  

---

## 5. MinerU

- **Cloud** 默认；本地重模型非默认  
- **仅语料**；竞赛题面主 OCR 不走 MinerU  

---

## 6. Embedding

- 硅基 `BAAI/bge-m3` @1024  
- 无 key 时允许 stub/cosine mock 以保 CI 形  

---

## 7. Cognee（旁路 smoke · 非主记忆）

- Cloud Free 额度 **smoke**；503 → LOCAL_FALLBACK 可接受  
- **禁止** objective dump 入库  
- **定位：** 作品集/实验级跨任务图；**不是**运筹长期记忆主轴  
- 运筹稳定战法 → **Skill / agent md / specs**（见 `memory.md` §0 §4）  
- 生产检索与领域结构 → **本文件 hybrid/seed + L4 种子图**，不以 Cognee 为唯一  
- V0+M0 前不新开 Cognee 生产化史诗；以后默认保持可选 smoke  

---

## 8. 制品路径

| | |
|--|--|
| retrieval | `notes/<slug>-retrieval.json` |
| research | `notes/<slug>-research.md` |
| 索引缓存 | gitignore 目录 |
| skill 白名单 | `knowledge/export_allowlist.txt` |
| skill/lesson RAG 副本 | `knowledge/corpus/skills/` · `knowledge/corpus/lessons/` |

### 8.1 Skill / Lesson → RAG（Phase 4）

- **命令：** `orpath.bat knowledge-sync`（= allowlist export + ingest --clear）  
- **Skill：** 仅 allowlist 中的 `.pi/skills/<name>`；超大文件跳过  
- **Lesson：** 仅 `orpath.lesson.v1`；拒绝 authoritative objective 字段  
- **硬边界：** RAG 副本 **≠** 运行时 skill 加载；数字权威仍 L0 solve+validate  

详见 `memory.md` §4.5。

---

## 9. M0 关系

M0 可用 `knowledge_mode=seed` 或 off；**不**以 hybrid 云调用为 M0 硬依赖。  
真 sub 证据优先于「检索很炫」。

---

## 10. 验证

```bat
.venv-314\Scripts\python.exe scripts\knowledge_smoke.py --step all
pytest knowledge_svc/test_knowledge_unit.py -q
orpath.bat phase3-hybrid-gate
orpath.bat phase4-knowledge-gate
```

---

## 11. 参考

`memory.md` · `multi-agent.md` research scale · T2 knowledge 实现笔记（archive）  
