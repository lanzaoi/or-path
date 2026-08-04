# docs/ 导航（活文档面）

**原则：** 默认只读本目录顶层 + `adr/` + `tickets/` + 仓库根 `specs/`。  
历史关单/证据/口播进 **`archive/`**，不参与日常导航。

## 先跑起来

| 路径 | 用途 |
|------|------|
| **`../START-CASE.bat`** | 路径 A：本地案例文件夹 + Watch/watch-run |
| **`../START-WATCH.bat`** | 一键过程脸（默认 live-btube） |
| **`../ORPATH.md`** | 操作主说明 |
| **`../README.md`** | 仓库总览 |

## 活文档（Living）

| 路径 | 用途 |
|------|------|
| **`../specs/README.md`** | **法条总索引**（优先于 docs） |
| **`../specs/process-visibility.md`** | **实时过程台硬底线（V0）** |
| **`../specs/product-flow-sdd.md`** | 总流程主合同 |
| **`v0-smoke.md`** | V0 Live Watch 冒烟 |
| **`m0-smoke.md` / `m0-closeout.md`** | M0 证据串 |
| **`m1-smoke.md` / `m1-closeout.md`** | M1 workdir + Watch CTA |
| **`m2-polyomino.md` / `m2-closeout.md`** | **M2 第一域桥 polyomino** |
| **`live-btube-closeout.md`** | 圆管 B LIVE 旁路 |
| `1.0-closeout.md` · `1.1-closeout.md` · `1.2-closeout.md` | 产品关单 |
| `solver-stack.md` | 求解器话术 |
| `anti-cosplay-harness.md` | 反偷懒 harness |
| `t1-smoke.md` / `t2-smoke.md` | 历史冒烟 |
| `adr/` | ADR-0001… |
| `tickets/` | 施工单 |
| `OUT_OF_BAND.md` | vendor / pi-main 带外 |

## B 题全问

| 路径 | 用途 |
|------|------|
| `../scripts/pack_b_polyomino_case.py` | 把全问 JSON/Excel/论文打进案例目录 |
| `../tools/solve_polyomino.py` · `solve_polyomino_q3.py` | CP-SAT 求解 |
| 案例内 `papers/B-polyomino-full-paper.md` | 打包后的完整论文 |
| 案例内 `outputs/b-full/` | 各子问明细 |

单次 `watch-run` 默认只演示 Q1.1；全问用 pack 脚本。

## 归档（Archive）

见 [`archive/README.md`](archive/README.md)。

## 读法

1. 产品法 → `specs/`  
2. 怎么跑 → 根 `README` / `ORPATH.md` / `*-smoke.md`  
3. 架构为什么 → `adr/`  
4. 历史证据 → `archive/`（需要时再开）
