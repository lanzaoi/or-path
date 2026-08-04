# Demo seed（默认脸 / M0 回放）

安装或 `orpath setup` 时，会把本目录下的 slug **合并拷贝**到 `ORPATH_WORKDIR`（默认=安装根），让别人也能：

- `START-WATCH.bat` → 默认 **live-btube** 有过程/数字线索  
- `orpath.bat watch --slug m0` → 看到 M0 mock 证据串  

## 含什么

| slug | 用途 |
|------|------|
| `m0/` | mock shortest_path 证据（solution + validate + runs stages） |
| `live-btube/` | 圆管演示回放（瘦身：outputs/runs/notes/papers，**无**全量 `.agents` 日志） |

## 不含什么

- `.env` / API key  
- `.venv*` / `runtime/node_modules`（由 setup / Release 包另装）  
- `outputs/.agents/**` 全量 transcript（体积大；LIVE 请自备 key 重跑）  
- 竞赛 inbox PDF  

## 话术

- seed = **回放快照**，不是「此刻刚 LIVE 完」  
- 数字以 `*-solution.json` + `*-validate.json`（solve+validate）为准  
- 重跑 mock：`orpath.bat demo-m0 --slug m0`  

## 导出（作者机）

```bat
python scripts\export_demo_seed.py --slug m0
python scripts\export_demo_seed.py --slug live-btube
python scripts\export_demo_seed.py --check
```
