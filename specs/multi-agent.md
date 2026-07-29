# Multi-Agent — 多智能体法

## 硬要求

演示与 closeout 必须能展示：

1. **≥2** 个子 Agent **可检**独立轨迹（`.pi-subagents/artifacts/*_transcript.jsonl` 或平台等价物）  
2. **上下文隔离**（research 长文 ≠ modeler 上下文）  
3. **显式委派**（subagent 工具），禁止单会话角色扮演  
4. 最终数字仍来自 solve + validate  

## 角色

| 角色文件 | 职责 | 不做 |
|----------|------|------|
| `or-orchestrator` | 节点内拆合、ledger、汇总结论 | 心算最优；抢 LG 阶段 |
| `or-researcher` | 算法/约束/案例；**必须读** retrieval 制品（当 knowledge≠off） | 写 objective |
| `or-modeler` | 出 ProblemSchema | 填 optimal / tour / routes / path 答案 |
| `or-writer` | 论文草稿绑定 solution | 发明数字 |
| `or-verifier` | 引用/结构辅助 | 替代 R1/R2 脚本硬门 |
| `or-reviewer` | 语义批评 | 无上限互怼 |

路径：`.pi/agents/or-*.md`

## 手递纪律

- 大块内容落盘：`notes/`、`outputs/`、`papers/`  
- 父会话优先传 **路径**  
- plan ledger：`outputs/.plans/<slug>.md`  

## Live vs CI

| | CI | Live |
|--|----|------|
| 默认 | 确定性节点写同路径制品 | Pi/OpenPi 真委派 |
| T2 额外 | — | **OpenPi 截图硬 DoD**；bridge 成功证据硬 DoD |

## Bridge（T2 硬 DoD）

- 组件：`orpath/pi_bridge.py` + `pi-py-sdk` / 官方 `pi --mode rpc`  
- 开关：`ORPATH_LIVE_PI=1`  
- 至少 **一个** LG 节点（建议 research 或 model）经 bridge 成功写出制品  
- 失败：不得 closeout；evidence 记录错误（无密钥）  
- CI 默认 `ORPATH_LIVE_PI=0`，但 closeout 清单含一次 =1 成功 run  

## 模型

- Pi/OpenPi：**DeepSeek only**  
- 环境安装与 pip：**非 DeepSeek 通道**（Hermes/用户）

## 禁止

- Agent Teams 对等互聊作 OR 核心  
- 消息总线 Agent 社交层  
- 无 subagent 的「你现在是 modeler」cosplay 充数 DoD  
