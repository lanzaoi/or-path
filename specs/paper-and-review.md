# Paper and Review — 论文环（详细）

**对齐：** `product-flow-sdd.md` · ADR-0004  
**状态：** LAW 2026-08-01

---

## 1. 统一接缝

| 模块 | 职责 |
|------|------|
| **`orpath/paper_protocol.py`** | `run_from_solution` 权威 |
| `paper_workflow.py` | 渲染/review 实现 |
| `paper_live_subagent.py` | cite/review live |
| `post_solve_paper.py` | shim |
| 图内节点 | draft→cite→review→revise→provenance = 同环 |

```text
python scripts/orpath_paper.py protocol --slug S --solution path/to/solution.json
from orpath.paper_protocol import run_from_solution
```

---

## 2. 两环分离

| 环 | 目标 | 数字权威 |
|----|------|----------|
| A Solve | 可行/优解 | solution+validate |
| B Paper | 文稿 | **绑定** solution；禁编造 objective |

已有 solution 时优先 **只跑 B**，不重解。

---

## 3. 默认顺序

```text
draft_paper  → outputs/.drafts/<slug>-draft.md / papers/
  → cite_pack   → cited + claim-map +（live）or-verifier
  → review_pack → R1∥R2∥claim + review md +（live）or-reviewer
  → revise_or_done
       ├─ fix → revise-proof → 可 re-cite → review
       └─ done → provenance PASS|BLOCKED
  → FATAL ceiling → HUMAN_REQUIRED
```

---

## 4. Review 通道

| 通道 | 类型 | 硬度 |
|------|------|------|
| R2 | 文中数字 ⊆ solution | **硬** |
| R1 本地 | 引用 ⊆ WL ∪ retrieval | **硬**（本地 gate） |
| R1 在线 | arXiv/DOI | **硬**（cloud 轨） |
| claim_map | 结构/URL/虚榜/面积等 | **硬**（P0） |
| claim_ledger | 稳定 claimId | 厚 paper 1.0 |
| R0 结构 | 软可选 | |
| R3 语义 critic | 软可选 | |

---

## 5. 打回（论文侧）

- `revise_count` ≤ **2**  
- 回 **draft** 再 cite/review  
- **不改** solution 数字；数错回环 A  
- 时间线须能标 repair_edge（process-visibility）  

特殊：BLOCKED 求解后 paper 应 fail-closed / 快速 provenance，避免无意义烧 cite 次数（1.2 residual）。

---

## 6. Live vs 确定性

| | LIVE=0 | LIVE=1 |
|--|--------|--------|
| cite/review | 脚本路径 | harness 真 sub + 本地硬门 |
| 宣称 MA paper | 否 | 需 toolCall + 子文件 |

Draft：允许 lead 写（Feynman Step4 取向）；**禁止** lead ghost-write cited/review。

---

## 7. 路径约定

| 制品 | 路径 |
|------|------|
| 终稿 | `papers/<slug>.md` |
| 草稿层 | `outputs/.drafts/<slug>-{draft,cited,revised}.md` |
| review | `outputs/<slug>-review.md` |
| claim-map | `.drafts/*-claim-map.json` |
| provenance | `outputs/<slug>.provenance.md` |
| 模板 | `templates/paper/*` |

---

## 8. R2 要点

- objective-like 必须在 solution  
- 小计数器策略继承 T1 教训  
- 多题 `questions`/`metrics` 绑定  
- 掩 arXiv `YYYY.NNNNN` 防大数误报  

---

## 9. CLI

```bat
orpath.bat paper-gate
orpath.bat paper-1.0-gate
orpath.bat paper-protocol --slug S --solution path.json
orpath.bat paper-tube
```

---

## 10. 话术

LLM review ≠ 真期刊审稿；不宣称已发表/顶会水平。

---

## 11. 参考

`docs/paper-1.0-closeout.md` · ADR-0004 · `multi-agent.md`  
