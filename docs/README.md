# docs/ 导航（活文档面）

**原则：** 默认只读本目录顶层 + `adr/` + `tickets/` + `specs/`（仓库根）。  
历史关单/证据/口播进 **`archive/`**，不参与日常导航。

## 活文档（Living）

| 路径 | 用途 |
|------|------|
| **`../ORPATH.md`** | **主控 + Live Watch 操作：默认 live MA + intake + 实时过程台** |
| **`OPENPI-DEFAULT-MA-INTAKE.md`** | 开箱默认策略与人测封条 |
| **`../specs/README.md`** | **法条总索引**（优先于 docs） |
| **`../specs/process-visibility.md`** | **实时过程台硬底线（V0）** |
| `1.0-closeout.md` | 产品 1.0 关单总览 |
| **`1.1-closeout.md`** | **1.1 题面 intake 关单** |
| `1.1-smoke.md` | 1.1 操作冒烟 |
| **`1.2-closeout.md`** | **1.2 架构 soak 关单**（真题 intake→LG→BLOCKED + residual） |
| `architecture-refactor-status.md` | 架构整理 #1–#6 进度 |
| `solver-stack.md` | 求解器组合与话术（claim ladder） |
| `anti-cosplay-harness.md` | 反偷懒 harness 说明 |
| **`harness-ideal-on-lcc-skeleton.md`** | **理想目标套 Learn Claude Code 骨架**（心智/作品集讲法，非法） |
| **`v0-smoke.md`** | **V0 Live Watch 冒烟** |
| **`m0-smoke.md`** | **M0 demo-m0 证据串冒烟** |
| **`m1-smoke.md`** | **M1 workdir + Watch 加厚冒烟** |
| **`m1-closeout.md`** | **M1 收口（路径合同 + CTA）** |
| **`live-btube-closeout.md`** | **圆管 B LIVE 收口（tube validate）** |
| **`m0-closeout.md`** | **M0 工程切片关单（诚实边界）** |
| `t1-smoke.md` / `t2-smoke.md` | 冒烟操作 |
| `t3-stage-map.mmd` | 产品阶段图（门禁 `t3_lg_gate` 依赖） |
| `adr/` | 架构决策 ADR-0001… |
| `tickets/` | 施工单 |
| `OUT_OF_BAND.md` | vendor / openpi / pi-main 带外说明 |
| **`../specs/problem-intake.md`** | **1.1 题面 OCR + 自主审读（法条）** |
| **`../specs/1.2-architecture-soak.md`** | **1.2 soak 法条** |
| **`1.1-smoke.md`** | **1.1 操作冒烟**（`intake_gate` / OCR→parse） |

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
