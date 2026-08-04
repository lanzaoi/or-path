# OR-Path · 知识厚栈 v2 五阶段计划  
# MinerU → chunk → LightRAG∥BM25/FTS → RRF → research（最厚目标收口）

> **状态：** **Phase 1–5 ALL DONE · CLOSED**  
> **日期：** 2026-08-04  
> **承接：** v1 关单 `docs/archive/closeouts/knowledge-rag-v1-closeout.md`  
> （v1 = 管子 + 策展 md + Pi 能吃 retrieval；**≠** 七月最厚目标完成）  
> **消费方：** **Pi** research（主）— 不是人用知识站、不是 fine-tune  
> **技术脊柱：** 继续 `knowledge_svc/*`，**不换** LlamaIndex / 不上 Cognee 主脑  

---

## 0. 为什么还要五阶段

### v1 已有

| 有 | 薄在哪 |
|----|--------|
| BM25 / FTS / RRF / chunk | 真语义偏 **stub** |
| hybrid → research 证据 | 默认 `force_stub=True` |
| 策展 `papers/*.md`×~29 | **无 PDF→文本产品闭环** |
| skill/lesson allowlist | 非规模论文库 |
| CLI + phase3–5 gate | MinerU 仅 client + offline md 路径 |

### 你要的最厚目标（硬对齐）

```text
PDF / 扫描件
  → MinerU（云或等价）→ 干净 md/txt
  → 统一 chunk_id
  → LightRAG 语义索引  ∥  BM25 + FTS 词法
  → RRF 融合
  → notes/*-retrieval.json
  → research 必消费（hybrid）
  + 种子图 / 白名单 skill·lesson（v1 已有，继续用）
```

**关键因果（写入法）：**  
hybrid = 语义 + 词法。**语义侧吃文本向量/图，词法侧吃 token。**  
PDF 不进预处理 → 库里没有合格主粮 → LightRAG+BM25 再厚也是空转。  
故 **MinerU（或同等 PDF→md）是厚栈上游刚需**，不是可选花活。

### v2 成功一句话

> 任意运筹 PDF 可进箱 → 预处理落 `corpus` → **真 embed hybrid** 可查 →  
> 产品 `knowledge_mode=hybrid` 的 research **稳定引用**预处理语料路径；  
> optima 仍只信 solve+validate。

---

## 1. 与 v1 边界

| | v1（已 CLOSED） | v2（本计划） |
|--|-----------------|--------------|
| 语料 | 策展短 md | **PDF 流水线 + 规模论文 md** |
| MinerU | client 存在 | **产品命令 + 门禁 + 落盘约定** |
| LightRAG | stub/cosine 可演示 | **真 embed 默认路径（有 key）+ stub 降级** |
| 完成话术 | 「RAG 竖切可重建」 | 「厚栈上游+语义+规模可交代」 |
| 不做什么 | 网页 / fine-tune | 同左 + 仍不 Cognee 主脑 |

**v1 门禁继续绿；v2 不推翻 v1，只加厚。**

---

## 2. 五阶段总览

| 阶段 | 名称 | 核心交付 | 预估人日 | 依赖 |
|------|------|----------|----------|------|
| **1** | MinerU 预处理闭环 | PDF→md→corpus 可重复命令与证据 | 1.5～2.5 | token 或 offline 夹具 |
| **2** | 真语义 LightRAG 加厚 | 硅基 bge-m3（或配置 embed）ingest/retrieve；stub 仅降级 | 1～2 | API key 可选但要测双轨 |
| **3** | 规模主粮入库 | ≥N 篇真论文/讲义 md（经预处理）+ 索引重建 | 1～3 | Phase 1 |
| **4** | 产品厚路径证据 | hybrid **非 stub 优先** 的产品 run + research 引用预处理源 | 1～1.5 | Phase 1–2 |
| **5** | 厚栈验收 · 关单 | eval 加厚 + v2 closeout + 完成度诚实表 | 0.5～1 | 1–4 |

**合计约 5～10 人日**（视 PDF 数量与云 API 稳定性）。

```text
Phase1 MinerU 闭环 ──┬──► Phase3 规模入库 ──► Phase4 产品厚证据 ──► Phase5 关单
Phase2 真 embed ─────┘         ▲
                               └── 可并行 1∥2，3 依赖 1
```

---

## 3. 进度快照

| 阶段 | 状态 |
|------|------|
| Phase 1 MinerU 闭环 | **DONE 2026-08-04**（`phase1_mineru_gate` · offline fixture） |
| Phase 2 真语义 | **DONE 2026-08-04**（`ORPATH_KNOWLEDGE_EMBED` · `phase2_embed_gate`） |
| Phase 3 规模主粮 | **DONE 2026-08-04**（papers≥40 · mineru≥10 · phase3_scale_gate） |
| Phase 4 产品厚证据 | **DONE 2026-08-04**（thick-hybrid-sp · phase4_thick_hybrid_gate） |
| Phase 5 关单 | **DONE 2026-08-04**（phase5_thick_knowledge_gate + v2 closeout） |

基线（开工前已存在，勿当 v2 完成）：

- `knowledge_svc/mineru_client.py`
- `knowledge_svc/lightrag_adapter.py` + `embed_siliconflow.py`
- `knowledge/mineru_out/`（历史/缓存目录名，约定以本计划为准）
- v1：`knowledge-sync` · `phase3/4/5-*-gate`

---

## Phase 1 — MinerU 预处理闭环（上游刚需）· **DONE**

**目标：** 「PDF 进箱 → 文本落 corpus → 可 ingest」成为 **一条官方命令**，有磁盘证据；无 token 时有 **offline 夹具**不崩门禁。

### 做（已交付）

- [x] 目录：`knowledge/inbox_pdf/` · `mineru_out/` · `corpus/papers/_from_mineru/`
- [x] CLI：`knowledge-mineru` · `knowledge-preprocess` · `phase1-mineru-gate`
- [x] 本地提取：sidecar `.md`/`.txt` · pypdf/pymupdf · offline fixture
- [x] 云 submit 可选（有 token）；不阻塞本地落盘
- [x] manifest：`notes/mineru-last.json` · `knowledge/mineru_out/manifest.json`
- [x] Windows 去重 `*.pdf`/`*.PDF`

### 验收（2026-08-04）

```bat
orpath.bat phase1-mineru-gate
```

`PASS phase1_mineru_gate` — preprocess → corpus md → ingest retrieve 命中 `_from_mineru`。

---

## Phase 2 — 真语义 LightRAG / embed 加厚 · **DONE**

**目标：** hybrid 的语义腿在 **有硅基（或配置）key 时走真 embed**；无 key 时 **明确降级 stub**，话术不得称「语义已厚完」。

### 做（已交付）

- [x] `ORPATH_KNOWLEDGE_EMBED=auto|live|stub` + `resolve_embed_mode`
- [x] ingest/retrieve/node_retrieve 不再永远 force_stub
- [x] artifact 字段 `embed_mode` / `embed_meta`
- [x] `phase2_embed_gate`（stub 硬绿；live 有 key 硬绿 / 无 key SKIP）

### 原清单（保留参考）

- [x] 配置契约（env，不入库 secret）：

  | 变量 | 含义 |
  |------|------|
  | `SILICONFLOW_API_KEY` / 既有 embed 变量 | 真 bge-m3 |
  | `ORPATH_KNOWLEDGE_EMBED=live\|stub\|auto` | 默认 `auto`：有 key→live else stub |

- [ ] `ingest` / `retrieve` / `node_retrieve`：
  - 去掉「产品路径永远 `force_stub=True`」；改为读配置
  - artifact 写明 `embed_mode: live|stub`
- [ ] LightRAG adapter：
  - live：持久化向量（既有 lightrag_ws 或等价）可重建
  - 失败自动 stub + warning（不拖死主数字链）
- [ ] 双轨门禁：
  - `knowledge-embed-gate --mode stub` 必绿
  - `knowledge-embed-gate --mode live`：无 key → **SKIP 非红**；有 key → 必绿且 live 命中可区分
- [ ] 文档：stub vs live 完成度话术；**禁止**无 key 宣称「真语义生产就绪」

### 交付

- embed 模式开关 + retrieval JSON 字段 `embed_mode`
- `scripts/phase2_embed_gate.py`（名可调整）
- ORPATH / knowledge-and-retrieval 一小段

### 验收

| 检查 | 标准 |
|------|------|
| stub | 无 key 时 hybrid 仍 hits≥1（v1 回归） |
| live | 有 key 时 ingest 写向量、retrieve `embed_mode=live` |
| 可区分 | 同一 query 的 artifact 能看出 live/stub |
| 主链 | SP mock validate 仍与 embed 解耦 |

### 非目标

自训 embedding；上 Graphiti；换向量商业库为硬依赖。

---

## Phase 3 — 规模主粮入库 · **DONE**

**目标：** corpus 从「策展 29 短笔记」提升到 **可感知的论文/讲义主粮**（经 Phase1 预处理或等价 md）。

### 做

- [ ] 数量门槛（可调，关单写死当时数字）：

  | 指标 | 建议最低 |
  |------|----------|
  | 经预处理或人工 md 的 **papers 文件** | **≥40**（含 v1；其中 **≥10** 来自 MinerU/inbox 路径若有 PDF） |
  | ingest chunks | **≥120**（或 papers≥40 二选一写进验收） |
  | 领域覆盖 | SP / TSP / VRP / poly / 通用建模 均有 ≥1 真源 |

- [ ] 元数据：`kind: paper-note | paper-mineru | lecture` · 来源 · 日期
- [ ] `knowledge/CORPUS.md` 更新索引（MinerU 来源单独表）
- [ ] `knowledge-sync` 后跑 `knowledge-eval`（12 问全 hits）
- [ ] git：大 PDF 默认 gitignore；**md 与 manifest 可入库**

### 交付

- 加厚 `corpus/papers/`
- 更新 CORPUS.md
- eval 日志 `notes/knowledge-eval-last.json`

### 验收

| 检查 | 标准 |
|------|------|
| 规模 | 达上表门槛 |
| 来源 | 至少 1 条 chunk `source_path` 含 mineru 产物路径或 `_from_mineru`（若本机跑过 PDF） |
| 安全 | corpus 仍无 `*-solution.json` / 权威 objective 文件 |
| eval | 12/12 hits≥1 |

### 非目标

爬全网；公开 BEIR SOTA；把竞赛官方答案 PDF 当 optima 库。

---

## Phase 4 — 产品厚路径证据 · **DONE**

**目标：** 证明厚栈不是 CLI 玩具：**产品 run** 在 hybrid 下 research 引用的是 **预处理/规模语料**，且 embed_mode 诚实。

### 做

- [ ] 固定演示 slug：`thick-hybrid-sp`（或 poly 小题）  
  ```bat
  run_t2 ... --knowledge-mode hybrid --solve-mode mock --no-live-subagent
  :: 可选：ORPATH_KNOWLEDGE_EMBED=live
  ```
- [ ] 断言（`scripts/phase4_thick_hybrid_gate.py`）：
  - `*-retrieval.json`：`knowledge_mode=hybrid`，hits≥1
  - 至少 1 条 hit 的 `source_path` 指向 **papers 主粮**（优先 mineru 来源若存在）
  - research.md：Coverage + chunk_id 引用
  - `embed_mode` 字段存在
  - validate ok（数字与 RAG 解耦）
- [ ] 与 v1 `phase3-hybrid-gate` **并存**（v1 回归不删）
- [ ] LIVE 真 Pi：**可选加分项**，不挡 v2 关单（慢、贵）

### 交付

- `notes/thick-hybrid-*-retrieval.json` + research + evidence.md
- thick gate 脚本 + bat 入口

### 验收

| 检查 | 标准 |
|------|------|
| 产品路径 | gate PASS |
| 引用 | research 含主粮 chunk_id |
| 回归 | v1 `phase3-hybrid-gate` 仍 PASS |
| 话术 | evidence 写清 stub/live |

### 非目标

model 站灌全文 PDF；cite 爬全网。

---

## Phase 5 — 厚栈验收 · 文档 · 关单 · **DONE**

**目标：** 可对外诚实说清 **v2 完成了什么、仍多厚**。

### 做

- [ ] 加厚 eval（可选 +4 问：mineru 源、live embed、某篇论文标题关键字）
- [ ] 总门禁 `phase5_thick_knowledge_gate.py`：  
  mineru gate + embed gate + eval + thick hybrid + v1 phase5 回归子集
- [ ] 更新：
  - `specs/knowledge-and-retrieval.md`（MinerU 上游、embed_mode）
  - `docs/ARCHITECTURE.md` 一句厚路径
  - `ORPATH.md` 命令收束
- [ ] closeout：`docs/archive/closeouts/knowledge-rag-v2-thick-closeout.md`
- [ ] **完成度表**（对照七月最厚，禁止 100% 空话）

### 交付

| 文件 | 内容 |
|------|------|
| v2 closeout | 边界 + 三句话 + 完成度 % |
| 总 gate | 一键回归 |
| 本计划勾选 | ALL DONE |

### 验收（完成定义）

- [ ] Phase 1–4 验收全勾  
- [ ] 新人：inbox PDF（或 fixture）→ preprocess → sync → eval → thick-hybrid-gate  
- [ ] 对外三句话就绪：  
  1. PDF/文本经预处理进 Pi 参考书库  
  2. hybrid = 真语义（能 live 则 live）+ BM25/FTS + RRF  
  3. 数字仍只 solve+validate  
- [ ] 完成度表填写且 **MinerU、live embed、规模** 三项不得标「空」却写完成  

### 非目标

M4 记忆史诗；Cognee 生产化；RAG Web UI；宣称 fine-tune。

---

## 4. 跨阶段硬约束

| 规则 | |
|------|--|
| 框架 | 只加厚 `knowledge_svc`，不换 LI 主脑 |
| 上游 | **PDF 主粮必须经预处理**；禁止「二进制 PDF 直接当 chunk 正文」蒙混 |
| UI | **无** RAG 网页 |
| 训练 | **禁止** fine-tune /「用论文训练模型」话术 |
| 数字 | solution/validate **不进** corpus 权威 |
| Cognee | 旁路 smoke only |
| 降级 | 无 MinerU token / 无 embed key → 管道可演示但 **完成度降级**，文档写明 |
| 默认产品 | Demo 仍可 seed；厚研究档 hybrid + 建议 live embed |

---

## 5. 环境与密钥（不入库）

| 变量 | 阶段 | 缺失时 |
|------|------|--------|
| `MINERU_API_TOKEN` | 1 | offline fixture；云测 SKIP |
| `MINERU_BASE_URL` | 1 | 默认 mineru.net API |
| 硅基 / embed key（既有 `embed_siliconflow`） | 2 | stub；live gate SKIP |
| `ORPATH_KNOWLEDGE_EMBED` | 2–4 | `auto` |

---

## 6. 建议命令面（完成后）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONPATH=
set PYTHONNOUSERSITE=1

:: 上游
orpath.bat knowledge-mineru --inbox
orpath.bat knowledge-preprocess

:: 索引（含 skill/lesson 白名单）
orpath.bat knowledge-sync

:: 真语义（有 key）
set ORPATH_KNOWLEDGE_EMBED=live
orpath.bat knowledge-sync

:: 查 + 评
orpath.bat knowledge-retrieve --query "..." --mode hybrid --topk 5
orpath.bat knowledge-eval

:: 门禁
orpath.bat phase3-hybrid-gate
orpath.bat thick-hybrid-gate
orpath.bat phase5-thick-knowledge-gate
```

PDF 投放：`knowledge/inbox_pdf/`  
入库文本：`knowledge/corpus/papers/`  

---

## 7. 风险与坑

| 风险 | 缓解 |
|------|------|
| MinerU API 变更/限流 | client 版本钉死；fixture 保门禁；manifest 记 error |
| 真 embed 费钱/慢 | 增量 ingest；CI 默认 stub；live 本机/夜跑 |
| 大 PDF 进 git | gitignore inbox；只提交 md |
| MSYS 路径 | 沿用 `normalize_fs_path` / 相对路径 |
| 与 v1 gate 漂移 | v2 总门禁显式跑 v1 子集 |
| 话术膨胀 | closeout 强制完成度表 |

---

## 8. 决策记录

| 问题 | 决定 |
|------|------|
| 是否重做 v1 | **否**，加厚为 v2 |
| MinerU 是否可选 | **厚目标下否**；无 token 仅降级演示 |
| 为何要 MinerU | hybrid 双腿需要**文本主粮**；PDF 必须预处理 |
| LightRAG | 继续 adapter 加厚，不新开重框架 |
| 几个阶段 | **5**（本文件） |
| 关单名 | `knowledge-rag-v2-thick-closeout.md` |
| 完成标志 | Phase5 gate PASS + 完成度表诚实 |

---

## 9. 和「完成了多少」对齐（开工基线）

| 厚栈块 | 开工前粗估 | v2 目标后 |
|--------|------------|-----------|
| MinerU 闭环 | ~20% | **≥90%**（有 token）/ 70%+fixture |
| chunk/BM25/FTS/RRF | ~90% | 保持 |
| LightRAG 真语义 | ~35% | **≥75%**（live 路径） |
| 规模主粮 | ~30% | **≥70%** |
| research 消费 | ~80% | **≥90%**（厚源引用） |
| **整条最厚目标** | **~45–55%** | **~80–90%**（诚实上限，视 key/语料） |

---

## 10. 开干顺序（实操）

```text
先 Phase 1（MinerU 命令+manifest+gate）
  ∥ 可平行 Phase 2（embed_mode + live/stub）
→ Phase 3（你丢 PDF/md，sync，eval）
→ Phase 4（thick-hybrid 产品证据）
→ Phase 5（closeout）
```

**v2 已关单：** `docs/archive/closeouts/knowledge-rag-v2-thick-closeout.md` · `orpath.bat phase5-thick-gate`
