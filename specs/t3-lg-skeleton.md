# T3 — LangGraph Product Skeleton（详细）

**Grill freeze:** 2026-07-29  
**主轴：** LG 产品骨架完整  
**对齐：** `product-flow-sdd.md` · `control-plane.md`  
**状态：** 2026-08-01 重写排版；freeze 锁不重开

---

## 1. Freeze 表

| ID | 锁 |
|----|-----|
| Q1 DoD | E — 骨架+叶+bridge+portfolio（OpenPi 截图项 **退役**） |
| Q2 图 | B 厚 — graph_product + run_orpath |
| Q3 CP | C — Sqlite + stage snapshot + status/resume/list |
| Q4 Resume | D — 严格续跑 + from-stage + 脏检 |
| Q5 阶段 | C — 全表 + bridge + snapshot |
| Q6 矩阵 | D — SP/TSP/VRP/tw + hybrid + live 可分轨 |
| Q7 门禁 | D — t3_lg ∥ t3 ∥ live；图导出 diff 节点 |
| Q8 Bridge | D — live 硬失败；默认 research 前 |
| Q9 脏检 | D — artifact_hashes 全量 |
| Q10 作品集 | D — closeout 等；OpenPi 截图取消 |
| Q11 谁写 | D — 骨架禁双写 |
| Q12 OUT | D — codegen/Teams/bus/Graphiti/K8s 硬/重开 T1T2 |
| Q13 启动 | C — orpath.bat run\|status\|resume\|list\|gate-t3 |
| Q14 Owner | D — assert + 测 |
| Q15 节点 | D′ — nodes.py 权威 |
| Q16 旧 gate | C′ — t1/t2 走产品图 |

---

## 2. 产品入口

| 组件 | 路径 |
|------|------|
| 拓扑 | graph_product.py |
| 控制面 | control_plane.py |
| 节点 | nodes.py |
| CLI | run_orpath.py |
| 导出 | stage_map.json · docs/t3-stage-map.mmd |
| CP | runs/orpath.sqlite |
| 快照 | runs/<thread>/stages/*.json |

---

## 3. 阶段（含 1.1 后）

逻辑上在 T3 基表前可插入 intake_ocr/intake_parse。  
cite_pack 为真实节点。  
**PRODUCT_NODES 数量以代码与 t3_lg_gate 为准（约 17）。**

每个节点退出：stage snapshot + manifest hash。

---

## 4. 数字 / owner

objective 等仅 solve。  
NodeContext 拒非 solve 写数字。

---

## 5. 门禁

```bat
set PYTHONNOUSERSITE=1
orpath.bat gate-t3
.venv-314\Scripts\python.exe scripts\t3_lg_gate.py
.venv-314\Scripts\python.exe scripts\t3_gate.py
```

---

## 6. 与 M0

T3 骨架 **服务** M0；M0 额外要 timeline + 用户入口叙事。  
不因 t3_lg 绿宣称 M0 PASS。

---

## 7. 非目标

见 Q12；不重开 T1/T2 DoD。  
