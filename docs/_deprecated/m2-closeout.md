# M2 Closeout — polyomino 第一域桥

**日期：** 2026-08-04  
**切片：** M2 Parts 1–5  
**法：** `specs/product-flow-sdd.md` §14 · `specs/solvers-and-validate.md` §8  
**计划指针：** 会话冻结主域 **polyomino**（非 tube 冒充）

---

## 目标 vs 结果

| 目标 | 结果 |
|------|------|
| 注册 `polyomino_cover` + schema 白名单 | **通**（Part1） |
| solve→validate 数字链 | **通** q1 obj=6（Part2） |
| 产品入口 + workdir | **通**（Part3） |
| Watch 可见 + CTA（带 domain flags） | **通**（Part4） |
| paper/cite 演示尽量不卡 HUMAN | **通** R1/R2 烟（Part5） |
| M3 launch / M4 记忆 MCP | **未做**（后置） |

---

## 五段与门禁

| Part | 门禁 |
|------|------|
| 1 | `m2_phase1_contract_gate.py` |
| 2 | `m2_phase2_solve_validate_gate.py` |
| 3 | `m2_phase3_product_workdir_gate.py` |
| 4 | `m2_phase4_watch_cta_gate.py` |
| 5 | `m2_phase5_paper_gate.py` |
| **总装** | **`orpath.bat m2-gate`** → `scripts/m2_gate.py` |

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONPATH=
orpath.bat m2-gate
```

冒烟：`docs/m2-polyomino.md`

---

## Claim ladder

| 可说 | 不可说 |
|------|--------|
| **M2**：polyomino 第一域桥已注册并联通产品链 + Watch | M3 SYSTEM launch / M4 记忆·MCP 已交付 |
| q1 fixture solve+validate 绿；workdir 产物隔离 | 竞赛 B 全卷已交 / 全局最优已证（超规模） |
| paper R1/R2 对 polyomino demo 可绿（LIVE OFF） | LIVE 真 sub 必绿；浏览器自动 resume |
| CTA 可复制且带 `--solve-mode polyomino` | tube LIVE 等于 M2 主叙事 |

---

## 关键路径

```text
orpath/domain_registry.py
orpath/nodes.py                 # modeler/solve/paper cites
orpath/paper_workflow.py        # R2-safe path leaves
orpath/watch_snapshot.py        # CTA domain flags
tools/gate_schema.py
tools/solve_dispatch.py
tools/validate_solution.py      # polyomino recompute
tools/solve_polyomino.py
fixtures/t3/polyomino_b_q1/
scripts/m2_phase*_gate.py
scripts/m2_gate.py
orpath.bat m2-gate
docs/m2-polyomino.md
docs/m2-closeout.md             # 本文
```

---

## 一句话

> **M2 收口：polyomino 作为第一新域完成注册→数字链→workdir 产品跑→Watch/CTA→paper 烟；不宣称 launch/记忆/交卷。**
