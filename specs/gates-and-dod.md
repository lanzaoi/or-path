# Gates and DoD — 门禁与完成定义

## T1（冻结）

- 状态：**CLOSED / PASS**（2026-07-29）  
- 命令：`scripts/t1_gate.py`  
- **不重开 DoD**；回归红必须先修到绿再继续 T2 功能  

## T2 Grill Freeze（2026-07-29 确认）

| ID | 锁 |
|----|-----|
| 拓扑 | LG 阶段老板；Pi 节点内包工头；gate 硬审核 |
| Q1 | DoD **C**：本地 gate + cloud 轨 + live 多 Agent + **OpenPi 截图硬** |
| Q2 | specs 树 **B** |
| Q3 | 云分轨 **B**：`t2_gate` ∥ `t2_gate_cloud` |
| Q4 | LG↔Pi bridge **硬 DoD A** |
| Q5/6 | TSP n=8；VRP ≥2 车+容量；**无 TW** |
| Q7 | 知识竖切 **B** 进 research |
| Q8 | 真 PDF MinerU **B** |
| Q9 | Hermes 实现 **A** |
| Q10 | 三类 R2 + live writer + **在线 R1 C** |
| Q11 | 在线 R1 在 cloud/online 轨 **B** |
| Q12 | validate 红 → **调参重解 C** |
| Q13 | 调参≤3 → model≤2 → HUMAN **B** |
| Q14 | pi-memory + Cognee **B**；禁 objective |
| Q15 | **无** Compose/K8s 硬交付 **A** |
| Q16 | specs 中文+英文标识 **B** |
| Q17 | 无 `.agents/`；AGENTS 指针 **B** |

## 门禁脚本（目标形状）

| 脚本 | 内容 |
|------|------|
| `scripts/t1_gate.py` | 保持 |
| `scripts/t2_gate.py` | 本地：pytest 契约/求解/validate/R2 三类；seed；`run_t2` mock+ortools；negatives；**不强制**外网 |
| `scripts/t2_gate_cloud.py` | MinerU、硅基 retrieve hybrid、Cognee、**R1 在线**；`T2_REQUIRE_CLOUD=1` |
| `scripts/t2_negatives.py` | 篡改/坏 schema/HUMAN_REQUIRED 天花板等 |

本机交付默认：

```bat
set PYTHONNOUSERSITE=1
set T2_REQUIRE_CLOUD=1
.venv-314\Scripts\python.exe scripts\t1_gate.py
.venv-314\Scripts\python.exe scripts\t2_gate.py
.venv-314\Scripts\python.exe scripts\t2_gate_cloud.py
```

## T2 CLOSED 清单（硬）

- [ ] `t1_gate` PASS  
- [ ] `t2_gate` PASS  
- [ ] `t2_gate_cloud` PASS  
- [ ] SP networkx/mock + validate  
- [ ] TSP ortools n=8 + validate  
- [ ] VRP multi-vehicle ortools + validate  
- [ ] 调参阶梯或 negatives 证明天花板  
- [ ] 知识：seed + hybrid 消费于 research  
- [ ] MinerU 真 PDF 证据（打码）  
- [ ] Cognee smoke  
- [ ] pi-memory smoke  
- [ ] **Bridge** 一次成功（`ORPATH_LIVE_PI=1`）证据  
- [ ] Live multi-agent transcripts 路径记录  
- [ ] **OpenPi GUI 截图** 入 `docs/t2-evidence.md`（或约定目录）  
- [ ] 三类 R2 路径  
- [ ] 在线 R1 绿  
- [ ] `docs/t2-closeout.md` 写明 PASS  
- [ ] 无密钥进 git  
- [ ] claim ladder 诚实  

## 非门禁（T2）

- Docker compose up  
- K8s 集群  
- 自建 OR MRR 评测集  
- 时间窗 VRP  

## Evidence 文档

- `docs/t2-smoke.md` — 操作  
- `docs/t2-evidence.md` — 命令输出摘要、截图路径、transcript 指针  
- `docs/t2-portfolio-talk.md` — 口播  
- `docs/t2-closeout.md` — 关单  

## 失败语义

- 任一门禁非 0 → 不得宣称 T2 PASS  
- `HUMAN_REQUIRED` 是 **预期可证** 路径，不是静默成功  

## T3 LG Skeleton Grill Freeze（2026-07-29）

权威全表：`specs/t3-lg-skeleton.md`。

| ID | 锁 |
|----|-----|
| 主轴 | LG 产品骨架完整 |
| Q1 | DoD **E** |
| Q2 | `graph_product` + `run_orpath` **B** |
| Q3–Q16 | 见 `t3-lg-skeleton.md` |

### T3 门禁

| 脚本 | 内容 |
|------|------|
| `scripts/t3_lg_gate.py` | 拓扑/checkpointer/resume/脏检/owner |
| `scripts/t3_gate.py` | 业务矩阵（含 vrp_tw） |
| `scripts/t3_gate_live.py` | live bridge 分轨（可选） |

### T3-mini CVRPTW 叶

- Spec: `specs/t3-vrp-tw.md`；fixture gold objective **58**  
- 挂在 T3 矩阵，不单独当 T3 标题  
