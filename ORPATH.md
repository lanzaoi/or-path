# OR-Path：宿主无关主控（OpenPi 已移除）

**Hermes 不是产品运行时。** **OpenPi 桌面壳已从本安装删除**（2026-07-31，方案 B）。  
控制面：**`orpath.bat menu`**；轻量对话：**`pi.bat` / `orpath.bat pi`**。

## 默认策略

| 项 | 默认 | 关闭 |
|----|------|------|
| **Live 多 Agent** | **ON**（`ORPATH_LIVE_SUBAGENT=1`） | `set ORPATH_LIVE_SUBAGENT=0` 或 `--no-live-subagent` |
| **Intake / OCR** | 有文件：`pdf_text` / ppocr / rapidocr | 无题面 → skip |
| **控制面** | **`orpath.bat menu`** | — |
| **CI / 门禁** | live **OFF** | `orpath.bat gate*` |

裸 Pi 聊天 ≠ 多 Agent。须跑产品图后看 `outputs\.agents\` 是否含 `"name":"subagent"`。

## 推荐操作（无 Hermes、无 OpenPi）

**双击打开（推荐）：** 资源管理器进入本目录，双击 **`START-ORPATH.bat`**  
（会开菜单并在结束时 `pause`，窗口不会一闪就关。）

或命令行：

```bat
cd /d C:\Users\Lanzao\Desktop\agent
orpath.bat
orpath.bat menu
orpath.bat doctor
```

> 注意：直接双击 `orpath.bat` 现在默认也是 **menu**。  
> 若窗口闪退，用 `START-ORPATH.bat`，或在 **cmd** 里运行看报错。

菜单：Intake / inbox / run-full / gui-demo / 廉价演示 / 证据目录 / doctor。

```bat
orpath.bat intake --slug ocr1 --in fixtures\intake\ocr\scan_sample.png
orpath.bat run-full --slug myrun --thread-id myrun
orpath.bat pi
```

`orpath.bat openpi` → **退出码 2**，提示已移除。

## OCR / ppocr

- `ORPATH_PADDLEOCR_PYTHON`（系统 Python311 paddleocr）  
- 失败 → paddle api token → **rapidocr**  
- `backend` 写实名，禁止 placeholder 当成功  

## Pi 会话法

- `.pi/APPEND_SYSTEM.md` / 后续 `SYSTEM.md`（Feynman 对齐大改）  
- `.pi/settings.json` — pi-subagents  

## 证据

| 要验 | 路径 |
|------|------|
| OCR | `notes\*-ocr.raw.md` |
| 审题 | `outputs\*-intake.json` |
| 真 MA | `outputs\.agents\<slug>\*-lead-*.log` → `"name":"subagent"` |

## 法条

- `specs/openpi-boot-ma-ocr.md`（历史文件名；内容已改宿主无关）  
- OpenPi 删除说明：本文件 + `docs/OUT_OF_BAND.md`  
