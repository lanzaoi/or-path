# V0 Live Watch 冒烟

**目的：** 确认产品脸入口可用（读盘聚合 + 本机页），**不是**全链路做题验收。  
**法：** `specs/process-visibility.md` §0/§6/§11 · `specs/product-flow-sdd.md` §9.0  

---

## 主路径 P3：一条命令边跑边看（推荐）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
orpath.bat p3-gate
orpath.bat watch-run
:: 或指定 slug 并保留页面：
:: orpath.bat watch-run --slug p3-demo --keep-watch
```

**期望（≤5 分钟）：**

1. 本机浏览器打开 Live Watch（除非 `--no-browser`）  
2. mock 产品图在跑；**本 slug** 的 L0 stages **从 0 变长**  
3. 证据：`outputs/<slug>-watch-run.json` 里 `stages_grew=true`、`ok=true`  
4. **不**依赖历史 `test` slug 当唯一证据  

可选 LIVE（慢、需 Pi）：

```bat
orpath.bat watch-run --slug p3-live --live --keep-watch
```

menu：**7) Watch-run — 边跑边看 P3**

---

## 只看脸（不跑题）

```bat
orpath.bat doctor
orpath.bat v0-watch-gate
orpath.bat watch --slug test
```

浏览器约 **1s** dirty 轮询（P1）：

- **L0** 阶段列表非空（`runs/test/stages` 存在时）  
- footer：**fp / stages / events / +N / cursors**  
- **L1** 若有 lead log：research/model 等派工；**children + transcript**（P2）  
- 事件区 **all / lead / sub** 过滤  
- **L3** `thinking` 有或 `thinking_unavailable`  
- **L4** 产物路径 / counters  

### P1 增量脊梁

| 能力 | |
|------|--|
| `GET /api/poll` | 指纹 dirty，不 parse lead |
| `GET /api/snapshot?prev_fp=&prev_events=` | 全量 + `poll.events_added` |
| `GET /api/stream` | SSE 可选 |
| 前端 | 1s 先 poll，dirty 才 snap |

### P2 Sub 过程

| 能力 | |
|------|--|
| dispatch.`children[]` | agent / transcript_path / tool_count |
| events.`source` | `lead` \| `sub` |
| snapshot.`process` | event_kinds / sub_events / children_count |
| UI | 子节点树 + all/lead/sub 过滤 |

### P3 一键联跑

| 能力 | |
|------|--|
| `orpath.bat watch-run` | 起 watch + mock run + 证 L0 增长 |
| `outputs/*-watch-run.json` | 机读证据 |
| `orpath.bat p3-gate` | 门禁 |

### P4 Tier-2（Pi session）

| 能力 | |
|------|--|
| `ORPATH_PI_SESSION=1` | product lead 写 Pi session |
| snapshot.`tier2` | sessions_root / recent / kanban_hint |
| 文档 | `docs/p4-tier2-deep-look.md` |
| `orpath.bat p4-gate` | session 开关 + UI 门禁 |

### P5 抛光 + Tier-3 文档

| 能力 | |
|------|--|
| timeline / follow / pause / err banner | Watch UI |
| 事件窗口渲染 | 默认 last 80 |
| `tier3` + `ORPATH_LANGFUSE` | 可选表面（不替脸） |
| closeout | `docs/p5-closeout.md` |
| `orpath.bat p5-gate` | 门禁 |

## 两终端手拧（后备，非主路径）

终端 A：`orpath.bat watch --slug m0-watch-demo`  
终端 B：`orpath.bat run --fresh --slug m0-watch-demo ... --no-live-subagent`

## 门禁

| 命令 | 查什么 |
|------|--------|
| `python scripts/watch_snapshot_gate.py` | P1+P2 聚合 |
| `python scripts/v0_watch_gate.py` | 文档入口 + HTML + HTTP |
| `python scripts/p3_watch_run_gate.py` | **P3 联跑 L0 增长** |
| `python scripts/p4_session_gate.py` | **P4 session 开关 + tier2** |
| `python scripts/p5_polish_gate.py` | **P5 UI + tier3 文档** |
| `orpath.bat v0-watch-gate` / `p3-gate` / `p4-gate` / `p5-gate` | bat 封装 |

## 负例（台面应诚实）

| 情况 | 期望 |
|------|------|
| 不存在的 slug | `status=no_product_run`，不装全链 |
| `ORPATH_LIVE_SUBAGENT=0` | 顶栏 LIVE off |
| cosplay（无 toolCall） | 不显示假成功 sub |
| 只开文件夹 | **不等于** V0/P3 PASS |
| 只用历史 test 当 LIVE 证据 | **不等于** P3 PASS |

## 不算 PASS

- 仅 gate 绿、仅 folder、仅事后 md、仅 Hermes 贴 log  
- 无 `watch-run` 却宣称「实时可视化主路径完成」  

## 相关

- 实现：`orpath/watch_snapshot.py` · `scripts/orpath_watch.py` · `scripts/orpath_watch_run.py` · `orpath/web/watch.html`  
- 操作总览：`ORPATH.md`  
- 法：`specs/process-visibility.md` §11  
