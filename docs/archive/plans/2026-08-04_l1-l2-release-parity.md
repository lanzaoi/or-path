# OR-Path L1+L2 分发对等 — Implementation Plan

> **For Hermes:** Use subagent-driven-development（或单会话按 Task 顺序）实现。  
> **用户锁定（2026-08-04）：** 起码 **L2**；**L1 + L2 Release 包装**；原则 **「我这边有的、别人那边都要有」= 可运行能力对等**（非把本机所有 adhoc 垃圾产物原样上传）。  
> **实施状态（2026-08-04）：** Task 1–11 **已在工作区落地**；`doctor` + `l2_release_gate`（含 full unpack）本地 PASS；`dist/orpath-0.2.0-win-x64.zip` 已打出。**未 commit / 未 GitHub Release**（待作者）。`.gitignore` 已改为跟踪 `demo/seed/**`。

**Goal:** 让陌生人用接近 Feynman 的路径安装并跑通 OR-Path：一行/一脚本安装 → setup → doctor PASS → 默认 Watch 有料 + mock M0 可复现；作者本机能力（venv 依赖、Pi runtime、演示产物、启动器）在 **Release 包** 侧齐备。

**Architecture:**  
- **Git `main`**：保持瘦源码（无 node_modules / venv / .env / 海量 outputs）。  
- **L1**：仓库内 `orpath setup` 从源码恢复运行时（pip + npm ci）。  
- **L2**：`pack_release` 打 **半肥 zip**（源码 + **预装 `runtime/node_modules`** + **演示数据 seed** + 安装脚本）；`install.ps1`/`install.sh` 下载解压并调用 setup（Python 现场建 venv；Node 模块优先用包内预装）。  
- **密钥永不进包**；用户只带自己的 `DEEPSEEK_API_KEY`。

**Tech Stack:** 现有 `orpath.bat` / Python 3.11+ / Node ≥22.19 / npm / GitHub Releases；对标 `vendor/feynman` 的 install 漏斗（不嵌入 Feynman 产品壳）。

**Non-goals（本切片不做）：**  
- L3 embed 官方 Node/Python 二进制  
- 公网短域名 / 独立官网  
- 把 `vendor/`、全历史 `runs/*`、竞赛 `inbox` PDF 打进包  
- 改求解器算法或 Watch 产品 UI 大翻修  

---

## 0. 「我有的 → 别人要有」对等表

| 你本机有的 | 别人如何获得 | L1（clone） | L2（Release zip） |
|------------|--------------|------------|-------------------|
| 产品源码 `orpath/` `tools/` `scripts/` `specs/` `.pi/agents` | git / zip 内 | ✅ 仓内 | ✅ 包内 |
| 启动器 `orpath.bat` `START-*.bat` `pi.bat` | 同上 | ✅ | ✅ |
| fixtures 金标 | 同上 | ✅ | ✅ |
| Python 依赖（langgraph/ortools…） | setup → venv + pip | ✅ 现装 | ✅ 现装（**不**拷贝 `.venv-314`，跨机 venv 不可靠） |
| Pi + pi-subagents（`runtime/node_modules` ~163MB） | npm 或预装 | ✅ setup 现装 | ✅ **预装进 zip**（对等「我已 npm i」） |
| Node 本体 ≥22.19 | 系统前置 | 文档+doctor 检查 | 同上（L2 不 embed Node） |
| `.env` / API key | 用户自备 | setup 拷 example | 同上；**禁止**打进包 |
| 默认脸 `live-btube` 可读产物 | seed 目录 | setup 或 `demo seed` 释放 | ✅ **pack 时写入包内 `demo/seed/live-btube/`** |
| M0 证据串 | `demo-m0` 可再生成 + seed | ✅ 命令生成 | ✅ seed + 仍可重跑 |
| doctor / menu / watch-run | 源码 | ✅ | ✅ |
| LIVE 真 sub 全过程（重跑） | key + 时间 | 可选 | 可选；seed 提供**只看脸**不替代 LIVE 重跑 |
| 本机 adhoc 实验、166MB 全量 agent 日志是否全要 | **精选 seed** | 见 §0.1 | 见 §0.1 |

### 0.1 演示 seed 范围（「有料」≠ 全盘拷贝）

**必须进 seed（默认 START-WATCH / face 不空）：**

| slug | 内容 | 本机参考量级 |
|------|------|----------------|
| **`m0`** | `outputs/m0-*` + `runs/m0/stages`（及 evidence） | ~100KB 级 |
| **`live-btube`** | Watch 可读最小集：`outputs/live-btube-*`（solution/validate/schema/intake/provenance 等）、`runs/live-btube/stages` + `latest_snapshot.json`、`notes/live-btube-*`、`papers/live-btube.md` | outputs+runs+notes+papers ≈ **1MB 内** |

**可选进 seed（「L1 树有料」更深）：**

| 内容 | 本机量级 | 决策 |
|------|----------|------|
| `outputs/.agents/live-btube` 全量 | **~166MB** | **默认 L2 标准包不含**；另打 `orpath-x.y.z-win-x64-fullface.zip` 可选，或文档写「装完可 `--live` 自己跑」 |
| `.pi-subagents` 原始 transcript | 视情况 | 不进标准包（可从 agents 派生）；Watch 无 transcript 时 honesty 字段已能说明 |

**禁止进任何包：** `.env`、`.venv-314`、`inbox/**`、知识库缓存、`vendor/`、全仓库历史 `outputs/adhoc-*`。

**对等语义（对外话术）：**

- 标准包 = 你机器上 **装好 Pi + 能 doctor + 能看默认脸 + 能重跑 mock M0**  
- 不含 = 你机器上 **历史调试垃圾** 与 **密钥**  
- LIVE 重跑能力 = 有 runtime + key，与作者相同（时间成本自付）

---

## 1. 目标用户路径（验收剧本）

### 1.1 L2 主路径（对标 Feynman 安装）

```powershell
# Windows
irm https://github.com/lanzaoi/or-path/releases/download/vX.Y.Z/install.ps1 | iex
# 或下载 orpath-X.Y.Z-win-x64.zip 解压后：
cd %LOCALAPPDATA%\Programs\orpath   # 安装器默认根
orpath setup
# 编辑 .env 填 DEEPSEEK_API_KEY（仅 LIVE 需要；mock 可先空）
orpath doctor          # PASS
START-WATCH.bat        # 默认 live-btube 有阶段/数字可看
orpath demo-m0 --slug m0-fresh
orpath watch --slug m0-fresh
```

### 1.2 L1 路径（clone 开发者）

```bat
git clone https://github.com/lanzaoi/or-path.git
cd or-path
orpath.bat setup
orpath.bat doctor
orpath.bat demo-seed   # 若 seed 以 git-lfs/或 release 附件提供；见 Task 种子策略
orpath.bat demo-m0 --slug m0
START-WATCH.bat m0
```

**seed 进 git 策略（锁定）：**  
- `demo/seed/**` **允许进 main**（仅 §0.1 必须集，无 agents 166MB）  
- 这样 L1 clone 不依赖 Release 也能默认有脸  
- fullface 大包仅 Release

### 1.3 前置（写进 doctor + README）

| 组件 | 最低版本 |
|------|----------|
| OS | Windows 10+（主）；Linux/macOS 用 `orpath.sh` 次要 |
| Python | 3.11+（launcher 优先 `.venv-314`） |
| Node | **≥ 22.19.0**（Pi engine） |
| 磁盘 | 标准包解压后约 **0.5–1GB**（node_modules + venv） |
| 网络 | L1 setup 需 npm+PyPI；L2 标准包 npm 可离线，pip 仍要网（或后续加 wheelhouse，本切片不做） |

---

## 2. 包布局（L2 zip 根目录）

```text
orpath-X.Y.Z-win-x64/
  README.md                 # 含 Install 漏斗
  ORPATH.md
  LICENSE                   # 若无则后补 MIT/自述
  orpath.bat
  orpath.sh
  START-WATCH.bat
  START-CASE.bat
  START-ORPATH.bat
  pi.bat
  pi.sh
  requirements.txt
  .env.example
  orpath.env.example
  package-meta.json         # pack 写入：version, git_sha, created_utc, contents flags
  runtime/
    package.json
    package-lock.json
    README.md
    node_modules/           # ★ 预装（半肥）
  demo/
    seed/
      README.md             # seed 说明与 claim ladder
      live-btube/           # 展开到 WORKDIR 的模板
        outputs/...
        runs/live-btube/...
        notes/...
        papers/...
      m0/
        outputs/...
        runs/m0/...
  orpath/ tools/ scripts/ specs/ fixtures/ contracts/ .pi/agents/ .pi/settings.json ...
  # 无: .env .venv* outputs/ runs/ 根上的用户数据（seed 只在 demo/seed）
```

安装后 `orpath setup`：

1. 建 `.venv-314` + pip  
2. 若 `runtime/.../cli.js` 已存在则 **跳过 npm**；否则 npm ci  
3. 将 `demo/seed/live-btube/*` 与 `demo/seed/m0/*` **合并拷贝**到 `ORPATH_WORKDIR`（默认安装根），**不覆盖**用户已改文件（`--force-seed` 才覆盖）  
4. 无 `.env` 则 copy example  
5. doctor  

---

## 3. 分阶段任务（实现顺序）

---

### Task 1: 冻结版本与元数据约定

**Objective:** 发布版本号与 pin 单一来源。

**Files:**
- Create: `VERSION`（纯文本，如 `0.2.0`）或读自 `package-meta` 模板  
- Modify: `.env.example`（已有 PI pin 注释，保持与 `runtime/package.json` 一致）  
- Create: `demo/seed/README.md`

**Steps:**
1. 确定首个公开分发版本 **`0.2.0`**（或 `0.1.0-l2`——实现时写死进 VERSION）。  
2. 记录 pin：`pi-coding-agent@0.82.1`、`pi-subagents@0.37.2`（以 `runtime/package-lock.json` 为准）。  
3. `demo/seed/README.md` 写清：seed 不含 key、不含最优值口算、数字以 solution+validate 为准。

**Verify:** `runtime/package.json` 与 lock 中版本一致。

**Commit:** `chore: add VERSION and demo seed contract`

---

### Task 2: 采集并检入标准 seed（m0 + live-btube 瘦身）

**Objective:** main 仓自带「默认有脸」数据，L1/L2 同源。

**Files:**
- Create: `demo/seed/m0/**`（从本机 `outputs/m0-*`、`runs/m0` 拷贝精选）  
- Create: `demo/seed/live-btube/**`（outputs 前缀文件 + runs/stages + notes + papers；**不含** `outputs/.agents/live-btube`）  
- Create: `scripts/export_demo_seed.py`  
  - 参数：`--slug m0|live-btube`、`--from-workdir`、`--out demo/seed/<slug>`  
  - 白名单拷贝；拒绝 `.env`；打印字节数  

**Steps:**
1. 实现 `export_demo_seed.py`。  
2. 从当前作者机器导出 m0 与 live-btube 瘦身集。  
3. 人工打开 `orpath.bat watch --slug live-btube`（WORKDIR 临时指向 seed 展开目录）确认 L0 非空。  
4. git add `demo/seed`（确认无密钥、无 inbox PDF）。

**Verify:**
```bat
python scripts\export_demo_seed.py --check demo\seed
:: 或
orpath.bat watch --workdir %TEMP%\orpath-seed-test --slug live-btube
:: 先 setup 拷 seed 到该 workdir
```
Expected: Watch 快照含 stages 或 solution 路径；非 `no_product_run` 空壳。

**Commit:** `feat(demo): seed m0 + live-btube for default face`

---

### Task 3: `scripts/bootstrap_orpath.py`（setup 核心）

**Objective:** 一条命令恢复与作者等价的可运行环境（除 key 与 LIVE 重跑时间）。

**Files:**
- Create: `scripts/bootstrap_orpath.py`  
- Modify: `orpath.bat` — 增加 `setup` 子命令  
- Modify: `orpath.sh` — 同上  

**CLI：**
```text
python scripts/bootstrap_orpath.py
  [--skip-npm] [--skip-pip] [--force-seed] [--no-seed] [--no-doctor]
  [--python PATH]
```

**行为（顺序）：**
1. 解析 `ORPATH_HOME`（默认仓库根）。  
2. 检查 `python` ≥3.11、`node` ≥22.19（用 `node -p process.versions.node`）；失败 **exit 2** + 中文说明。  
3. 若无 `.venv-314`：`python -m venv .venv-314`。  
4. `.venv-314/Scripts/pip install -U pip` 后 `pip install -r requirements.txt`。  
5. 若缺 `runtime/node_modules/@earendil-works/pi-coding-agent/dist/cli.js`：  
   `cd runtime && npm ci`（失败则 `npm install`）。  
6. 若无 `.env`：copy `.env.example` → `.env`，打印「请填写 DEEPSEEK_API_KEY」。  
7. 调用 seed 安装：把 `demo/seed/*/…` 映射到 workdir（见 Task 4）。  
8. 默认跑 doctor；非 0 则 setup 失败。

**Verify:**
```bat
:: 在干净克隆或临时目录（可先删 .venv-314 与 runtime/node_modules 做一次）
orpath.bat setup
orpath.bat doctor
```
Expected: `PASS: orpath_doctor`

**Commit:** `feat(setup): bootstrap venv + runtime npm + seed`

---

### Task 4: seed 安装到 WORKDIR

**Objective:** setup/install 后默认 slug 有数据。

**Files:**
- Create: `scripts/install_demo_seed.py`（或并入 bootstrap）  
- Modify: bootstrap 调用它  

**规则：**
- 源：`ORPATH_HOME/demo/seed/<slug>/`  
- 目标：`ORPATH_WORKDIR/{outputs,runs,notes,papers}/…`  
- 默认 **不覆盖** 已存在文件；`--force-seed` 覆盖  
- 打印拷贝文件数  

**Verify:** 空 workdir 执行后存在 `outputs/live-btube-solution.json` 与 `runs/live-btube/`。

**Commit:** `feat(setup): install demo seed into workdir`

---

### Task 5: doctor 增强（可运行导向）

**Objective:** 失败时告诉用户怎么修，并检查 L2 关键前置。

**Files:**
- Modify: `scripts/orpath_doctor.py`

**新增检查：**
1. Python 版本 ≥3.11  
2. 能 `import langgraph` / `ortools`（在 launcher 使用的 py 上）  
3. Node 版本 ≥22.19（若 which node）  
4. Pi cli.js（已有）— BAD 时打印：`orpath.bat setup` 或 `cd runtime && npm ci`  
5. **软检查（WARN 不 fail）：** seed 是否已安装（`outputs/live-btube-solution.json` 或 m0）；提示 `setup` / `install_demo_seed`  
6. **软检查：** `.env` 是否存在；`DEEPSEEK_API_KEY` 是否非空（空则 WARN：mock 可用，LIVE 不可）

**Verify:**
```bat
orpath.bat doctor
:: 故意改名 cli.js 后应 FAIL 且文案含 setup
```

**Commit:** `fix(doctor): actionable setup hints + runtime version checks`

---

### Task 6: `orpath.bat` / 菜单接入 setup + demo-seed

**Objective:** 用户可发现入口。

**Files:**
- Modify: `orpath.bat` — `setup`、`demo-seed`、help 文本  
- Modify: `scripts/orpath_menu.py` — 增加「安装/修复环境」「释放演示数据」项（若菜单结构简单则只 bat）  
- Modify: `START-WATCH.bat` 注释：首次请 `orpath setup`；默认 live-btube 依赖 seed  

**Verify:** `orpath.bat help` 含 setup。

**Commit:** `feat(launcher): wire setup and demo-seed commands`

---

### Task 7: `scripts/pack_release.py`（打 L2 zip）

**Objective:** 从干净/当前树生成可上传 GitHub Release 的 zip + 校验。

**Files:**
- Create: `scripts/pack_release.py`  
- Create: `scripts/release_include.txt`（可选，或代码内白名单）

**打包逻辑：**
1. 读 `VERSION` + `git rev-parse --short HEAD`。  
2. 暂存目录 `dist/orpath-{ver}-win-x64/`。  
3. 拷贝白名单源码与启动器（**排除** `.git` `.venv*` `.env` `outputs/` `notes/` `papers/` `runs/` `vendor/` `pi-main/` `.hermes/` `inbox/**` `**/__pycache__` `demo/` 以外的本地垃圾）。  
4. **必须包含** `demo/seed/**`。  
5. 若本机 `runtime/node_modules/.../cli.js` 存在：拷贝整个 `runtime/node_modules`；否则在 pack 内执行 `npm ci`（要求网络）。  
6. 写 `package-meta.json`：`{version, git_sha, pi_version, packed_utc, has_node_modules, seed_slugs}`。  
7. zip → `dist/orpath-{ver}-win-x64.zip`  
8. 写 `dist/SHA256SUMS`（该 zip 一行）。  
9. 打印路径与 MB。

**不要：** 打包 `.venv-314`（Windows venv 不可移植）。

**Verify:**
```bat
python scripts\pack_release.py
:: 检查 zip 内存在 runtime\node_modules\@earendil-works\pi-coding-agent\dist\cli.js
:: 检查不存在 .env
```

**Commit:** `feat(release): pack_release half-fat zip + SHA256SUMS`

---

### Task 8: Windows `install.ps1`（+ 同步副本）

**Objective:** 对标 Feynman `irm … | iex` 体验（资产在 GitHub Releases）。

**Files:**
- Create: `scripts/install/install.ps1`  
- Create: `install.ps1`（根目录薄包装，指向 raw/release URL 文档说明）  
- 可选：pack 时把 `install.ps1` 拷进 `dist/` 与 zip 外同级上传  

**参数：**
```powershell
-Version 0.2.0          # 默认 latest（解析 GitHub latest release）
-InstallDir $env:LOCALAPPDATA\Programs\orpath
-Repo lanzaoi/or-path
-SkipSetup              # 只下载解压
```

**行为：**
1. 解析 version 与 asset 名 `orpath-$ver-win-x64.zip`。  
2. 下载 zip + SHA256SUMS；校验哈希。  
3. 解压到临时目录，校验关键文件 `orpath.bat` 存在，再 **替换** InstallDir（避免 Expand-Archive 直接怼活目录——学 Feynman 暂存再 swap）。  
4. 可选：用户 PATH 增加 InstallDir（提示需新开终端）。  
5. 除非 `-SkipSetup`：调用 `orpath.bat setup`（用 InstallDir）。  
6. 打印 wow 命令。

**Verify（人工/脚本）：**
- 在干净目录 dry-run：对本地 `dist/*.zip` 用 `-LocalZip` 参数（**实现时加**）跳过网络。  
```powershell
powershell -File scripts\install\install.ps1 -LocalZip dist\orpath-0.2.0-win-x64.zip -InstallDir $env:TEMP\orpath-l2-test
```

**Commit:** `feat(release): Windows install.ps1 with checksum`

---

### Task 9: Unix `install.sh`（次要，L2 完整性）

**Objective:** Linux/macOS 同学不致完全无门。

**Files:**
- Create: `scripts/install/install.sh`  
- Asset 名：`orpath-X.Y.Z-linux-x64.zip` **或** 与 win 共用同一 **源码+node_modules** zip（node_modules 含平台 native 时需分平台——**风险见 §5**）。

**本切片锁定：**  
- **主交付 Windows zip**（作者主场）。  
- `install.sh` 可装 **瘦包/同源 zip**，node_modules 若架构不符则 setup 里 **删后 npm ci**。  
- pack_release 增加 `--platform win|linux|darwin|all`；默认先 `win`。

**Commit:** `feat(release): install.sh best-effort`

---

### Task 10: 文档漏斗（README + ORPATH + install.md）

**Objective:** 公开仓打开就能走 Feynman 式路径。

**Files:**
- Modify: `README.md` — 顶部改为 Install（L2 Release / L1 clone）→ setup → doctor → START-WATCH / demo-m0  
- Modify: `ORPATH.md` — 链到安装；默认脸依赖 seed  
- Create: `docs/install.md` — 前置、故障树、Release 资产列表、与 claim ladder  
- Modify: `docs/onboarding-research.md` — 文首加「L1+L2 计划已落：见 archive/plans/…」指针  
- Modify: `docs/archive/plans/README.md` — 登记本计划  

**Verify:** README 不再把「30 秒 gate」伪装成全新机器路径。

**Commit:** `docs: L1/L2 install funnel and default face honesty`

---

### Task 11: 发布门禁脚本 `scripts/l2_release_gate.py`

**Objective:** 打包后自动证明「别人那边有」。

**Files:**
- Create: `scripts/l2_release_gate.py`

**检查：**
1. zip 存在且 SHA256 匹配 SUMS  
2. zip 内：`orpath.bat`、`runtime/.../cli.js`、`demo/seed/live-btube/**`、`demo/seed/m0/**`、无 `.env`  
3. 解压到临时目录 → `orpath.bat setup --skip-npm`（node_modules 已在）→ doctor PASS  
4. `demo-m0 --slug l2gate-m0` 或 mock run 退出码 0（可 `--quick` 只检查 seed 文件 + doctor）  
5. watch_snapshot 对 live-btube 返回非空 stages 或 solution 路径  

**Wire:** `orpath.bat l2-gate`（可选）

**Verify:** pack 后 `python scripts/l2_release_gate.py --zip dist/....zip` → exit 0。

**Commit:** `test(release): l2_release_gate unpack doctor seed`

---

### Task 12: 手工 GitHub Release 流程（作者操作清单）

**Objective:** 真上传，别人 `irm` 可用。

**不写进 CI 也行（本切片可手动）；步骤必须文档化在 `docs/install.md`：**

1. 工作树干净；VERSION 已 bump。  
2. `python scripts/pack_release.py`  
3. `python scripts/l2_release_gate.py --zip dist/orpath-VERSION-win-x64.zip`  
4. `gh release create vVERSION dist/orpath-*.zip dist/SHA256SUMS dist/install.ps1 --title "…" --notes-file …`  
   （无 gh 则网页上传）  
5. 另一台机或干净目录实测 install.ps1。  
6. 给 README 徽章/链接指向 latest release。

**Verify:** 外机 doctor PASS + START-WATCH 默认 slug 有内容。

**Commit:** 无代码；Release 在 GitHub。

---

### Task 13:（可选同一里程碑）fullface 附加包

**Objective:** 「L1 树也要有」的完整 agents 轨迹。

**Files:**
- `scripts/pack_release.py --extra fullface` → `orpath-VERSION-win-x64-fullface-seed.zip` 仅含 `outputs/.agents/live-btube`  
- 或单一大包 `…-full.zip` = 标准 + agents  

**默认不阻塞 L2 标准包发布。**

---

## 4. 文件变更总表

| 动作 | 路径 |
|------|------|
| Create | `VERSION` |
| Create | `demo/seed/README.md` |
| Create | `demo/seed/m0/**` |
| Create | `demo/seed/live-btube/**` |
| Create | `scripts/export_demo_seed.py` |
| Create | `scripts/bootstrap_orpath.py` |
| Create | `scripts/install_demo_seed.py`（可合并进 bootstrap） |
| Create | `scripts/pack_release.py` |
| Create | `scripts/l2_release_gate.py` |
| Create | `scripts/install/install.ps1` |
| Create | `scripts/install/install.sh` |
| Create | `docs/install.md` |
| Modify | `scripts/orpath_doctor.py` |
| Modify | `orpath.bat` / `orpath.sh` |
| Modify | `README.md` / `ORPATH.md` |
| Modify | `START-WATCH.bat`（注释/缺 seed 提示） |
| Modify | `docs/archive/plans/README.md` |
| Modify | `docs/onboarding-research.md`（指针） |
| Out | 不改 `tools/solve_*` 核心算法；不提交 `.env` |

---

## 5. 风险与权衡

| 风险 | 缓解 |
|------|------|
| `node_modules` 含 **native** 扩展，Win zip 在 Linux 不能用 | 主打 win-x64；其它平台 setup 强制 `npm ci` |
| zip 体积 200MB+ | 半肥必要；GitHub Release 可接受；git 主分支仍瘦 |
| seed 数字过期/与代码行为不一致 | seed 旁 README + m0 可 `demo-m0` 重跑；gate 查 validate 文件存在 |
| 用户以为 seed = LIVE 刚跑完 | claim ladder：seed=回放；LIVE 需 key |
| 拷贝 venv 的诱惑 | **禁止**；只 pip |
| install.ps1 执行策略 | 文档：`Set-ExecutionPolicy` 或 `powershell -File`；提供手动解压路径 |
| 密钥误打包 | pack_release 黑名单 + gate 扫 `.env` / `sk-` 模式 |
| 「全都要有」理解成 166MB agents | 标准包瘦 seed；fullface 可选 Task 13 |

---

## 6. 验收清单（DoD）

- [ ] 干净 Windows：仅装 Python+Node，无本仓历史 → `install.ps1` 或解压 zip + `setup` → **doctor PASS**  
- [ ] **START-WATCH.bat**（默认 live-btube）能开浏览器且 **非空过程/有 solution 线索**  
- [ ] `demo-m0` 可重新跑出 solution+validate  
- [ ] 无 `.env` 在 zip / git seed 内  
- [ ] `l2_release_gate` 绿  
- [ ] README 路径与 Feynman 同级清晰（Install → Setup → Wow）  
- [ ] main 仓仍无 `node_modules`/venv（瘦）  
- [ ] 作者本机原有能力：menu、watch-run、gates、LIVE（有 key）均保留  

---

## 7. 建议实施节奏

| 日序 | 交付 |
|------|------|
| D1 | Task 1–2 seed + export |
| D1–D2 | Task 3–6 setup + doctor + launcher |
| D2 | Task 7 pack_release |
| D3 | Task 8–9 install 脚本 |
| D3 | Task 10 文档 |
| D3–D4 | Task 11 gate + Task 12 真发一个 **pre-release** |
| 可选 | Task 13 fullface |

---

## 8. 与旧计划关系

- `docs/onboarding-research.md`：调研结论；本计划 = **L1+L2 落地施工单**  
- `2026-07-31_feynman-style-orpath-rearch.md`：launch/SYSTEM 对齐（**另一条线**）；本计划 **不阻塞** 于 F1–F12，只做分发对等  
- specs：不降低数字真相与 claim ladder  

---

## 9. 开放问题（实现前可默认如下）

| # | 问题 | 默认（可改） |
|---|------|----------------|
| Q1 | 首版版本号 | `0.2.0` |
| Q2 | 标准包是否含 agents 166MB | **否**；fullface 可选 |
| Q3 | seed 是否进 main git | **是**（瘦身集） |
| Q4 | Linux 是否首发 | **否**；仅 win-x64 标准 + sh best-effort |
| Q5 | install 默认目录 | `%LOCALAPPDATA%\Programs\orpath` |
| Q6 | 无 key 时 setup 是否算成功 | **是**（doctor PASS + WARN） |

---

## 10. 执行手令（批准后）

1. 按 Task 1→12 顺序改代码，每 Task 一次 commit。  
2. 本地 `pack_release` + `l2_release_gate`。  
3. 用户执行 GitHub Release 上传（或授权 `gh`）。  
4. 用临时目录模拟「别人机器」走验收剧本。  

**批准前不实施。**
