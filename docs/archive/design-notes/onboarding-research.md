# OR-Path 他人如何使用 · 安装形态研究（对照 Feynman 等）

**状态：** 调研笔记；**L1+L2 已按计划实施** → `docs/archive/plans/2026-08-04_l1-l2-release-parity.md` · 操作 **`docs/install.md`**  
**日期：** 2026-08-04  
**问题：** 别人应如何使用本项目？要不要做「自动安装 Pi」脚本？市面成熟方案是什么？

---

## 0. 结论先讲

| 问题 | 结论 |
|------|------|
| 别人今天怎么用？ | **Clone/拷贝安装树 → 装 Python venv + Node 依赖 → 配 key → `orpath.bat doctor` → `START-WATCH` / menu**。没有一键公网安装器。 |
| 要不要自动装 Pi？ | **要，但是「bootstrap 安装器」而不是只装 Pi。** Pi 只是运行时一层；缺的是 **Python venv + runtime npm + doctor + setup 向导** 的一体化入口。 |
| 对标谁？ | **近亲：Feynman**（同 Pi + multi-agent + watch/serve）。**通用 agent 安装范式：Claude Code / Hermes**（curl\|bash + setup + doctor）。**不要**做成「再包一层 Feynman 主壳」（`product-scope` OUT）。 |
| 现阶段优先级 | 若受众是 **作品集面试官 / 自己换机**：先做 **`orpath.bat setup` / `install.ps1` 本机 bootstrap** 即可。若要 **公网一键下载**：再做 release bundle + SHA256（Feynman 级），成本高一个数量级。 |

---

## 1. 本项目「别人」是谁

按 `specs/product-scope.md`，当前不是 SaaS 用户，而是：

1. **作品集评审 / 面试官** — 本机或录屏复现 M0–M2 + Watch 脸  
2. **作者自己** — 换机、重装、搬迁 `ORPATH_HOME`  
3. **未来贡献者 / 同学** — 需要可复现环境，不是猜路径  

因此 onboarding 目标应是：**30–90 分钟内 doctor PASS + 一条 mock demo + 打开 Watch**，而不是「全球 npm 日活」。

---

## 2. 今天别人实际要走的路径（诚实版）

仓库已有的「半产品」入口：

| 层 | 已有 | 缺口 |
|----|------|------|
| 产品脸 | `START-WATCH.bat` / `START-CASE.bat` / `orpath.bat face\|menu\|watch-run` | 假定环境已装好 |
| 健康检查 | `orpath.bat doctor`（agents、pi-subagents、runtime CLI、specs、workdir） | **不装**依赖，只报 BAD |
| 可搬迁 | `ORPATH_HOME` / `ORPATH_WORKDIR`（`docs/archive/ops/t2-relocatable.md`） | OpenPi 已删，文档仍提 openpi 历史句 |
| Pi 运行时 | `runtime/package.json` pin：`pi-coding-agent@0.82.1` + `pi-subagents@0.37.2`；`pi.bat` 调 `runtime/.../cli.js` | **无根级 install 脚本**；需人手 `npm i` + 系统 Node |
| Python | `requirements.txt` + `.venv-314`（launcher 优先） | **无 create-venv 脚本** |
| 密钥 | `.env.example` / `orpath.env.example` | **无 `orpath setup` 向导** |
| 文档 | `README.md`「30 秒上手」、`ORPATH.md` | 30 秒路径写的是 **已装好机器上的 gate/watch**，不是 fresh clone |

### 2.1 Fresh machine 真实清单（今天）

```text
前置：
  - Git
  - Python 3.11+（推荐 3.11/3.14 之一，与 .venv-314 命名对齐或改名）
  - Node.js ≥ 22（pi.bat / Feynman 同代；本机常见 22.x）
  - （可选）DeepSeek API key；OCR 重度再加 ppocr 路径

步骤：
  1. git clone <repo>  或  拷贝安装树到 D:\apps\orpath
  2. cd 安装根
  3. python -m venv .venv-314
     .venv-314\Scripts\pip install -r requirements.txt
  4. cd runtime && npm install && cd ..
  5. copy .env.example .env  → 填 DEEPSEEK_API_KEY 等
  6. orpath.bat doctor          # 必须 PASS
  7. orpath.bat m0-gate 或 demo-m0 --slug m0
  8. START-WATCH.bat            # 或 watch --slug live-btube / m0
```

**LIVE 多 Agent** 还要：Pi 能登录模型、`.pi/settings.json` 含 `pi-subagents`、`.pi/agents/or-*.md` 齐全（doctor 已查）。  
**门禁路径** 默认 live OFF，可在无 key 时用 mock 证明控制面。

### 2.2 推荐给外人的「最小成功路径」

| 角色 | 命令 | 看见什么 |
|------|------|----------|
| 只看脸 | `START-WATCH.bat`（默认 live-btube 若产物在） | 浏览器过程台 |
| 可信数字 demo | `orpath.bat demo-m0` → `watch --slug m0` | solution+validate + 证据清单 |
| 边跑边看 | `orpath.bat watch-run --keep-watch` | mock 流水线 + Watch |
| 真 LIVE | `watch-run --live` 或 `START-CASE` + intake | 慢；要 key；看 L1 sub toolCall |
| 工程证 | `doctor` → `m0-gate` → `m1-gate` / `m2-gate` | 退出码 0 |

**话术边界（claim ladder）：** gate 绿 ≠ 体验完成；开文件夹 ≠ 实时可视；Hermes 不是产品运行时。

---

## 3. 市面成熟方案（深度对照）

### 3.1 共性模式（2025–2026 agent 产品）

成熟 agent CLI/桌面几乎都收敛到同一套漏斗：

```text
1) 一行安装器（curl|bash / irm|iex / 桌面 .msi）
2) 自带或固定运行时（bundled Node，或声明 engine）
3) setup 向导（模型 / key / OAuth）
4) doctor（失败可诊断）
5) 默认一条「wow」命令（REPL / serve / demo）
6) 可选：skills-only 轻量安装、pin 版本、SHA256、update 通道
```

| 产品 | 安装 | 运行时策略 | 配置 | 验证 | 默认 wow |
|------|------|------------|------|------|----------|
| **Feynman** | `curl …/install \| bash`；Win `install.ps1`；或 `npm i -g` | **Standalone 带 pin 的 Node bundle** + SHA256；内嵌 Pi workspace（`prepare-runtime-workspace.mjs`） | `feynman setup` | `feynman doctor` / `--version` | `feynman` / `deepresearch` / `serve` |
| **Claude Code** | 官方 native installer（curl/ps1）；winget/brew；npm 降级 | Native 二进制优先，免本机 Node | 浏览器登录 | `claude --version` | `claude` 进项目 |
| **Hermes** | Desktop 安装包；`install.sh` / `install.ps1` | 安装器拉 Node 等 | `hermes setup` | `hermes doctor` | `hermes` 聊天 |
| **OpenHands** | npm global canvas 或 Docker sandbox | 声明 Node+uv；或容器隔离 | 首次 4 步 wizard | 健康检查 | Agent Canvas |
| **OR-Path（今）** | **无** | **本机 Node + 本机 venv + runtime/npm** | 手改 `.env` | `orpath doctor` | `START-WATCH` / menu（环境好才行） |

### 3.2 Feynman：最近的「正确参考实现」

本仓 `vendor/feynman` 只读；**产品法明确 OUT「Feynman 主开发壳」**，但 **安装工程可学**：

1. **双通道**  
   - 大众：standalone zip/tar + launcher 进 PATH + checksum  
   - 开发者：`npm i -g @companion-ai/feynman`（Node `>=22.22 <26`）

2. **Pi 不是用户自己 npm 的**  
   - 发布时 `prepare-runtime-workspace.mjs` 打好 **runtime-workspace.tgz**（pin Pi 0.82.x、打 patch、prune）  
   - 用户侧 `feynman update` 只刷 **环境内 Pi packages**，整包升级靠 **重跑 installer**

3. **Skills-only 分流**  
   - 不要完整终端的人：`install-skills` → Codex / `.agents/skills` / OpenCode  
   - OR-Path 类比可以是：只给 `or-*.md` + tools 契约的「gate 评测包」，与完整 Watch 产品拆开

4. **文档漏斗**  
   Installation → Setup → Quickstart → Workbench；README 顶部就是 install 两行

5. **与 OR-Path 同构点**  
   - 都 wrap **Pi + pi-subagents**  
   - 都有 outputs/notes/papers、slug、provenance  
   - Feynman 有 `serve` workbench；OR-Path 有 **Watch HTML 脸**（更轻、更 OR 专用）  
   - Feynman agents：researcher/reviewer/writer/verifier；OR-Path：or-orchestrator + 五角色 + **solve/validate 硬闸**

**不要抄的部分：** Bio tools 大盘、全站 workbench、把 OR-Path 嵌进 Feynman CLI。OR-Path 差异化是 **运筹数字真相 + LG 控制面 + Watch 过程法**。

### 3.3 Claude Code / Hermes：安装器「行业默认」

- **一行脚本 + 可选桌面包** 已成为用户心理锚点  
- **setup 与 install 分离**：装完不等于配完  
- **doctor 一等公民**：支持成本主要靠它降  
- Windows：**PowerShell irm|iex** 与 bash 并列，不是事后补丁  

OR-Path 当前 Windows 主场更强（一堆 `.bat`），应对齐 **`install.ps1` + `install.sh`**，而不是只写 Linux 思维。

### 3.4 OpenHands 等：重运行时用 Docker 旁路

若 OR 求解 + OCR 依赖地狱，业界会给 **Docker 一键** 作为 Option B。  
OR-Path 短期可不做镜像；长期「面试官 5 分钟」可考虑 **demo 容器（仅 mock + watch）**。

---

## 4. 「要不要自动安装 Pi」——拆开答

### 4.1 用户真正卡的不是「Pi」一个词

Doctor 已证明多 Agent 完整安装 = 交集：

```text
runtime/node_modules/@earendil-works/pi-coding-agent/dist/cli.js
.pi/settings.json → packages 含 pi-subagents
.pi/agents/or-*.md × 6
tools/ + orpath/ + specs/
Python 能 import langgraph/ortools
可选：DEEPSEEK_API_KEY
```

只写 `npm i -g @earendil-works/pi-coding-agent` **不够**：  
全局 Pi ≠ 本仓 `runtime/` 路径；`pi.bat` **写死**看 `runtime\node_modules\...`；subagent 扩展与 agents 在 **项目 `.pi/`**。

### 4.2 推荐做的三档（由易到难）

| 档 | 交付物 | 解决谁 | 工作量 | 建议 |
|----|--------|--------|--------|------|
| **A. Bootstrap（应做）** | `scripts/bootstrap_orpath.py` + `orpath.bat setup`：建 venv、`pip -r`、`npm ci` in runtime、拷 `.env.example`、跑 doctor | 自己换机、贡献者、面试官 clone | 小 | **立刻值得** |
| **B. Guided setup** | `orpath.bat setup --wizard`：问 DeepSeek key、写 `.env`、可选模型、打印下一条 wow 命令 | 非作者用户 | 中 | A 稳定后 |
| **C. Release installer（可后做）** | GitHub Release：源码树或「runtime 预装 zip」+ `install.ps1` SHA256；PATH 可选 | 公网陌生人 | 大（要对标 Feynman 发布工程） | 作品集外链前再评估 |

**不推荐：**

- 只装全局 Pi、让用户自己拼 PYTHONPATH  
- 把 `vendor/feynman` 当安装源给用户  
- 在无 release 工程时宣称 `curl|bash` 生产级  
- 自动 `npm i` 最新 Pi 漂版本（应 **pin**，与 `.env.example` 的 `PI_NPM_VERSION` 一致）

### 4.3 A 档伪代码（实现时遵循）

```text
orpath setup
  1. 检测 python3.11+ / node22+
  2. 若无 .venv-314 → python -m venv && pip install -r requirements.txt
  3. 若无 runtime/node_modules/.../cli.js → cd runtime && npm ci || npm install
  4. 确保 .pi/agents 与 settings（从模板；勿覆盖用户 key）
  5. 若无 .env → copy example，打印「请填 DEEPSEEK_API_KEY」
  6. 调 orpath_doctor；失败 exit 1 + 中文修复列表
  7. 成功打印：
       orpath.bat demo-m0 --slug m0
       START-WATCH.bat
```

Pin 来源单一：`runtime/package.json` + `.env.example` 注释。

### 4.4 Pi 版本与 Feynman 对齐策略

| 策略 | 含义 |
|------|------|
| **跟随 pin** | 与 Feynman 常用 Pi 同大版本（当前仓 0.82.1）减少「subagent 行为漂移」 |
| **不嵌入 Feynman** | 不调用 feynman CLI；不把 research skills 当 OR 主路径 |
| **patch 谨慎** | Feynman 对 Pi 有大量 patch；OR-Path 目前靠 stock npm — 保持简单，除非撞 bug |

---

## 5. 「别人如何使用」分层说明书（可直接贴 README）

### 层 0 — 观众（不装）

- 看录屏 / 截图：Watch L0–L4 + `outputs/*-solution.json` + validate  
- 读 `ORPATH.md` + `docs/m0-smoke.md`

### 层 1 — 试用者（本机，mock）

```bat
git clone ... && cd orpath-install
orpath.bat setup          :: 待实现；现用手装 §2.1
orpath.bat doctor
orpath.bat demo-m0 --slug m0
START-WATCH.bat m0
```

### 层 2 — 完整产品路径（LIVE + 案例夹）

```bat
START-CASE.bat
:: 或
orpath.bat watch-run --workdir %USERPROFILE%\Documents\orpath-cases\demo1 --slug demo1 --live --keep-watch
```

契约：`ORPATH_HOME`=代码；`ORPATH_WORKDIR`=案例数据。

### 层 3 — 工程贡献者

```bat
orpath.bat m0-gate
orpath.bat m1-gate
orpath.bat m2-gate
:: 重门禁按需 gate-t3 / gate
```

读 `specs/` 再改代码。

---

## 6. 文档与入口改造建议（不实施，仅清单）

1. **README 顶部**改为：Install（A 档命令）→ Doctor → Demo M0 → Watch（现在「30 秒」假设环境已好，对外易翻车）  
2. **新增** `docs/install.md`：前置版本表、Windows/macOS/Linux、故障树（doctor BAD → 修复）  
3. **`orpath.bat setup`** 接入 bootstrap；`doctor` 在缺失 runtime 时提示 `setup`  
4. **删/改** relocatable 文中过时 `openpi` 句，避免新人找已删壳  
5. **不要**新建第二套菜单；保持 `START-*.bat` 为 wow 入口  
6. 作品集页写清：**数字来自 solver+validate；Watch 是过程脸；非 Feynman/Hermes 套壳**

---

## 7. 与竞品定位一句话

| 若用户要… | 去… | 不要用 OR-Path 硬充 |
|-----------|-----|---------------------|
| 文献深研 / paper-code audit | **Feynman** | vendor 参考即可 |
| 通用编程 agent | **Claude Code / Hermes / OpenHands** | — |
| 运筹题：建模隔离 + **求解器出数** + validate + 过程台 | **OR-Path** | — |

OR-Path 的安装体验应 **达到 agent 行业地板（setup+doctor+demo）**，产品内核保持 **OR 硬闸**，而不是追求 Feynman 级发布工厂——除非决定做公网分发。

---

## 8. 建议决策（供你拍板）

| 决策项 | 建议 |
|--------|------|
| 现在做自动装 Pi？ | **做 A：bootstrap 装 runtime 内 pin 的 Pi + Python，不是全局 Pi** |
| 公网 curl 安装器？ | **暂缓**（无私有 release 流水线前） |
| 文档 | 立刻可改 README「外人路径」；实现 setup 后改「30 秒」为真 |
| Docker demo | 可选，面试官场景；非 V0 阻塞 |
| 对标叙事 | 「安装学 Feynman/Hermes；产品不是 Feynman」 |

---

## 9. 主要来源

- 本仓：`README.md` · `ORPATH.md` · `runtime/README.md` · `scripts/orpath_doctor.py` · `docs/archive/ops/t2-relocatable.md` · `specs/product-scope.md` · `vendor/feynman/README.md` + `website/.../installation.md` + `install.ps1` + `prepare-runtime-workspace.mjs`  
- 公开产品：Feynman（feynman.is / companion-inc/feynman）、Claude Code 官方安装范式、Hermes Agent 官方 Installation/Quickstart、OpenHands Agent Canvas first-time setup  

---

## 10. 下一步（若批准实现）

1. 实现 `scripts/bootstrap_orpath.py` + `orpath.bat setup`  
2. doctor 失败时打印 setup 提示  
3. README 增加「全新机器」章节并链本文  
4. （可选）`install.ps1` 仅封装：clone 已存在目录上的 setup + PATH 提示  

**未批准前不改启动器行为。**
