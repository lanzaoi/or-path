# Gates and DoD — 门禁与完成定义（详细）

**对齐：** `product-flow-sdd.md`  
**状态：** LAW 2026-08-01  
**原则：** 历史里程碑 DoD **不重开**；**当前产品最高 DoD = M0**（总流程 §9）

---

## 0. 门禁总原则

1. 门禁非 0 → 不得宣称对应里程碑 PASS  
2. 一切 `gate*` / CI：**强制** `ORPATH_LIVE_SUBAGENT=0`  
3. `HUMAN_REQUIRED` 是可证路径，不是静默成功  
4. **门禁绿 ≠ M0 Demo 完成**（禁止再混淆）  
5. 环境：`PYTHONNOUSERSITE=1`，清 `PYTHONPATH`  

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONNOUSERSITE=1
set PYTHONPATH=
set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
```

---

## 1. 当前产品 DoD：V0 + M0

权威：`product-flow-sdd.md` §9 + **`process-visibility.md` §0 / §9（S1）**。

| 层级 | 内容 |
|------|------|
| **选型** | **S1 已冻结并工程收口 P1–P5**（见 `docs/p5-closeout.md`）；Langfuse 全自动 span **未**做 |
| **V0/P3** | `orpath.bat watch` + **`watch-run`** 本机实时主路径 |
| **M0** | V0 + solution/validate + 真 sub 证据 |

**在 V0 实现完成前：** 不得在 README 宣称「可视化 / 实时多 Agent 体验已交付」。  
静态 timeline.md、打开文件夹、仅 gate 绿、仅选型写进 specs → **均不够**。

---

## 2. T1（冻结 CLOSED/PASS）

- 命令：`scripts/t1_gate.py`  
- **不重开 DoD**；回归红必须先修  

---

## 3. T2 Grill Freeze（历史）

| ID | 锁 |
|----|-----|
| 拓扑 | LG 阶段；Pi 站内；gate 硬 |
| Q1 | 原含 OpenPi 截图硬 — **截图 DoD 退役**（壳已删）；隔离/gate 仍有效 |
| Q3 | t2_gate ∥ t2_gate_cloud |
| Q4 | bridge 硬证（历史） |
| Q5/6 | TSP n=8；VRP≥2 无 TW |
| Q12/13 | tune≤3 → model≤2 → HUMAN |
| Q14 | 记忆分层：Skill 战法主轴；pi-memory prefs；Cognee smoke 旁路；禁 objective |

### 命令

```bat
.venv-314\Scripts\python.exe scripts\t1_gate.py
.venv-314\Scripts\python.exe scripts\t2_gate.py
.venv-314\Scripts\python.exe scripts\t2_gate_cloud.py
```

默认 `t2_gate.py` 在无模型密钥的干净克隆上校验已归档的 T2 关闭证据；输出必须明确标记 `current_live_run=false`。严格的当前机器多代理隔离证据由 `orpath.bat isolation` 单独检查，它只接受本地 `.pi-subagents/artifacts/` 中的真实 transcript，缺失时必须失败。

### T2 硬清单（历史关单用）

见 `docs/archive/closeouts/t2-closeout.md`。OpenPi 截图项 **不再作为活 DoD**。

---

## 4. T3

权威：`t3-lg-skeleton.md`。

| 脚本 | |
|------|--|
| t3_lg_gate.py | 拓扑/CP/resume/脏/owner |
| t3_gate.py | 业务矩阵含 vrp_tw |
| t3_gate_live.py | live 分轨 |

```bat
orpath.bat gate-t3
```

---

## 5. Subagent / Paper / Intake

| 脚本 | |
|------|--|
| subagent_gate.py | M1/M2/M3 glue + launch law |
| paper_gate.py / paper_1_0_gate.py | 论文协议 |
| intake_gate.py | 1.1 |

```bat
orpath.bat subagent-gate
orpath.bat paper-gate
orpath.bat paper-1.0-gate
orpath.bat gate-intake
```

---

## 6. 1.1 Intake（历史 CLOSED）

全文：`problem-intake.md`。  
回归：intake_gate + t1 + t3_lg。

OCR 宣称就绪：图像 fixture 上 backend **非 placeholder**。

---

## 7. 1.2 Soak（历史工程 PASS）

全文：`1.2-architecture-soak.md`。  
**不是**交卷 PASS。  
PASS = 架构证据包（intake + 诚实 FAIL/BLOCKED + MA 轨迹 + 监控）。

---

## 8. 产品默认 vs CI

| 项 | 产品 | CI/gate |
|----|------|---------|
| LIVE subagent | 默认 ON | 强制 OFF |
| Intake | 有源才开 | 常 skip |
| 主控 | menu | 脚本 |

裸 Pi ≠ MA。

---

## 9. 失败语义

| 现象 | 解释 |
|------|------|
| exit 2 menu | run 失败如实 |
| HUMAN_REQUIRED | 计数器用尽 |
| BLOCKED solution | 无 adapter 或必需源数据缺失时诚实停止 |
| gate 绿 only | 工程回归，非用户 Demo |

---

## 10. Evidence 文档位置

- 活：`docs/*-smoke.md`、`docs/README.md`  
- 历史：`docs/archive/closeouts/`、`docs/archive/evidence/`  

---

## 11. 变更记录

| 日期 | |
|------|--|
| 2026-08-01 | 全册重写：M0 置顶；OpenPi 截图退役；与总流程对齐 |
