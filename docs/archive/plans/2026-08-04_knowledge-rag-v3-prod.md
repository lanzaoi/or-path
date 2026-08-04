# OR-Path · 知识厚栈 v3 五阶段计划  
# 真 PDF 生产力 · 云 MinerU 硬化 · live 默认研究档 · 产品体验

> **状态：** **Phase 1–5 ALL DONE · CLOSED**  
> **日期：** 2026-08-04  
> **承接：**  
> - v1 关单 `docs/archive/closeouts/knowledge-rag-v1-closeout.md`  
> - v2 关单 `docs/archive/closeouts/knowledge-rag-v2-thick-closeout.md`（**CLOSED ~80–85%**）  
> **消费方：** 仍是 **Pi research**（非人用站、非 fine-tune）  
> **关单名（预告）：** `docs/archive/closeouts/knowledge-rag-v3-prod-closeout.md`

---

## 0. 为什么还要 v3

v2 已证明管子通：

```text
inbox_pdf → preprocess → corpus → hybrid(live|stub) → research → validate
```

v2 **诚实缺口**（关单表）：

| 缺口 | v2 状态 | v3 要推到 |
|------|---------|-----------|
| 云 MinerU | best-effort / 门禁靠 offline fixture | **真 PDF 云抽一次有 manifest 证据** |
| 语料 | 策展 md + mineru 形态种子 | **真文献/真 PDF 主粮可重复进库** |
| live embed | 能绿；研究档未默认 | **有 key 时研究 hybrid 默认 live** |
| 产品体验 | gate slug 演示 | **CASE/研究路径可复现厚证据，非仅 CI** |
| claim/paper | 语料厚后 claim_map 曾抖 | **厚 corpus 下 paper 路径不红死数字链** |

**不做：** RAG Web UI、换 LlamaIndex、Cognee 主脑、M4 记忆史诗、宣称 fine-tune。

**产品优先级提醒（AGENTS）：** V0/M0 仍高于新史诗；本 v3 是 **旁路可演示的知识生产力加厚**，不挡 Watch 主脸。

---

## 1. 目标完成度（相对七月最厚）

| 厚栈块 | v2 关单 | v3 目标 |
|--------|---------|---------|
| MinerU 闭环 | ~85% | **≥92%**（有 token 真云绿；无 token 仍 fixture） |
| chunk/BM25/FTS/RRF | ~95% | 保持 |
| 真语义 | ~75–80% | **≥85%**（live 默认研究档 + 增量） |
| 规模主粮 | ~75% | **≥85%**（真源 PDF/论文条目，不只种子） |
| research 消费 | ~90% | **≥93%**（默认路径 + claim 稳） |
| **整条** | **~80–85%** | **~88–93%**（诚实上限；无全网爬取） |

---

## 2. 五阶段总览

| 阶段 | 名称 | 人日（估） | 依赖 |
|------|------|------------|------|
| **1** | **云 MinerU 真 PDF 硬化** | 1–2 | `MINERU_API_TOKEN` 可选；无 token → SKIP 云硬测 |
| **2** | **真文献主粮流水线** | 1–2 | 可平行 1 的后半 |
| **3** | **live embed 研究默认 + 增量 ingest** | 1 | 2 有一批真 md |
| **4** | **产品厚体验（CASE/hybrid 默认研究档）** | 1–2 | 3 |
| **5** | **验收 · 菜谱 · v3 关单** | 0.5–1 | 1–4 |

合计约 **5–8 人日**。

---

## Phase 1 — 云 MinerU 真 PDF 硬化 · **DONE**

**目标：** 门禁不再只靠 offline fixture；**有 token 时** 至少 1 份真 PDF 走云 → md → `_from_mineru` → ingest 可检索。

### 做

- [ ] `mineru_client`：云 submit/poll **超时、重试、错误码进 manifest**（不落 token）
- [ ] 小体积 **真实 PDF 夹具**（自备 1–3 页 OR 讲义或公开 note；**不**提交竞赛原卷）
  - 路径建议：`knowledge/inbox_pdf/fixtures/or_sample_*.pdf`（gitignore 大文件策略写清）
- [ ] 命令：
  ```bat
  orpath.bat knowledge-mineru --pdf knowledge\inbox_pdf\fixtures\or_sample_01.pdf
  orpath.bat knowledge-preprocess --cloud
  ```
- [ ] 门禁 `phase1_mineru_cloud_gate.py`：
  - 无 `MINERU_API_TOKEN` → **SKIP 非红**（offline 仍 PASS）
  - 有 token → 云路径必绿：`notes/mineru-last.json` 含 `backend=cloud` 或等价 · md 非空 · hybrid 可命中
- [ ] 文档：`knowledge/inbox_pdf/README.md` 写清云 vs offline

### 交付

- 云路径可重复命令 + cloud gate  
- manifest 字段：`extract_backend` / `cloud_job_id?` / `error?`

### 验收

| 检查 | 标准 |
|------|------|
| offline | 仍 `phase1-mineru-gate` PASS |
| cloud | 有 token 时 cloud gate PASS |
| 安全 | 日志/manifest **无** raw token |

### 非目标

本地 GPU MinerU 重部署；全自动扫盘 OCR 一切 PDF。

---

## Phase 2 — 真文献主粮流水线 · **DONE**

**目标：** 主粮从「策展短笔记 + 合成 mineru_lecture」升级为 **可指认来源的文献/讲义条目**（md 必进库；PDF 可选经 Phase1）。

### 做

- [ ] 清单源（优先已有脚本，不新造爬虫帝国）：
  - 既有 `knowledge/or_papers_*` / `scripts/build_or_paper_list.py` 等 → **筛选 TopN 可 OA 或已有 md**
  - 人工策展补充允许
- [ ] 入库规范（每篇 md frontmatter 或头注释）：
  ```yaml
  kind: paper-note | paper-mineru | lecture
  source: doi|arxiv|path|curated
  title: ...
  domain: shortest_path|tsp|vrp|polyomino|general_or
  date: YYYY-MM-DD
  ```
- [ ] 门槛（关单写死当时数）：

  | 指标 | 建议最低 |
  |------|----------|
  | 有 `source`/`title` 的 papers | **≥50** |
  | 经 **真 PDF 预处理**（非 synthetic lecture 文件名） | **≥5**（有 token/PDF 时）否则 SKIP 记完成度 |
  | chunks | **≥150** |
  | 域覆盖 | SP/TSP/VRP/poly/建模 均 ≥1 **真源** |

- [ ] `CORPUS.md` 分表：策展 / mineru 真抽 / 文献 shortlist  
- [ ] `knowledge-eval` 保持 ≥16 问；可 +2 问绑真实 title 关键字  
- [ ] git：PDF 默认 ignore；md 可入库

### 交付

- 真源语料批次 + CORPUS 索引  
- `phase2_real_corpus_gate.py`（规模+元数据+eval）

### 验收

| 检查 | 标准 |
|------|------|
| 元数据 | 抽查 ≥10 篇含 title/source |
| 规模 | 达上表 |
| 安全 | 无 solution JSON 进 corpus |

### 非目标

BEIR SOTA；付费全库镜像；默认批量下载 Elsevier PDF。

---

## Phase 3 — live embed 研究默认 + 增量 ingest · **DONE**

**目标：** 有硅基 key 时，**研究档 hybrid 默认 live**；全量 rebuild 不再是唯一姿势。

### 做

- [ ] 配置契约：
  | 变量 | 含义 |
  |------|------|
  | `ORPATH_KNOWLEDGE_EMBED` | `auto\|live\|stub`（保持） |
  | `ORPATH_KNOWLEDGE_PROFILE` | `demo\|research`（新）：`research` → hybrid + prefer live |
- [ ] **增量 ingest**：按 mtime/hash 跳过未变文件；`--clear` 仍全量  
- [ ] retrieval 制品：`embed_mode` + `index_fingerprint`（可选）  
- [ ] 门禁 `phase3_live_default_gate.py`：
  - stub 必绿  
  - 有 key：`profile=research` 或 env live → artifact `embed_mode=live`  
  - 无 key：SKIP live 断言，文档写降级  
- [ ] CI/演示：默认 stub；本机研究：live

### 交付

- 增量 ingest + profile 开关  
- live default gate

### 验收

| 检查 | 标准 |
|------|------|
| 增量 | 二次 ingest 更快或跳过计数 >0 |
| live | 有 key 时 research 路径 live |
| 数字链 | mock SP validate 仍与 embed 解耦 |

### 非目标

自训 embedding；上云向量库硬依赖。

---

## Phase 4 — 产品厚体验（CASE / 研究档） · **DONE**

**目标：** 厚栈不是「只有 gate slug」：用户按菜谱跑 **CASE 或 run_t2 研究档** 能看到 hybrid 吃真主粮。

### 做

- [ ] 固定 slug：`thick-research-sp`（或 poly 小题）  
  ```bat
  set ORPATH_KNOWLEDGE_PROFILE=research
  set ORPATH_KNOWLEDGE_EMBED=auto
  run_t2 ... --knowledge-mode hybrid --solve-mode mock --no-live-subagent
  ```
- [ ] 断言 `phase4_product_research_gate.py`：
  - retrieval hybrid · hits≥1 · **真源 papers**（优先非 synthetic 名）  
  - `embed_mode` 诚实  
  - research Coverage + chunk_id  
  - validate ok  
  - paper/claim_map：**不得**因厚 corpus 导致数字链失败；paper 失败最多 WARN（延续 v2 纪律）
- [ ] （可选加分）Watch 只读盘能看到 retrieve 阶段轨迹（slug 对齐）  
- [ ] 与 `thick-hybrid-gate` / v1 `phase3-hybrid-gate` **并存回归**  
- [ ] `ORPATH.md` 一节「研究档四步」

### 交付

- 产品研究档 gate + evidence.md  
- 菜谱写进 ORPATH / closeout

### 验收

| 检查 | 标准 |
|------|------|
| 产品路径 | gate PASS |
| 引用 | 至少 1 条 hit 真主粮 |
| 回归 | v2 `phase5-thick-gate` 子集或 thick-hybrid 仍 PASS |

### 非目标

LIVE 默认全开 hybrid（太慢/贵）；改 Watch 成 Pi 原生 tool 面板。

---

## Phase 5 — 验收 · 菜谱 · v3 关单 · **DONE**

**目标：** 对外诚实说清 v3 完成度；新人可复现。

### 做

- [ ] 总门禁 `phase5_v3_knowledge_gate.py`：  
  mineru offline +（cloud SKIP/硬）+ real corpus + live default + product research + v2 thick 子集  
- [ ] 更新：
  - `specs/knowledge-and-retrieval.md`（profile、增量、云门禁）  
  - `docs/ARCHITECTURE.md` 一句  
  - `ORPATH.md` 命令收束  
- [ ] closeout：`knowledge-rag-v3-prod-closeout.md`  
  - 完成度表（对照 v2，禁止 100% 空话）  
  - 文档放哪（不变主路径）  
  - 对外三句话（可微调）  
- [ ] 本计划勾选 ALL DONE

### 交付

| 文件 | 内容 |
|------|------|
| v3 closeout | 边界 + 三句话 + 完成度 % |
| 总 gate | 一键回归 |
| 菜谱 | 新人 PDF→…→research |

### 验收（完成定义）

- [ ] Phase 1–4 验收全勾  
- [ ] 新人路径：  
  `inbox PDF → preprocess → sync → eval → thick/product research gate`  
- [ ] 三句话就绪：  
  1. 真 PDF/文献可进 Pi 书库（云 MinerU 或 md）  
  2. 研究档 hybrid 优先 live 语义 + 词法 RRF  
  3. 数字仍只 solve+validate  
- [ ] 完成度表：云 MinerU / 真 PDF 数 / live 默认 三项诚实

### 非目标

M3 launch 注入史诗；M4 记忆；RAG 网页；fine-tune 话术。

---

## 3. 跨阶段硬约束

| 规则 | |
|------|--|
| 框架 | 只加厚 `knowledge_svc`，不换主脑 |
| 上游 | PDF → 预处理；禁止二进制当 chunk 正文 |
| 数字 | solution/validate **不进** corpus 权威 |
| 训练 | **禁止** fine-tune /「用论文训练模型」 |
| 降级 | 无 MinerU token / 无 embed key → 管道可演示 + **完成度降级写进 closeout** |
| 主产品 | Demo 可 seed；研究档 hybrid+live |
| V0/M0 | 本 v3 **不抢** Watch 主优先级 |

---

## 4. 环境变量（不入库）

| 变量 | 阶段 | 缺失 |
|------|------|------|
| `MINERU_API_TOKEN` | 1 | 云 gate SKIP |
| `SILICONFLOW_API_KEY` 等 | 3 | live SKIP / stub |
| `ORPATH_KNOWLEDGE_EMBED` | 3–4 | auto |
| `ORPATH_KNOWLEDGE_PROFILE` | 3–4 | demo 默认 |

---

## 5. 建议命令面（v3 完成后）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONPATH=
set PYTHONNOUSERSITE=1

:: 真 PDF
copy my.pdf knowledge\inbox_pdf\
orpath.bat knowledge-preprocess
orpath.bat knowledge-sync

:: 研究档
set ORPATH_KNOWLEDGE_PROFILE=research
set ORPATH_KNOWLEDGE_EMBED=auto
orpath.bat knowledge-eval
orpath.bat thick-hybrid-gate
orpath.bat phase5-v3-gate
```

**文档位置（不变）：**

| 内容 | 路径 |
|------|------|
| md | `knowledge/corpus/papers/` |
| PDF | `knowledge/inbox_pdf/` |
| 预处理产出 | `knowledge/corpus/papers/_from_mineru/` |

---

## 6. 风险

| 风险 | 缓解 |
|------|------|
| MinerU API 限流/变更 | 重试+fixture；云 gate SKIP |
| 真 PDF 版权 | 只用可分享讲义/OA；不进 public 强制大 PDF |
| live 费钱 | 增量；CI stub |
| claim_map 厚库抖 | paper WARN；数字链硬绿 |
| 计划膨胀碰 M4 | 本文件明确不做记忆史诗 |

---

## 7. 决策记录

| 问题 | 决定 |
|------|------|
| v2 后是否够用 | **产品演示够**；真 PDF/默认 live **不够** → v3 |
| 是否开 M4 | **否** |
| 几个阶段 | **5** |
| 关单名 | `knowledge-rag-v3-prod-closeout.md` |

---

## 8. 开干顺序

```text
Phase 1 云 MinerU 真 PDF
  ∥ Phase 2 真文献主粮（可交错）
→ Phase 3 live 默认 + 增量
→ Phase 4 产品研究档体验
→ Phase 5 v3 关单
```

**v3 已关单：** `docs/archive/closeouts/knowledge-rag-v3-prod-closeout.md` · `orpath.bat phase5-v3-gate`

---

## 9. 进度板（开工后勾选）

| 阶段 | 状态 |
|------|------|
| Phase 1 云 MinerU | **DONE 2026-08-04**（phase1_mineru_cloud_gate） |
| Phase 2 真文献主粮 | **DONE 2026-08-04**（lit shortlist + phase2_real_corpus_gate） |
| Phase 3 live 默认 | **DONE 2026-08-04**（profile + incremental + phase3_live_default_gate） |
| Phase 4 产品研究档 | **DONE 2026-08-04**（thick-research-sp · product-research-gate） |
| Phase 5 v3 关单 | **DONE 2026-08-04**（phase5_v3_knowledge_gate + v3 closeout） |
