# OR-Path 安装（L1 clone · L2 Release）

目标：别人用接近 [Feynman](https://feynman.is) 的路径装上并能看脸。  
**使用教程（详细）：** [`user-guide.md`](user-guide.md)  
计划：`docs/archive/plans/2026-08-04_l1-l2-release-parity.md`  
**版本文件：** 仓库根 `VERSION`（当前目标 **0.3.0**）

## 前置

| 组件 | 最低 |
|------|------|
| OS | Windows 10+（主）；Linux/macOS 可用 `orpath.sh` |
| Python | **3.11–3.13 推荐**（3.14 可用核心依赖；图像 OCR 可选包可能装不上） |
| Node.js | **≥ 22.19**（首次 `npm ci` 装 Pi；若 Release 已带 `node_modules` 可略低但建议升级） |
| 磁盘 | 解压 + venv 约 0.5–1 GB |
| 密钥 | LIVE 多 Agent 需要 `DEEPSEEK_API_KEY`；**mock / 看 seed 脸不要 key** |

## 版本怎么选

| 版本 | 状态 | 内容 |
|------|------|------|
| **v0.2.0** | GitHub 已发布 | L1/L2 半肥 + seed 脸；**无** RAG v3 / promote-run 等后续 |
| **main / v0.3.0** | 代码在 main；zip 按 `archive/releases/v0.3.0-notes.md` 打 | 知识轨 · promote · tube LIVE 可绿 · claim 修复 · user-guide |

路人要最新能力：等 **v0.3.0** zip，或 L1 `git pull`。

## L2 — GitHub Release（推荐路人）

### v0.2.0（当前线上）

- `orpath-0.2.0-win-x64.zip` — 半肥包（源码 + **预装 Pi** + `demo/seed`）
- `SHA256SUMS` · `install.ps1`

```powershell
irm https://github.com/lanzaoi/or-path/releases/download/v0.2.0/install.ps1 | iex
```

### v0.3.0（打好包后）

```powershell
irm https://github.com/lanzaoi/or-path/releases/download/v0.3.0/install.ps1 | iex
# 或
powershell -ExecutionPolicy Bypass -File scripts\install\install.ps1 `
  -LocalZip .\dist\orpath-0.3.0-win-x64.zip `
  -InstallDir $env:TEMP\orpath-try -NoPath
```

说明全文：[`archive/releases/v0.3.0-notes.md`](archive/releases/v0.3.0-notes.md)。

安装默认目录：`%LOCALAPPDATA%\Programs\orpath`  
然后：

```bat
cd %LOCALAPPDATA%\Programs\orpath
orpath.bat doctor
START-WATCH.bat
:: 详细用法
:: 浏览器打开 docs\user-guide.md 或仓库 docs/user-guide.md
orpath.bat demo-m0 --slug m0
```

## L1 — git clone（开发者）

```bat
git clone https://github.com/lanzaoi/or-path.git
cd or-path
git pull
orpath.bat setup
orpath.bat doctor
START-WATCH.bat
orpath.bat demo-m0 --slug m0
orpath.bat watch --slug m0
```

`setup` 会：建 `.venv-314` → `pip install -r requirements.txt` → `runtime` 下 `npm ci`（若缺 Pi）→ 拷 `.env.example` → 释放 `demo/seed` → doctor。

## 作者打 Release 包（v0.3.0）

```bat
:: 0) VERSION 文件已是 0.3.0
type VERSION

:: 1) 导出/更新 seed（本机有产物时）
python scripts\export_demo_seed.py --slug all

:: 2) 确保 runtime 已 npm
cd runtime && npm ci && cd ..

:: 3) 打包
python scripts\pack_release.py
:: → dist\orpath-0.3.0-win-x64.zip + dist\SHA256SUMS

:: 4) 门禁
python scripts\l2_release_gate.py --zip dist\orpath-0.3.0-win-x64.zip

:: 5) 上传 GitHub Release
:: gh release create v0.3.0 dist\orpath-0.3.0-win-x64.zip dist\SHA256SUMS scripts\install\install.ps1 --notes-file docs\archive\releases\v0.3.0-notes.md
```

**不要**把 `.env`、`.venv-314`、全量 `outputs/.agents`、竞赛 PDF 推进 git 或 zip。  
`dist/` 已 gitignore。

## 故障

| 现象 | 处理 |
|------|------|
| doctor BAD missing cli.js | `orpath.bat setup` 或 `cd runtime && npm ci` |
| import langgraph 失败 | setup / 检查是否用了 `.venv-314` |
| START-WATCH 空脸 | `orpath.bat demo-seed` 或 setup |
| LIVE 不跑 | `.env` 填 `DEEPSEEK_API_KEY` |
| Node 版本警告 | 升级 ≥22.19；已有 Pi 时可先 WARN |

## 话术

- seed / 默认 live-btube = **回放**，不是此刻 LIVE  
- 数字只认 `*-solution.json` + `*-validate.json`  
- Hermes ≠ 产品运行时  
