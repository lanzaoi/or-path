# docs/ — 活文档导航

**原则：** 顶层只放「现在还要读的」。历史关单 / 计划 / 证据 → **`archive/`**。  
产品法在 **`../specs/`**，操作入口在仓库根 **`ORPATH.md`** / **`START-*.bat`**。

## 先跑起来

| 路径 | 用途 |
|------|------|
| **[`install.md`](install.md)** | L1 setup · L2 Release 安装 |
| **[`../ORPATH.md`](../ORPATH.md)** | 日常操作（路径 A · Watch · LIVE） |
| **[`../README.md`](../README.md)** | 仓库总览 |
| **[`../START-CASE.bat`](../START-CASE.bat)** | 路径 A 一键 |
| **[`../START-WATCH.bat`](../START-WATCH.bat)** | 过程脸一键 |

## 活文档（Living）

| 文件 | 用途 |
|------|------|
| **[`ARCHITECTURE.md`](ARCHITECTURE.md)** | 当前产品架构（简洁） |
| **[`repo-surface.md`](repo-surface.md)** | 可上传 / 禁上传边界 |
| **[`OUT_OF_BAND.md`](OUT_OF_BAND.md)** | vendor / pi-main / .hermes 等带外 |
| **[`m2-polyomino.md`](m2-polyomino.md)** | M2 骨牌域桥 |
| **[`solver-stack.md`](solver-stack.md)** | 求解栈 claim（与 specs 配套） |
| **[`v0-smoke.md`](v0-smoke.md)** | Watch / 过程脸冒烟（门禁锚点） |
| **[`p5-closeout.md`](p5-closeout.md)** | P5 过程脸收口（门禁锚点） |
| **[`m0-smoke.md`](m0-smoke.md)** · **[`m1-smoke.md`](m1-smoke.md)** | M0 mock · M1 workdir |
| **[`m1-closeout.md`](m1-closeout.md)** · **[`m2-closeout.md`](m2-closeout.md)** | 近里程碑关单（门禁仍引用） |
| **[`t1-smoke.md`](t1-smoke.md)** · **[`t2-smoke.md`](t2-smoke.md)** · **[`1.1-smoke.md`](1.1-smoke.md)** | 回归冒烟入口 |

## 架构决策（ADR）

| 路径 | 说明 |
|------|------|
| **[`adr/`](adr/)** | ADR-0001…0006（阶段节点、solve/validate、控制面、论文、subagent、文档卫生） |

## 历史（默认不整树加载）

| 路径 | 说明 |
|------|------|
| **[`archive/closeouts/`](archive/closeouts/)** | T1–T3 / 1.x / M0 / P5 / 旧关单 |
| **[`archive/plans/`](archive/plans/)** | 施工单（原 `.hermes/plans`） |
| **[`archive/tickets/`](archive/tickets/)** | 已完成架构票 |
| **[`archive/design-notes/`](archive/design-notes/)** | 设计长文 / OpenPi 退役笔记 / IDEA 草稿 |
| **[`archive/evidence/`](archive/evidence/)** | 截图与 JSON 证据 |
| **[`archive/ops/`](archive/ops/)** · **[`archive/portfolio/`](archive/portfolio/)** | 运维与口播 |

完整索引：[`archive/README.md`](archive/README.md)

## 法条（不在 docs）

| 路径 | 说明 |
|------|------|
| **`../specs/README.md`** | 规格总索引 |
| **`../specs/product-flow-sdd.md`** | 总流程主合同 |
| **`../specs/process-visibility.md`** | 过程可视合同 |
