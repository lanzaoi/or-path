# Host-agnostic boot — menu · MA · OCR（详细）

**状态：** LAW 2026-08-01  
**OpenPi：** **已删除**（2026-07-31 plan B）  
**对齐：** `product-flow-sdd.md`

---

## 1. 主控

| 入口 | 角色 |
|------|------|
| `orpath.bat` 无参 / `menu` | **主控制面** |
| `START-ORPATH.bat` | 双击 + pause |
| `run` / `run-full` | 全链 |
| `intake` | 仅读题 |
| `timeline` | 过程可视（M0 目标） |
| `pi` | TUI；≠ 自动 MA 全链 |
| `openpi` | **tombstone exit 2** |
| `doctor` | 安装检查 |

---

## 2. 默认策略

| 项 | 默认 | 关闭 |
|----|------|------|
| Live MA | ON（unset→1） | env=0 / `--no-live-subagent` / gate |
| Intake | 有文件才开 | 无源 skip |
| OCR | pdf_text → **ppocr** → api → **rapidocr** | — |
| Pi 法条文件 | `.pi/APPEND_SYSTEM.md`（未来 SYSTEM.md + 真注入） | 死键 appendSystem 不生效 |

---

## 3. Menu 项（实现以脚本为准）

| # | 含义 |
|---|------|
| 1 | Intake 指定路径 |
| 2 | inbox 自动 |
| 3 | run-full（耗 DS 若 LIVE） |
| 4 | gui-demo fixture |
| 5 | 廉价 mock SP，LIVE off |
| 6 | 打开 agents/runs 证据 |
| 7 | doctor |
| 0 | 退出 |

**空 inbox + run-full：** 可能 `auto_intake_empty` → mock SP 演示，**不是用户竞赛题**。

---

## 4. Windows 启动器法

1. **禁止** `shift` 后依赖 `%*` 传 run-full 参数（用 %2–%9）  
2. 子进程 Pi：**UTF-8** decode（禁 GBK text 默认）  
3. bat：CRLF、ASCII 无 BOM  
4. 大改 bat 优先整文件重写  

---

## 5. OCR 诚实

- meta.backend 写实名  
- 禁止 placeholder 当成功  
- 图像验收：`fixtures/intake/ocr/scan_sample.png`  

```bat
orpath.bat intake --slug ocr1 --in fixtures\intake\ocr\scan_sample.png
```

---

## 6. 证据

| | |
|--|--|
| OCR | notes/*-ocr* |
| intake | outputs/*-intake.json |
| MA | outputs/.agents/* `"name":"subagent"` |
| 阶段 | runs/*/stages |
| 时间线 | outputs/*-timeline.md（M0） |

---

## 7. 与可视化

menu 项 6 打开目录；M0 后应有 **生成时间线** 项或 run 结束自动写。  
→ `process-visibility.md`

---

## 8. 历史

计划：`.hermes/plans/2026-07-31_openpi-boot-ma-ocr.md`  
Feynman 对齐大改计划：`.hermes/plans/2026-07-31_feynman-style-orpath-rearch.md`（**未等于已实现**）  
