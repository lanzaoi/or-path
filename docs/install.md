# OR-Path 安装与部署指南（Release 安装包 · 源码部署）

**目标：** 开箱即用、一键启动 Web Studio 智能工作舱与运筹求解全流程。  
**使用教程（详细）：** [`user-guide.md`](user-guide.md)  
**当前版本：** 仓库根 `VERSION`（**1.0.0 正式版**）

---

## 1. 系统要求与环境准备

系统已全量升级为**纯 Python 原生架构**，已彻底剥离历史 Node.js `pi` CLI 子进程依赖，**无需安装任何 Node.js / npm 运行时**。

| 组件 | 最低要求 | 推荐配置 | 说明 |
|------|----------|----------|------|
| **操作系统** | Windows 10+ / Linux / macOS | Windows 11 / Ubuntu 22.04+ (WSL2) | 双端原生支持 `START.bat` / `START.sh` |
| **Python** | Python 3.11 – 3.14 | Python 3.12+ | 建议使用专用虚拟环境 `.venv` |
| **磁盘空间** | 1.0 GB 可用空间 | 2.0 GB+ | 包含 27 工业求解器矩阵与本地运筹知识库 |
| **API 密钥** | 可选（离线回归不需要） | 科大讯飞星火 `spark-x2.6` 或 DeepSeek Key | 仅在运行真多智能体闭环研判与写论文时需要 |

---

## 2. Release 正式版安装包（推荐普通用户）

### v1.0.0 正式版一键安装

通过 PowerShell 一键拉取并安装官方正式发行版：

```powershell
irm https://github.com/lanzaoi/or-path/releases/download/v1.0.0/install.ps1 | iex
```

安装程序默认释出至目录：`%LOCALAPPDATA%\Programs\orpath`

安装完成后直接运行：
```bat
cd %LOCALAPPDATA%\Programs\orpath
START.bat
```
浏览器将自动弹出并呈现 Web Studio 智能工作台。

---

## 3. 源码 Clone 部署（面向开发者与参赛队员）

```bash
# 1. 克隆代码仓库
git clone https://github.com/lanzaoi/or-path.git
cd or-path

# 2. 安装 Python 核心依赖
.venv/bin/pip install -r requirements.txt

# 3. 运行环境诊断
.venv/bin/python scripts/orpath_doctor.py

# 4. 一键启动 Web Studio 智能做题工作舱
# Windows 环境:
START.bat
# Linux / macOS / WSL 环境:
./START.sh
```

---

## 4. Release 打包与自检指南（Maintainer）

```bash
# 1. 确认版本文件
cat VERSION  # 1.0.0

# 2. 导出或校验演示种子
.venv/bin/python scripts/export_demo_seed.py --slug all

# 3. 执行官方多平台打包（生成 zip 与 SHA256SUMS）
.venv/bin/python scripts/pack_release.py --platform win-x64
.venv/bin/python scripts/pack_release.py --platform linux-x64

# 4. 运行 Release 完整性校验门禁
.venv/bin/python scripts/l2_release_gate.py --zip dist/orpath-1.0.0-win-x64.zip --quick
.venv/bin/python scripts/l2_release_gate.py --zip dist/orpath-1.0.0-linux-x64.zip --quick

# 5. 发布 GitHub Release
# gh release create v1.0.0 dist/orpath-1.0.0-win-x64.zip dist/orpath-1.0.0-linux-x64.zip dist/SHA256SUMS dist/install.ps1 --title "OR-Path v1.0.0 Official Release" --notes-file docs/archive/releases/v1.0.0-notes.md
```

---

## 5. 常见问题与排查

| 异常现象 | 根因排查 | 解决方案 |
|----------|----------|----------|
| 缺少 C 库编译错误 | 缺少 C/C++ 编译器 | Windows 安装 Visual C++ Build Tools；Linux 执行 `apt install build-essential` |
| Web Studio 界面空白 | 静态资产未构建 | 执行 `.venv/bin/python orpath/web/build.py` 重新生成静态页面 |
| 离线回归挂起 | 误触实时 API 调用 | 确认环境变量设置 `ORPATH_LIVE_SUBAGENT=0` |
| 端口冲突 (8000/8765) | 历史服务未关闭 | 任务管理器关闭旧 Python 进程，或指定端口 `START.bat --port 8080` |
