# OR-Path 交接文档 · 2026-08-04 收工

**给下一会话 / 下一 Agent。** 产品法以 `specs/` 为准；本文只指针 + 现状，不复制大段法条。

**路径：** 本文件亦落在仓库 `docs/archive/handoffs/2026-08-04_eod-handoff.md`；  
技能要求的本机副本：`%LOCALAPPDATA%\Temp\orpath-handoff-2026-08-04.md`。

---

## 1. 产品是什么

OR-Path Multi-Agent / Graph-OR：题面 → research → model → **solve** → **validate** → paper。  
控制面 LangGraph；Pi = 节点内包工头。数字权威 **只信 solve+validate**。

主入口：`START-CASE.bat` · `START-WATCH.bat` · `orpath.bat`  
远端：**https://github.com/lanzaoi/or-path**（`origin`）

---

## 2. 今天已完成（可宣称）

| 项 | 证据 / 口径 |
|----|-------------|
| RAG v1–v3 | closeout `docs/archive/closeouts/knowledge-rag-v*-*.md`；诚实完成度 **~88–92%** |
| promote-run | `scripts/promote_run_to_skill.py` · `orpath.bat promote-run` |
| Tube 确定性 schema | `orpath/nodes.py` tube 分支；no-live 可过 schema |
| Tube envelope | `tools/solve_dispatch.py` 双路径 OUT + remnant_min_mm=200 |
| claim_map 诚实 | 否定句不误杀 global-opt；**claims_recorded:N** 过程计数不绑结果 |
| LIVE B 题 | slug **`hdu-b-tube-ma2`** workdir `Desktop/hdu2026-b-tube`：live=True · exit=0 · 全 gate 绿 |
| Specs 瘦身 | 合并 hygiene；删 openpi/t3-vrp-tw/coding+git 分册 |
| Git commit | `d9d17b5` feat RAG v3 + tube LIVE + claim_map（**push 曾因未 gh login 失败**） |

### Tube 数字（pack / ma2 一致量级）

| 问 | 母材 mm | 共切 mm | 备注 |
|----|---------|---------|------|
| Q1 | 100000 | 0 | FEASIBLE |
| Q2 | 100000 | ~464 | 共切弱 |
| Q3 | **99000** | ~466 | 主 objective |
| Q4 | **260000** 新母材 | ~1018 | remnant≥200 |

**对照：** 用户 GPT 迭代稿 PDF 约 Q3=**97000** · Q4=**252000** · Q2 共切 **~2400** —— 建模更深；**skills/RAG 未自动抬到该档**（差在几何共切+搜索，不在插件数量）。

---

## 3. 未做 / 勿宣称

- M3/M4 记忆史诗；Cognee 主记忆  
- Tube 共切对齐 GPT 360° 矩阵 + 列生成级搜索  
- 云 MinerU CDN 全文 100% 硬化  
- `knowledge/corpus/papers` 大体量、inbox PDF、运行日志 **默认不入库**  
- **push 需本机 `gh auth login` 后** `git push -u origin HEAD`

---

## 4. 关键路径

| 用途 | 路径 |
|------|------|
| 法条索引 | `specs/README.md` |
| 工程卫生 | `specs/engineering-hygiene.md` |
| 知识法 | `specs/knowledge-and-retrieval.md` · `memory.md` |
| 架构 | `docs/ARCHITECTURE.md` |
| 操作 | `ORPATH.md` · `README.md` |
| B 案例 workdir | `C:\Users\Lanzao\Desktop\hdu2026-b-tube` |
| pack 数字 | `outputs/b-tube-cut/` |
| LIVE 绿跑 | `…/outputs/hdu-b-tube-ma2.provenance.md` |
| GPT 对照稿 | `C:\Users\Lanzao\Downloads\B题论文.pdf`（本地，不入库） |

---

## 5. 建议下一刀（若续）

1. **鉴权 push：** `gh auth login` → `git push origin main`  
2. **Tube 抬分（可选）：** 共切 360° 包络 + Q2 重排 + Q3 联合搜索 → 对照 97k/252k  
3. **不要：** 再开 Memory 五阶段史诗；用手改 objective 刷绿  

---

## 6. Suggested skills

| Skill | 何时 |
|-------|------|
| `orpath-windows-product-runtime` | START-CASE / watch-run / LIVE / bat |
| `or-path-knowledge-rag` | knowledge-sync / promote / corpus |
| `handoff` | 再交接 |
| `github-pr-workflow` / `gh` | push/PR 之后 |

---

## 7. 红线备忘

- Hermes：OCR/路径/拉起/监控；**不代解、不改 objective**  
- LIVE 必须 `--live`；否则 live=false  
- Watch 多次 start 会弹多标签 → 可用 `--no-browser`  
- 过程计数 `claims_recorded` ≠ 结果数字（已 mask）  

---

## 8. 提交说明（待 push）

```text
d9d17b5 feat: RAG v3 + tube LIVE path; fix claim_map meta false-positive
(+ 本交接/README/specs 瘦身另 commit)
```
