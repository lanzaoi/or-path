# docs/ 导航（活文档面）

**原则：** 默认只读本目录顶层 + `adr/` + `tickets/` + `specs/`（仓库根）。  
历史关单/证据/口播进 **`archive/`**，不参与日常导航。

## 活文档（Living）

| 路径 | 用途 |
|------|------|
| **`../specs/README.md`** | **法条总索引**（优先于 docs） |
| `1.0-closeout.md` | 产品 1.0 关单总览 |
| `architecture-refactor-status.md` | 架构整理 #1–#6 进度 |
| `solver-stack.md` | 求解器组合与话术（claim ladder） |
| `anti-cosplay-harness.md` | 反偷懒 harness 说明 |
| `t1-smoke.md` / `t2-smoke.md` | 冒烟操作 |
| `t3-stage-map.mmd` | 产品阶段图（门禁 `t3_lg_gate` 依赖） |
| `adr/` | 架构决策 ADR-0001… |
| `tickets/` | 施工单 |
| `OUT_OF_BAND.md` | vendor / openpi / pi-main 带外说明 |

## 归档（Archive）

见 [`archive/README.md`](archive/README.md)。

| 子目录 | 内容 |
|--------|------|
| `archive/closeouts/` | T1/T2/T3/paper 历史关单 |
| `archive/evidence/` | 证据摘要、截图、live meta |
| `archive/portfolio/` | 口播稿 |
| `archive/design-notes/` | M1–M3 / Feynman 设计笔记 |
| `archive/ops/` | 可搬迁、OpenPi 隔离 howto 等 |

## 读法

1. 产品法 → `specs/`  
2. 怎么跑 → `*-smoke.md` + `orpath.bat`  
3. 架构为什么这样 → `adr/`  
4. 历史证据 → `archive/`（需要时再开）
