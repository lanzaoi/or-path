# OR-Path 安装（L1 clone · L2 Release）

目标：别人用接近 [Feynman](https://feynman.is) 的路径装上并能看脸。  
计划：`docs/archive/plans/2026-08-04_l1-l2-release-parity.md`

## 前置

| 组件 | 最低 |
|------|------|
| OS | Windows 10+（主）；Linux/macOS 可用 `orpath.sh` |
| Python | **3.11–3.13 推荐**（3.14 可用核心依赖；图像 OCR 可选包可能装不上） |
| Node.js | **≥ 22.19**（首次 `npm ci` 装 Pi；若 Release 已带 `node_modules` 可略低但建议升级） |
| 磁盘 | 解压 + venv 约 0.5–1 GB |
| 密钥 | LIVE 多 Agent 需要 `DEEPSEEK_API_KEY`；**mock / 看 seed 脸不要 key** |

## L2 — GitHub Release（推荐路人）

发布资产（`v0.2.0`）：

- `orpath-0.2.0-win-x64.zip` — 半肥包（源码 + **预装 Pi** + `demo/seed`）
- `SHA256SUMS`
- `install.ps1`

**本机已验收（作者机）：** `pack_release` → `l2_release_gate` PASS；`install.ps1 -LocalZip` → doctor PASS → Watch face `status=ok`。

```powershell
# 在线（发布 tag 后）
irm https://github.com/lanzaoi/or-path/releases/download/v0.2.0/install.ps1 | iex

# 或本机已有 zip（不经 GitHub）
powershell -ExecutionPolicy Bypass -File scripts\install\install.ps1 `
  -LocalZip .\dist\orpath-0.2.0-win-x64.zip `
  -InstallDir $env:TEMP\orpath-try -NoPath
```

安装默认目录：`%LOCALAPPDATA%\Programs\orpath`  
然后：

```bat
cd %LOCALAPPDATA%\Programs\orpath
orpath.bat doctor
START-WATCH.bat
orpath.bat demo-m0 --slug m0
```

## L1 — git clone（开发者）

```bat
git clone https://github.com/lanzaoi/or-path.git
cd or-path
orpath.bat setup
orpath.bat doctor
START-WATCH.bat
orpath.bat demo-m0 --slug m0
orpath.bat watch --slug m0
```

`setup` 会：建 `.venv-314` → `pip install -r requirements.txt` → `runtime` 下 `npm ci`（若缺 Pi）→ 拷 `.env.example` → 释放 `demo/seed` → doctor。

## 作者打 Release 包

```bat
:: 1) 导出/更新 seed（本机有产物时）
python scripts\export_demo_seed.py --slug all

:: 2) 确保 runtime 已 npm
cd runtime && npm ci && cd ..

:: 3) 打包
python scripts\pack_release.py
:: → dist\orpath-VERSION-win-x64.zip + dist\SHA256SUMS

:: 4) 门禁
python scripts\l2_release_gate.py --zip dist\orpath-0.2.0-win-x64.zip

:: 5) 上传 GitHub Release（示例）
:: gh release create v0.2.0 dist\orpath-0.2.0-win-x64.zip dist\SHA256SUMS scripts\install\install.ps1
```

**不要**把 `.env`、`.venv-314`、全量 `outputs/.agents` 推进 git。  
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
