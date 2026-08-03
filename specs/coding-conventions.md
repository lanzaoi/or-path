# Coding Conventions — 编码约定

**对齐：** `product-flow-sdd.md`  
**状态：** LAW 2026-08-01

---

## 1. 语言与运行时

| | |
|--|--|
| 产品胶水 | Python 3.11+（`.venv-314` 常用） |
| 门禁 | `PYTHONNOUSERSITE=1`，清 PYTHONPATH |
| pytest | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` / `-p no:langsmith` |
| Pi | Node runtime/；DeepSeek |

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
- 新 adapter 走注册法（solvers 分册）  

---

## 4. Windows

- bat CRLF ASCII 无 BOM  
- 子进程 UTF-8  
- 临时验证脚本写 `%TEMP%`，不用 MSYS `/tmp`+venv 混用翻车  
- 多 hunk 改 bat 易碎 → 整文件重写  

---

## 5. 测试

- 契约边界：空/None/非法键  
- 负例：坏 schema、HUMAN 天花板  
- 不把 live DS 烧进默认 gate  

---

## 6. 文档

- 行为变 → 先 specs  
- 中文用户文档默认中文  
- skill 不复制大段法条  

---

## 7. 格式

- Python：项目既有风格；不强行全仓 reformat  
- JSON：UTF-8  
