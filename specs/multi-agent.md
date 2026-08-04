# Multi-Agent — 多智能体法（详细）

**对齐：** `product-flow-sdd.md` · `process-visibility.md`  
**状态：** LAW 2026-08-01

---

## 1. 统一接缝（ADR-0005）

产品代码 **只** import **`orpath.subagent_dispatch`**：

| API | 用途 |
|-----|------|
| `live_subagent_enabled` | 是否真 spawn |
| `run_*_subagent_lead` | research/model/cite/review |
| `run_forced_subagent_stage` | anti-cosplay harness |
| `STAGE_AGENTS` / `policy_snapshot` | 阶段→角色 |
| `detect_subagent_calls` / `spawn_lead` | 检测与底层 |

实现分层：`subagent_runtime` · `subagent_harness` · `paper_live_subagent` · `graph_live_subagent`。

---

## 2. 真 MA 四条（不可降级）

演示、M0、closeout 必须能展示：

1. **可检**子轨迹（`.pi-subagents/**` transcript 或等价 + lead log）  
2. **上下文隔离**（research 长文 ≠ modeler 窗；**文件路径手递**）  
3. **显式委派**（json 中 `toolCall`/`toolName`=subagent）  
4. 最终数字仍 **solve + validate**  

### 2.1 Cosplay 定义（FAIL）

| Cosplay | 真 |
|---------|-----|
| 一个 `-p` 长文「扮演 verifier」 | lead 调 subagent 工具 |
| DONE 表只有角色名 | 有 runId + transcript/log |
| 同上下文写 draft+review | 隔离会话 + 路径 |
| 文本「or-verifier produced」无 toolCall | detect 为 false |

---

## 3. Anti-cosplay harness（硬）

| 规则 | 值 |
|------|-----|
| Lead 工具 | **无 write/edit**（`LEAD_TOOLS_NO_WRITE`） |
| 模式 | `--mode json` |
| 检测 | 仅真实 tool 事件 |
| 失败 | quarantine 假产物 → retry（默认 3）→ `gate_subagent_ok=false` |
| 适用站 | cite、review、model；research lead 亦无 write，由 Python 合并 notes |

详见 `docs/anti-cosplay-harness.md`（活文档；冲突以本 specs + 代码为准）。

---

## 4. 角色

路径：`.pi/agents/or-*.md`

| 角色 | 站 | 做 | 不做 |
|------|-----|----|------|
| or-orchestrator | 站内协调（若用） | 拆合、ledger | 抢 LG；心算优 |
| or-researcher | research | 算法/约束/读 retrieval | 写 objective |
| or-modeler | model | ProblemSchema | optimal/tour/routes/path 答案 |
| or-writer | draft 润色可选 | 文稿 | 发明数字 |
| or-verifier | cite | 引用辅助 | 替代 R1 脚本 |
| or-reviewer | review | 语义批评 | 无上限互怼 |

模型：Pi 侧 **DeepSeek only**（默认 **deepseek-v4-flash**；见 `orpath.subagent_runtime` / `.pi/settings.json`）。

---

## 5. 手递纪律

- 大块：`notes/` `outputs/` `papers/`  
- 父会话优先 **路径**  
- plan：`outputs/.plans/<slug>.md`  
- Feynman 同款：prefer file handoffs  

---

## 6. Live vs CI

| | CI / gate | 产品 live |
|--|-----------|-----------|
| `ORPATH_LIVE_SUBAGENT` | **0** | 默认 **1**（unset 时） |
| 制品路径可同 | 确定性写 | 真 spawn |
| 宣称 MA | 否 | 需 toolCall 证据 |

CLI：`--live-subagent` / `--no-live-subagent` / `--live-pi`（耦合 live）。

---

## 7. 启动法（pi_launch_law）

| 模式 | 何时 | 形态 |
|------|------|------|
| SINGLE_LEAD | 脚本重解、可写草稿 | 可含 write；**横幅诚实**；禁称 MA |
| MULTI_AGENT_HARNESS | cite/review/model/research live | tools 含 subagent、**无 write**、json |

裸 `pi -p` + LIVE=1 **≠** MA。  
见 `orpath/pi_launch_law.py`。

---

## 8. Research scale

| scale | 条件 | 行为 |
|-------|------|------|
| off | knowledge off | 无 researcher |
| narrow | seed+SP 等 | 1× researcher |
| wide | hybrid/VRP 等 | 2× 并行，failFast 思想 false |
| 覆盖 | `state.research_scale` | 允许 |

---

## 9. 与「看见 sub 思考」

| 产物 | 谁写 | 可视层 |
|------|------|--------|
| `*-lead-*.log` | spawn | L1 派工 + 可抽 L3 |
| transcript | pi-subagents | L2 主源 |
| harness json | harness | 索引 |

生成时间线：**禁止**只用 lead 散文。  
完整 UX → `process-visibility.md`。

---

## 10. Bridge（历史 T2）

- `orpath/pi_bridge.py` + RPC  
- `ORPATH_LIVE_PI=1`  
- M0 不阻塞若 harness 路径已有真 sub 证据  
- OpenPi 截图 DoD **退役**（壳已删）  

---

## 11. 禁止

- Teams 对等互聊作 OR 核心  
- 消息总线 Agent 社交脊柱  
- cosplay 充 DoD  
- 环境安装走 DeepSeek 通道  

---

## 12. 验收命令

```bat
orpath.bat subagent-gate
:: 期望: M1/M2/M3 glue tokens + PI_LAUNCH_LAW_PASS 等（以脚本输出为准）
```

Live 烟：

```bat
set ORPATH_LIVE_SUBAGENT=1
orpath.bat run --problem-id shortest_path --solve-mode mock --knowledge-mode seed --slug m0-live --fresh
:: grep outputs/.agents/m0-live for "name":"subagent"
orpath.bat timeline --slug m0-live
```
