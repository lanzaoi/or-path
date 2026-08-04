# OR-Path：宿主无关主控（OpenPi 已移除）

**Hermes 不是产品运行时。** **OpenPi 桌面壳已从本安装删除**（2026-07-31，方案 B）。  
控制面：**`orpath.bat menu`**；**实时过程脸：双击 `START-WATCH.bat` / `orpath.bat face` / `watch`**；轻量对话：**`pi.bat` / `orpath.bat pi`**。

**全新机器请先：** `orpath.bat setup` → `doctor`（说明见 **`docs/install.md`**）。

## 一键启动（推荐）

| 方式 | 做什么 |
|------|--------|
| **`orpath.bat setup`** | L1：venv + Pi npm + 释放 demo seed + doctor |
| **双击 `START-WATCH.bat`** | 清环境 → 起 Watch → 开浏览器；默认 **圆管 seed `live-btube`** |
| **双击 `START-CASE.bat`** | **路径 A**：指定**本地案例文件夹** + slug；可选 watch-run / 只看脸 / 题面路径 |
| 双击 `START-ORPATH.bat` | 选 **1 菜单** / **2 Watch**（回车默认 2） |
| `orpath.bat face` | 命令行同 START-WATCH 默认 |
| `START-WATCH.bat 其它slug` | 看 workdir 下指定任务 |
| `orpath.bat pack-release` | 打 L2 半肥 zip → `dist/` |

- 路径**不要加引号**（脚本会剥引号，但易踩坑）。  
- 结束 Watch：黑窗 **Ctrl+C** → 任意键。  
- 旧页面：**Ctrl+F5**。  
- 题面有「骨牌/polyomino/圆管/tube」文件名时，`START-CASE` 会猜域并带 `--auto-intake`。

### 路径 A · 本地文件夹

1. 建目录，例如 `D:\orpath-cases\demo1` 或 `Desktop\test`  
2. 双击 **`START-CASE.bat`** → **2** → 贴目录 → slug  
3. 可选题面 PDF/图；LIVE 先 **N** 更稳，真多 Agent 选 **y**  
4. 产物在该目录：`outputs\` · `runs\<slug>\` · `papers\`  
5. 只看：同一 bat 选 **1**，同一目录 + slug  

```bat
orpath.bat watch-run --workdir D:\orpath-cases\demo1 --slug demo1 --keep-watch
orpath.bat watch --workdir D:\orpath-cases\demo1 --slug demo1

:: 骨牌 + LIVE
orpath.bat watch-run --workdir D:\cases\b --slug b1 --live --keep-watch ^
  --auto-intake --intake-in D:\cases\b\B题.pdf ^
  --problem-id polyomino_b_q1 --problem-class polyomino_cover --solve-mode polyomino
```

**合同：** 安装根 = 代码/`.pi/agents`；workdir = 案例数据。Watch 必须同一 workdir+slug。

### B 题全问（不只 Q1.1）

单次产品 run 默认只演示 Q1.1。全问 bank → 案例目录：

```bat
.venv-314\Scripts\python.exe scripts\pack_b_polyomino_case.py --case D:\cases\b
:: 论文 papers\B-polyomino-full-paper.md · Excel outputs\b-full\*.xlsx
```

数字总表：Q1.1=**6** · Q1.2 L3 16/16 · Q2.1=**33** · Q2.2=**134** · Q2.3=**225** · Q2.4=**32** · Q3 cost=**82.5**/shared=**142**/pieces=**33**。

## 默认策略

| 项 | 默认 | 备注 |
|----|------|------|
| Live 多 Agent | 可选；START-CASE 默认 N | `--live` / `ORPATH_LIVE_SUBAGENT=1`；子代理超时默认 360s（watch-run） |
| Intake | 有 `--intake-in` 才开 | **不再**偷偷塞 fixtures intake |
| 过程台 | Watch HTTP :8765 | 中文 Apple 风；顶栏换模型 |
| CI / 门禁 | live OFF | `orpath.bat gate*` / `m1-gate` / `m2-gate` |

真 MA 证据：`outputs/.agents/<slug>/` 含 research/model/cite/review 日志与 subagent toolCall。

## 实时过程台

```bat
START-WATCH.bat
orpath.bat face
orpath.bat watch --slug live-btube
orpath.bat watch-run --slug p3-demo --keep-watch
orpath.bat p3-gate
```

法条：`specs/process-visibility.md` · 冒烟：`docs/v0-smoke.md` · M1：`docs/m1-smoke.md` · M2：`docs/m2-polyomino.md`。

## 菜单与 doctor

```bat
orpath.bat menu
orpath.bat doctor
orpath.bat m1-gate
orpath.bat m2-gate
orpath.bat tube-live-gate
```

## 环境

```bat
set PYTHONPATH=
set PYTHONHOME=
set PYTHONNOUSERSITE=1
:: 使用 .venv-314\Scripts\python.exe
```

## 相关

- 总览：[`README.md`](README.md)  
- 法条：[`specs/README.md`](specs/README.md)  
- docs：[`docs/README.md`](docs/README.md)
