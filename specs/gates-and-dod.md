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
- [ ] **OpenPi GUI 截图** 入 `docs/archive/evidence/`（或约定目录）  
- [ ] 三类 R2 路径  
- [ ] 在线 R1 绿  
- [ ] `docs/archive/closeouts/t2-closeout.md` 写明 PASS  
- [ ] 无密钥进 git  
- [ ] claim ladder 诚实  

## 非门禁（T2）

- Docker compose up  
- K8s 集群  
- 自建 OR MRR 评测集  
- 时间窗 VRP  

## Evidence 文档

- `docs/t2-smoke.md` — 操作  
- `docs/archive/evidence/t2-evidence.md` — 命令输出摘要、截图路径、transcript 指针  
- `docs/archive/portfolio/t2-portfolio-talk.md` — 口播  
- `docs/archive/closeouts/t2-closeout.md` — 关单  

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

## 1.1 Problem Intake（2026-07-30 freeze）

权威全文：`specs/problem-intake.md`。  
**不重开** T1/T2/T3/1.0 DoD。

| ID | 锁 |
|----|-----|
| F1 | 1.1 = OCR + 自主审读 brief/intake.json |
| F2 | OCR 主序 pdf_text → paddle → manual_stub；MinerU ≠ 题面主路径 |
| F3 | intake 禁 solution 键；数字只认 solve+validate |
| F4 | 子问全覆盖 + 歧义外显 |
| F5 | 最小 DoD **不强制** LG 挂载 / OpenPi UI |
| F6 | 竞赛建议 `human_confirm_intake`；CI 可 skip_intake |

### 1.1 门禁

| 脚本 | 内容 |
|------|------|
| `scripts/intake_gate.py` | OCR stub、parse 契约、禁键负例、子问覆盖 |
| 回归 | `t1_gate` + `t3_lg_gate` 必须仍绿 |

### 1.1 CLOSED 硬清单（摘要）

- [ ] `intake_gate` PASS  
- [ ] t1_gate + t3_lg_gate PASS  
- [ ] 至少一条真实图/PDF smoke（证据可打码）  
- [ ] closeout 文档 + 诚实 claim ladder  
- [ ] 无大 PDF/密钥进 git  

## 1.2 Architecture Soak（2026-07-31 freeze）

权威全文：`specs/1.2-architecture-soak.md`。  
**不重开** T1/T2/T3/1.0/1.1 DoD。  
**不是** C 题交卷 PASS；**不是** 零售产品扩类。

| ID | 锁 |
|----|-----|
| 主测 | 杭电 2025 美珈羽杯新生赛 **C 题**（服装·优衣库 xls） |
| 回退 | 圆管 B2026；回退时 **亦不接** 既有 tube solve 出数（对照壳） |
| 父边界 | **Pi-only**（Hermes=OCR/拉起/监控） |
| 拓扑 | 产品 LG 全图；`problem_id` 可借 SP 壳；禁金标冒充 C 题 |
| solve | 无 C adapter → **诚实 FAIL**；FAIL 后仍跑 paper 壳（R2/provenance BLOCKED） |
| live MA | research + model + cite + review **全硬** |
| 时盒 | 总 45–60 min；单 lead 12–15 min |
| PASS | 架构证据包（intake + 诚实 FAIL + MA 轨迹 + 监控报告） |

### 1.2 与 CI

- 确定性门禁保持 `ORPATH_LIVE_SUBAGENT=0`；1.2 live soak **不**塞进 t1/t3 默认绿条件  
- 回归：既有 `t1_gate` / `t3_lg_gate` / `intake_gate` 不得无故变红  
