# D3 · Tier-2 深链手测（session · kanban · supervise）

> **状态：** engineering checklist（2026-08-09）  
> **法：** `specs/human-steer-and-pi-guidance.md` §4.2 D3 · `specs/process-visibility.md` P4  
> **脸：** 仍是 Watch。本页 = **可选第二屏**，不是 V0 PASS 条件。

---

## 0. 一句话 DoD

| # | 检查 | 过线 |
|---|------|------|
| 1 | `.pi/settings.json` packages 含 **pi-kanban** + **pi-supervisor** | `pi.bat list` Project packages |
| 2 | snapshot.`tier2` 有 `deep_links` + `package_status` | Watch L4 面板或 curl snapshot |
| 3 | Watch HTML 有 **Tier-2 深链** + Copy cmd | `data-orpath-tier2` |
| 4 | 文档可点：`docs/d3-tier2-deep-link.md` · `docs/p4-tier2-deep-look.md` | 本文件 |
| 5 | 手测：`ORPATH_PI_SESSION=1` 路径写清；默认 0 诚实 `tier2_session_off` | 徽章/说明 |
| 6 | 交互 Pi：`/kanban` · `/supervise` 命令在 deep_links 可复制 | 不强制真开浏览器 |

**不做：** 强制装 kanban 才绿 gate；Watch 内嵌完整 Pi TUI；自动 resume。

---

## 1. 安装核验（一次）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
pi.bat list
```

期望 Project packages 至少：

```text
npm:pi-subagents@…
npm:pi-kanban
npm:pi-supervisor
npm:@juicesharp/rpiv-ask-user-question
```

缺则：

```bat
pi.bat install npm:pi-kanban -l --approve
pi.bat install npm:pi-supervisor -l --approve
pi.bat install npm:@juicesharp/rpiv-ask-user-question -l --approve
```

项目监督规则：`.pi/SUPERVISOR.md`。

---

## 2. Watch 上怎么看见（Tier-1 → Tier-2 出口）

```bat
set PYTHONPATH=
orpath.bat watch --slug live-btube
```

1. 顶栏徽章：**会话 / 无会话**（`ORPATH_PI_SESSION`）  
2. 右栏 **L4 · Tier-2 深链**（`data-orpath-tier2`）：  
   - `sessions_root`  
   - 插件就绪徽章（kanban / supervisor）  
   - recent sessions（若有）  
   - **Copy cmd** 深链（session_on / pi / kanban / supervise）  
3. 说明里可能有 `tier2_session_off`（SESSION=0 时诚实）

curl 自检：

```bat
:: watch 已启动时
curl -s "http://127.0.0.1:8765/api/snapshot?slug=live-btube" | findstr /i "deep_links package_status pi-kanban"
```

---

## 3. 产品 LIVE + session（给 kanban 喂盘）

```bat
set ORPATH_PI_SESSION=1
set ORPATH_LIVE_SUBAGENT=1
orpath.bat watch-run --live --keep-watch --slug tier2-handtest --solve-mode mock
```

| 证据 | 过线 |
|------|------|
| lead log 头 | `pi_session=on` · **无** `--no-session` |
| `~/.pi/agent/sessions/` | 有新 jsonl（路径因机器而异） |
| Watch tier2.recent | 可能出现新 session（扫盘，非实时强保证） |

默认 `ORPATH_PI_SESSION=0`：**不要**声称 kanban 能看产品 lead。

---

## 4. 交互 Pi · kanban / supervise（人工）

```bat
pi.bat
```

```text
/kanban start
/kanban open web
/supervise Prefer exact solve tracks; never invent objective; use solve_dispatch + validate
/supervise sensitivity medium
/supervise status
/supervise stop
```

| 工具 | 用途 | 非用途 |
|------|------|--------|
| **Watch 对话 + human-steer** | 全链航向 / 阶段精要 | 不替代 Pi TUI |
| **kanban** | session/todo/sub 细看 | 不替代 validate 数字 |
| **supervisor** | 交互会话目标监督 | 默认 **不** 挂 headless 产品 lead |

---

## 5. 与 D0–D2 关系

```text
D0 气泡（读盘） ─┐
D1 表单写 steer ─┼─→ Tier-1 Watch 主路径
D2 LG 合并 mode ─┘
D3 深链 ──────────→ Tier-2 Pi 插件（可选）
```

人导换算法：**D1/D2**（`solve_mode`）。  
想盯 sub 原生流 / 目标监督：**D3**。

---

## 6. 门禁

```bat
set PYTHONPATH=
.venv-314\Scripts\python.exe scripts\dialogue_steer_gate.py
.venv-314\Scripts\python.exe scripts\p4_session_gate.py
```

D3 断言落在 `dialogue_steer_gate` 的 `test_d3_tier2_deep_link`（HTML 标记 + snapshot.deep_links + packages 字符串；**不**要求真开 kanban 浏览器）。

---

## 7. 变更

| 日期 | 变更 |
|------|------|
| 2026-08-09 | D3 初版：tier2.deep_links · package_status · Watch 面板 · 本手测册 |
