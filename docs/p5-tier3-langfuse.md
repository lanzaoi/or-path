# P5 · Tier-3 Langfuse（可选 · 不替脸）

**脸永远是 Watch**（P1–P3）。Langfuse = 作品集/研发 **第二图**。  
法：`specs/process-visibility.md` §9 S1 · §11 P5。

## 开关

| 变量 | 含义 |
|------|------|
| `ORPATH_LANGFUSE=1` | Watch 上 `tier3.enabled=true`（声明意图） |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | 官方 SDK 凭据 |
| `LANGFUSE_HOST` 或 `LANGFUSE_BASE_URL` | 自托管地址（可选） |

```bat
set ORPATH_LANGFUSE=1
set LANGFUSE_PUBLIC_KEY=pk-...
set LANGFUSE_SECRET_KEY=sk-...
:: 可选自托管
set LANGFUSE_HOST=http://127.0.0.1:3000
```

## 工程现状（诚实）

| 已做 | 未做 |
|------|------|
| snapshot.`tier3` 面板 + docs | **未**默认在 LG 每站自动 OTel export |
| 选型 S1 写明可选 | 未把 Langfuse 当产品主脸 |
| | 未捆绑 Docker Compose 一键起 Langfuse |

若要真正打 span，推荐后续（**另开任务，非 P5 门禁**）：

1. `pip install langfuse`（或 OTel exporter）  
2. 在 `orpath/control_plane` / graph 节点边界 `start_as_current_span(node_name)`  
3. 用 Langfuse Agent Graph 看站序  

参考：https://langfuse.com/docs/observability/features/agent-graphs

## 禁止话术

- 「装了 Langfuse = 实时可视化完成」  
- 「Langfuse 替代 `orpath.bat watch`」  
- 「CoT 一定在 Langfuse 里」  

## Watch 上怎么看

右栏 **Tier-3 Langfuse (optional)**：

- `ORPATH_LANGFUSE=0|1`  
- 指向本文  
