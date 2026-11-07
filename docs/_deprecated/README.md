# `_deprecated/` — 废弃备份文档区

本目录存放从 `docs/` 根目录移除的旧任务文档，**仅作历史备份，不再维护**：

- 内容可能与现行架构（v1.0.0：4 核心代理 + 确定性 Python 闸门 + DomainCartridge）脱节
- **不得**作为现行规范、契约或决策依据引用
- 引用时请指向 `docs/` 根目录的现行文档，或 `docs/archive/`
- 如需恢复任何文件，须经人工审阅后移回并更新引用

## 归档清单（2026-11-07）

| 文件 | 原用途 |
|------|--------|
| `1.1-smoke.md` | 任务 1.1 收口 smoke |
| `OUT_OF_BAND.md` | 带外说明 |
| `d3-tier2-deep-link.md` | D3 Tier-2 深链设计 |
| `d4-dialogue-e2e.md` | D4 对话 E2E 收口 |
| `m0-smoke.md` | M0 demo smoke |
| `m1-smoke.md` / `m1-closeout.md` | M1 子代理运行 smoke / 收口 |
| `m2-polyomino.md` / `m2-closeout.md` | M2 多联骨牌专项设计 / 收口 |
| `p4-tier2-deep-look.md` | P4 Tier-2 深看 |
| `p5-closeout.md` / `p5-tier3-langfuse.md` | P5 收口 / Langfuse Tier-3 |
| `t1-smoke.md` / `t2-smoke.md` | T1 / T2 smoke |
| `tube-collaboration.md` / `tube-optimization-plan.md` / `tube-optimization-v2.md` | 圆管套裁协作与算法设计稿 |
| `v0-smoke.md` | Live Watch v0 smoke 契约 |
| `vrp-public-baseline.md` | VRP 公开基线复现说明 |

> 注意：`scripts/` 中 m0/m1/m2/p3/p5/v0/dialogue 闸门脚本仍会校验本目录文件的存在与关键内容（路径已更新），属历史回归闸门，非现行规范。
