# OR-Path：OpenPi / GUI 主控（默认多 Agent + 审题）

**Hermes 不是产品运行时。** 你打开本仓库 + OpenPi 操控。

## 默认策略（已批准）

| 项 | 默认 | 关闭 |
|----|------|------|
| **Live 多 Agent** | **ON**（`ORPATH_LIVE_SUBAGENT=1`） | `set ORPATH_LIVE_SUBAGENT=0` 或 `run --no-live-subagent` |
| **Intake 审题** | 有 `--intake-in` 或 `inbox/` 文件时 **ON** | 无题面 → skip（fixture 演示） |
| **CI / 门禁** | 强制 live **OFF** | `orpath.bat gate*` 已设 0 |

**裸 OpenPi 聊天 ≠ 多 Agent。** 必须跑产品图（下面命令），磁盘上才有 `name:subagent`。

## 开箱 3 步（无 Hermes）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
orpath.bat doctor
orpath.bat openpi
```

另开终端：

```bat
cd /d C:\Users\Lanzao\Desktop\agent

:: A) 最快看 intake + 全链壳（mock solve；LIVE=1 会 spawn 子 Agent，费钱）
orpath.bat gui-demo

:: B) 自己的题：复制到 inbox\ 后
copy path\to\题面.pdf inbox\
orpath.bat run-full --slug my-contest --thread-id my-contest --solve-mode mock
```

## 证据在哪（自证，不信口头）

| 要验 | 路径 |
|------|------|
| 审题 | `outputs\<slug>-intake.json` · `notes\*-problem-brief.md` |
| 真 subagent | `outputs\.agents\<slug\>\*-lead-*.log` 搜 `"name":"subagent"` |
| 阶段机 | `runs\<thread-id>\stages\` |
| 关 live | 日志应出现 skip / 无 lead spawn |

## OpenPi 里怎么用

1. **Project 打开安装根**（`ORPATH_HOME`，即本仓）。  
2. 终端跑 `orpath.bat …`（上表）；聊天窗口可用来读 `notes/` / 改 brief，**不要**靠角色扮演代替 `run`。  
3. 成本：LIVE=1 会调 DeepSeek + pi-subagents；演示可用 mock solve，但子 Agent 仍贵 → 调试可 `set ORPATH_LIVE_SUBAGENT=0`。

## 和「关单 PASS」的关系

- 门禁绿 = 契约/快路径。  
- **GUI 成功 = 你在无 Hermes 下跑通上表并看到证据。**  
- 详见 `docs/OPENPI-DEFAULT-MA-INTAKE.md`。
