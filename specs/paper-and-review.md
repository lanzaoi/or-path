# Paper and Review — 论文环与审稿门

## 统一接缝（ADR-0004）

| 模块 | 职责 |
|------|------|
| **`orpath/paper_protocol.py`** | **PaperProtocol 权威**：`run_from_solution` / 路径与模板 re-export |
| `orpath/paper_workflow.py` | 渲染、review md、plan log 等实现细节 |
| `orpath/paper_live_subagent.py` | cite/review live 适配器（nodes 内用） |
| `orpath/post_solve_paper.py` | 兼容 shim → `paper_protocol` |
| `scripts/orpath_paper.py` | 薄 CLI |
| `scripts/run_tube_cut_paper.py` | 圆管 → `run_from_solution`（不重解） |
| 图内 | `nodes` 的 `draft_paper`…`provenance` = 同环（`IN_GRAPH_STAGES`） |

```text
python scripts/orpath_paper.py protocol --slug S --solution path/to/solution.json
# 或
from orpath.paper_protocol import run_from_solution
```

## 两环分离

| 环 | 目标 | 数字权威 |
|----|------|----------|
| A Solve | 可行/最优解 | solution + validate（ADR-0002 dispatch） |
| B Paper | 文稿 | **必须绑定** solution/validate 制品 |

禁止 writer 在无 solution 时编造 objective。

## T2 Paper DoD（Q10-C）

1. **三类题**（SP / TSP / VRP）各至少一条：  
   `solve → validate 绿 → draft` 且 **R2 脚本绿**（可 mock solve）进本地 gate  
2. **Live writer ≥ 1**（建议 TSP 或 VRP）  
3. **OpenPi 截图** 可覆盖该 live 条（与 Q1-C 合并证据）  
4. **在线 R1**（真 arXiv/DOI 校验）进 **cloud/online 轨**（Q11-B）

## Review 通道

| 通道 | 类型 | T2 |
|------|------|-----|
| **R2** | 脚本：文中 objective-like / 大数值 ⊆ solution | **硬**；支持 path/tour/routes |
| **R1 本地** | 引用 ⊆ whitelist ∪ research/retrieval 证据 | **硬**（`t2_gate`） |
| **R1 在线** | HTTP/API 校验 DOI/arXiv 存在性 | **硬**（`t2_gate_cloud` 或 `t2_gate_paper_online`） |
| **R0** | 结构完整性 | 可选软 |
| **R3** | 语义 / 反虚榜 | 可选 LLM critic |

## 默认顺序

```text
writer draft  (outputs/.drafts/<slug>-draft.md)
  → cite_pack   (R1 whitelist + claim_map → .drafts/<slug>-cited.md + claim-map.json)
  → review_pack (R1∥R2∥claim + inline annotations)
  → revise_or_done
       ├─ fix → revise-proof.md → re-cite (cite_pack) → review
       └─ done → provenance (PASS|BLOCKED)
  → FATAL ceiling → HUMAN_REQUIRED
```

P0 硬门：`tools/r1_claim_map.py`（数字/URL/全局最优话术/面积结构映射到 solution 或 research）。

## R2 规则要点

- objective-like 断言必须能在 solution 中找到  
- 继承 T1 教训：小计数器 0–20 可放行；边权原样出现需在 solution/graph 允许集  
- tour 长度、路线数、总距离等从 solution 抽取允许集  

## R1 本地 whitelist

- fixture：`whitelist_refs.json`  
- 另允许 retrieval artifact 中的 `source_path` / 约定 chunk 引用格式  

## R1 在线

- 仅校验 **可解析** 的 arXiv id / DOI  
- 网络失败：cloud 轨 FAIL 或重试，**不得**静默当 PASS  
- 本地轨不依赖外网  

## 文稿路径

- `papers/<slug>.md`  
- 分层草稿（P1）：`outputs/.drafts/<slug>-{draft,cited,revised}.md`  
- review：`outputs/<slug>-review.md`（含 **Inline Annotations**）  
- verify notes：`outputs/<slug>-verify-notes.md`  
- plan ledger：`outputs/.plans/<slug>.md`（每阶段 append Verification log）  
- 模板：`templates/paper/or-portfolio.md` · `or-mcm.md`  

## P1 入口

```bat
orpath.bat paper-gate
orpath.bat paper template --slug X --solution path.json
orpath.bat paper review --slug X --paper papers/X.md --solution ... --whitelist ...
python tools/gate_research.py --research notes/X-research.md --retrieval notes/X-retrieval.json --knowledge-mode seed
```

## 话术

- LLM review ≠ 真期刊审稿  
- 不宣称论文已发表或达顶会水平  
