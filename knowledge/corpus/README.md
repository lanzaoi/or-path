# knowledge/corpus — Pi RAG 语料根

**给谁用：** 运行时 **Pi research** 检索，不是人用网站。  
**不是：** 微调训练数据仓；solution/optima 权威。

## 目录约定

| 路径 | 内容 | 谁写 |
|------|------|------|
| `papers/` | 论文笔记 / 领域短 md | 人 |
| `papers/_from_mineru/` | **PDF 预处理产出 md**（v2 Phase 1） | `knowledge-preprocess` |
| `skills/` | 从 `.pi/skills` **导出的副本** | `knowledge-export` |
| `lessons/` | 从 `knowledge/lessons` JSON **导出的 md** | `knowledge-export` |
| 根下已有 `*.md` | 历史 curated 笔记 | 人 |

**PDF 投放：** `knowledge/inbox_pdf/`

## 预处理（v2 Phase 1）

```bat
orpath.bat knowledge-preprocess
orpath.bat knowledge-sync
orpath.bat phase1-mineru-gate
```

- 有 `MINERU_API_TOKEN`：尝试云提交（可选）  
- 无 token：本地提取 / sidecar `.md` / offline fixture  
- manifest：`notes/mineru-last.json`

## 语料规模（v2 Phase 3）

- `papers/**` 目标 ≥40（含 `_from_mineru`）
- 门禁：`orpath.bat phase3-scale-gate`
- 索引：`knowledge/CORPUS.md`

```bat
orpath.bat knowledge-sync
orpath.bat knowledge-retrieve --query "polyomino CP-SAT" --mode hybrid --topk 5
```

## 禁止

- solution/validate 最优值当语料权威  
- 「用 corpus 训练了模型」  
- 二进制 PDF 不经预处理直接当 chunk 正文  
