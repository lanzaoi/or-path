# Knowledge and Retrieval — 知识与检索

## 管道（T2 竖切必达）

```text
corpus (PDF gitignore + curated md)
  → MinerU Cloud（真 PDF）
  → unified chunks (chunk_id)
       ├─ LightRAG
       └─ BM25 + FTS5（双写同一 chunk_id）
  → RRF fusion → retrieve CLI / LG retrieve 节点
  → notes/<slug>-retrieval.json → or-researcher
  + L4 seed graph
  + L3 Cognee Cloud smoke（非数字源）
```

## knowledge_mode

| 模式 | 行为 |
|------|------|
| `off` | 不检索；research 可用 fixture 说明 |
| `seed` | 仅领域种子图 → `seed_facts` |
| `hybrid` | seed + 向量/词法融合 hits |

`t2_gate`：**至少 seed 常绿**。  
`t2_gate_cloud`：**hybrid + MinerU + Cognee** 必绿（本机交付）。

## L4 种子图

- 路径：`knowledge/seed_graph/or_domain_seed.json`  
- 节点类型：`ProblemClass`、`Constraint`、`Solver`、`Case`  
- 必须覆盖：shortest_path、tsp、vrp 与 networkx/ortools 关系  
- CLI：`knowledge_svc.seed_graph_query`  

## MinerU Cloud（Q8-B）

- 真 PDF 走 Cloud API（`MINERU_API_TOKEN`）  
- 另备 1–2 篇 curated `.md` 可同管道入库  
- 输出：`knowledge/mineru_out/<doc_id>/`（gitignore）  
- 再切成 chunks JSONL  
- **禁止**默认本地下载多 GB MinerU 模型  

## Embedding

- 硅基 OpenAI-compatible：`BAAI/bge-m3`，维度 **1024**  
- `SILICONFLOW_API_KEY` / `SILICONFLOW_BASE_URL`  
- base URL **不含** `/embeddings` 叶子路径  

## LightRAG + 词法 + RRF

- 只索引 **预处理后** chunks  
- BM25（`rank_bm25`）与 SQLite FTS5 双写 `chunk_id`  
- RRF：默认权重 `w_semantic=1.0`，`w_lexical=0.4`（可配）  
- 空命中：返回 `hits: []`，Researcher **不得**伪造 cite  

## Researcher 消费（硬）

当 `knowledge_mode != off`：

1. 必须读取 `notes/<slug>-retrieval.json`（或 state 中路径）  
2. 笔记中的引用应能映射到 `chunk_id` 或 seed 节点 id  
3. R1 本地轨：whitelist ∪ retrieval 中的 source/chunk 标识  

## Cognee Cloud

- 配置：`COGNEE_API_KEY`、`COGNEE_BASE_URL`  
- T2：write 一条 lesson + search smoke  
- **禁止**写入 authoritative `objective` / tour / routes  
- solve 路径 **不得**从 Cognee 读数字真相  

## Claim ladder（文档/简历）

| 可写 | 不可写 |
|------|--------|
| 预处理解耦 + 混合检索供研究 | LightRAG 精通生 PDF 公式 |
| chunk 级可追溯引用 | 已达某公开 RAG 榜 SOTA |
| Cognee 作跨任务记忆 smoke | Cognee 保证最优解 |

## 评测

- T2 **不做**自建 OR 术语 MRR 黄金集（Q7-B）  
- 验收 = smoke + 契约 + research 消费检索制品  

## 密钥

- 仅 `.env`（gitignore）；evidence 打码  
- 不得把 token 写入 specs/plan/docs  
