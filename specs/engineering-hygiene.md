# Engineering Hygiene — 编码 · Git · AI 卫生

**对齐：** `product-flow-sdd.md`  
**状态：** LAW 2026-08-04（合并原 `coding-conventions.md` + `git-and-ai-hygiene.md`）

---

## 1. 语言与运行时

| | |
|--|--|
| 产品胶水 | Python 3.11+（`.venv-314` 常用） |
| 门禁 | `PYTHONNOUSERSITE=1`，清 PYTHONPATH |
| pytest | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` / `-p no:langsmith` |
| Pi | Node runtime；DeepSeek 等 |

---

## 2. 模块边界

| 做 | 不做 |
|----|------|
| 经 control_plane / dispatch / paper_protocol / subagent_dispatch | 节点直 import 深层 runtime 绕过门面 |
| 小 PR/切片 | 无关大重构 |
| 路径 pathlib | 假设唯一盘符硬编码业务 |

---

## 3. 数字与 MA

- 禁止 LLM 写 objective  
- 真 sub 必须 json tool 证据  
- 新 adapter 走注册法（`solvers-and-validate.md`）  

---

## 4. Windows

- bat CRLF ASCII 无 BOM  
- 子进程 UTF-8  
- 临时验证脚本写 `%TEMP%`，不用 MSYS `/tmp`+venv 混用  
- 多 hunk 改 bat 易碎 → 整文件重写  

---

## 5. 测试

- 契约边界：空/None/非法键  
- 负例：坏 schema、HUMAN 天花板  
- 不把 live DS 烧进默认 gate  
- R2/claim_map：过程计数（`claims_recorded` 等）不得当结果数字  

---

## 6. 永不提交

| 项 |
|----|
| `.env` / 密钥 / token / PAT |
| 竞赛 PDF 大宗（desktop-attachments、inbox 题） |
| `outputs/` `notes/` `papers/` `runs/` 默认 |
| `knowledge/corpus/papers/` 大正文 · `inbox_pdf/` · 运行日志（默认可本地） |
| `node_modules/` `pi-main/` `vendor/` · `.pi/memory` DB |
| 整棵 `.hermes/` |

详见 `docs/repo-surface.md`。

---

## 7. Git 操作

- **禁止**盲目 `git add -A`  
- 提交前 `git status` / diff  
- 大二进制需显式理由  
- 远端主仓：`lanzaoi/or-path`（public）；可选 `origin-rika`  
- **禁**把 PAT 写进 chat / 提交  

---

## 8. AI 协作

| | |
|--|--|
| 产品法 | specs 优先于 chat |
| Hermes | 规划/门禁/监控；Pi 做题时不代改 objective |
| DeepSeek | 不做环境/装依赖（用户偏好） |
| 假绿 | 禁止 |

---

## 9. 文档与 skill

- 行为变 → 先 specs  
- 中文用户文档默认中文  
- skill **不**复制大段产品法；指针到 `specs/`  

---

## 10. 格式

- Python：项目既有风格；不强行全仓 reformat  
- JSON：UTF-8  

---

## 11. 提交前清单

- [ ] 无密钥 / 无竞赛原题 PDF  
- [ ] specs 已随行为更新  
- [ ] 相关 gate 想过是否要跑  
- [ ] HOME≠WORKDIR 路径未写死错根  

---

## 12. 忽略策略意图

| ignore | 原因 |
|--------|------|
| pi-main | 上游 monorepo 大；npm 装 runtime |
| vendor / third_party | 对照源；许可与体积 |
| openpi | 已删防回潮 |
