# OR-Path：宿主无关主控（默认多 Agent + OCR）

**Hermes 不是产品运行时。** OpenPi 体积大、可换壳 — **控制面不绑 OpenPi 源码**（D5 搁置）。

## 默认策略

| 项 | 默认 | 关闭 |
|----|------|------|
| **Live 多 Agent** | **ON**（`ORPATH_LIVE_SUBAGENT=1`） | `set ORPATH_LIVE_SUBAGENT=0` 或 `--no-live-subagent` |
| **Intake / OCR** | 有文件时：`pdf_text` / **ppocr(paddle)** / rapidocr 回退 | 无题面 → skip |
| **控制面** | **`orpath.bat menu`** | — |
| **CI / 门禁** | live **OFF** | `orpath.bat gate*` |

裸聊天 ≠ 多 Agent。须跑产品图后看 `outputs\.agents\` 是否含 `"name":"subagent"`。

## 推荐操作（无 Hermes）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
orpath.bat doctor
orpath.bat menu
```

菜单：

1. Intake 指定文件（支持 **png/jpg 扫描图** + PDF）  
2. Intake `inbox/`  
3. Run full（auto-intake + live MA）  
4. gui-demo  
5. 廉价 no-live 演示  
6. 打开证据目录  
7. doctor  

或直接：

```bat
orpath.bat intake --slug ocr1 --in fixtures\intake\ocr\scan_sample.png
orpath.bat run-full --slug myrun --thread-id myrun
```

## OCR / 你的 ppocr

- 默认尝试：`ORPATH_PADDLEOCR_PYTHON`  
  （本机常见：`...\Python311\python.exe` 上的 **paddleocr 3.x**）  
- 若本地 Paddle 推理失败（如 oneDNN），自动：  
  1. `paddleocr api`（需 `PADDLEOCR_ACCESS_TOKEN`）  
  2. **rapidocr-onnxruntime**（产品 venv 轻量回退）  
- `ocr.meta.json` 的 `backend` 会写真实引擎名（**不会**再写 placeholder 当成功）

## Pi 会话法

- `.pi/APPEND_SYSTEM.md` — 禁 cosplay、数字真相  
- `.pi/settings.json` — pi-subagents 包  

任意宿主（未来小 GUI）只要 cwd=本仓 + 调 `orpath`，行为一致。

## 证据

| 要验 | 路径 |
|------|------|
| OCR | `notes\*-ocr.raw.md` · `*-ocr.meta.json` |
| 审题 | `outputs\*-intake.json` |
| 真 MA | `outputs\.agents\<slug>\*-lead-*.log` → `"name":"subagent"` |
| 阶段 | `runs\<thread>\stages\` |

## OpenPi（可选）

```bat
orpath.bat openpi
```

仅作重型桌面壳；**面板不在 OpenPi 内嵌**（可换 GUI）。开壳后仍用 **`orpath.bat menu`**。

## 法条

- `specs/openpi-boot-ma-ocr.md`  
- 计划：`.hermes/plans/2026-07-31_openpi-boot-ma-ocr.md`
