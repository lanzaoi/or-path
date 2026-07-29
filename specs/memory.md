# Memory — 记忆分层

## 总法

**OR-Path 产品记忆 ≠ Hermes MEMORY.md**

| 层 | 归属 | 内容 | T2 |
|----|------|------|-----|
| **L0 工作记忆** | 磁盘 `outputs/` `notes/` `papers/` `fixtures/` + plan ledger | 过程与制品真相 | **必** |
| **L1 Run** | LangGraph checkpointer `runs/` | 阶段、计数器、路径 | **必** |
| **L2 prefs** | `@samfp/pi-memory` 项目 `.pi/memory/` | 习惯、教训、偏好 | **必做安装与 smoke（Q14-B）** |
| **L3** | Cognee Cloud | 跨任务图记忆 smoke | **必 smoke** |
| **L4** | 种子图 | 领域结构 | **必** |
| — | Hermes MEMORY | 仅导航 Agent | **非产品** |
| — | Hindsight | 与 Cognee 重叠 | **非 T2 目标** |

## 禁止写入（所有 L2/L3）

下列不得作为 **authoritative** 记忆写入 pi-memory 或 Cognee：

- `objective` / `optimal_*`  
- 最终 `path` / `tour` / `routes` 充数「标准答案」  
- 完整 solution.json 当唯一真相源  

若讨论中提到数字，必须同时指向 **磁盘 solution 路径**；续跑以文件为准。

## Pi Session

- 压缩（compaction）不可靠保存精确坐标/容量  
- 关键数进 schema/solution/state，不进闲聊记忆  

## pi-memory 配置要点

- project-local path：`.pi/memory/`（db gitignore）  
- consolidation 模型：DeepSeek  
- 用途示例：「用户偏好 mock 默认」「VRP 必须多车」类教训  

## Cognee

- 见 `knowledge-and-retrieval.md`  
- 与 pi-memory **分工**：Cognee 偏跨任务图；pi-memory 偏会话偏好  
- 禁止双写 objective 到两边  

## 检查清单

- [ ] README/AGENTS 不声称 Hermes 为产品记忆  
- [ ] memory smoke 不断言数字最优  
- [ ] provenance 仍指向 solution 文件  
