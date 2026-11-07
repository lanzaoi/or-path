# P5 Closeout · 实时可视五阶段收口

**日期：** 2026-08  
**法：** `specs/process-visibility.md` §11 · `specs/product-flow-sdd.md` §9  
**产品脸：** `orpath.bat watch` / `watch-run`（**不是**开文件夹）

---

## Claim ladder（对外怎么说）

| 可以说 | 不可以说 |
|--------|----------|
| **P1–P3 主路径已交付**：dirty 实时 + sub 轨迹 + 一键边跑边看 | 「可视化早做完了」仅因旧 V0 gate |
| **P4 增强**：`ORPATH_PI_SESSION` + Tier-2 面板 + kanban 文档 | 「必须装 pi-kanban 才算完成」 |
| **P5 增强**：Watch 抛光 + 可选 Langfuse **文档/开关** | 「Langfuse 已全链路埋点并替代 Watch」 |
| thinking **有则显示，无则 `thinking_unavailable`** | 「一定能看到模型内心独白」 |
| mock 联跑 stages 增长 | 「mock 全链 paper R2 必绿」（slug 数字 claim 仍可能红） |

---

## 五阶段完成表

| 阶段 | 状态 | 证据入口 |
|------|------|----------|
| **P1** dirty 脊梁 | ✅ | `watch_snapshot_gate` · `/api/poll` |
| **P2** sub 轨迹 | ✅ | children + transcript · lead/sub 滤 |
| **P3** watch-run | ✅ | `orpath.bat p3-gate` · `*-watch-run.json` |
| **P4** Tier-2 session | ✅ | `orpath.bat p4-gate` · `docs/p4-tier2-deep-look.md` |
| **P5** 抛光 + Tier-3 文档 | ✅ 工程 | `orpath.bat p5-gate` · 本文 · `docs/p5-tier3-langfuse.md` |

---

## P5 交付清单

### 已做

- Watch UI：L0 **timeline/swim**、running **高亮/脉冲**、错误 **红条**、**Follow tail / Pause**  
- 事件 **窗口渲染**（默认 last 80，可 +more）— 大 log 不卡死 DOM  
- 移动端网格可滚；tab hidden 时降频  
- snapshot.`tier3`（`ORPATH_LANGFUSE`）+ 右栏说明  
- 门禁 `scripts/p5_polish_gate.py` / `orpath.bat p5-gate`  
- 演示清单嵌在右栏  

### 明确未做（诚实）

| 项 | 说明 |
|----|------|
| Langfuse **自动 span 埋点** | 仅 env 表面 + 文档；需另任务接 control_plane |
| 云端多租户 / 公网 SaaS 脸 | 不做 |
| 录屏文件入库 | 人工 2–3 分钟按清单录即可 |
| 虚拟列表完整库（react-window 级） | 用服务端 cap + 客户端 window 足够 |

---

## 2–3 分钟演示脚本

```bat
cd /d C:\Users\Lanzao\Desktop\agent
orpath.bat p5-gate
orpath.bat watch-run --slug p5-demo --keep-watch
```

1. 浏览器看 **timeline** 格子变长  
2. 点 **dispatch**，事件区 **sub** 过滤  
3. 右栏 **solution/validate** 路径 + Tier-2/3  
4. 需要细看 Pi：`set ORPATH_PI_SESSION=1` 后再 LIVE（可选）  

---

## 门禁命令

```bat
orpath.bat v0-watch-gate
orpath.bat p3-gate
orpath.bat p4-gate
orpath.bat p5-gate
```

---

## 一句话收口

> **实时可视 S1 主路径（Watch P1–P3）完工；P4 session 桥与 P5 抛光/可选 Langfuse 文档已交付。Langfuse 全自动埋点与 CoT 必现未承诺。**
