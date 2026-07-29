# Coding Conventions — 编码约定

## 语言与运行时

| 区域 | 约定 |
|------|------|
| LG / tools / knowledge_svc | Python 3.14 venv：`.venv-314` |
| Pi agents | Markdown under `.pi/agents/` |
| 标识符 | 代码英文；specs 中文叙述 |

## 环境变量（运行前）

```bat
set PYTHONNOUSERSITE=1
set PYTHONPATH=
set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
```

门禁子进程必须继承/强制上述，避免 user-site pydantic 污染（T1 教训）。

## 依赖

- 清单：`requirements.txt`  
- 安装通道：Hermes/用户 shell，**不用 DeepSeek 会话装环境**  
- 云：密钥只在 `.env`；模板 `.env.example` 无秘密  

## 测试

| 类型 | 标记建议 | 含义 |
|------|----------|------|
| 单元 | 默认 | 无外网 |
| cloud | `@pytest.mark.cloud` | 需密钥与网络 |
| 慢 | `@pytest.mark.slow` | ortools 大搜可选 |

诚实报告：`N passed` + 是否含 cloud。

## 代码风格

- 新代码：类型标注鼓励；公开 CLI 用 argparse  
- 失败：非 0 exit；stderr 人类可读  
- 少做无关重构；外科手术 diff  
- 不把产品逻辑写进 `pi-main/packages`  

## Windows

- 仓库脚本优先 `scripts/*.py`  
- 若写 `.bat`：CRLF + ASCII  
- 路径：工具内用 `pathlib`  

## 日志与隐私

- 禁止打印完整 API token  
- evidence 打码 `sk-...`  

## 实现顺序（T2）

遵循 plan S 序：**契约/求解/validate → LG → 知识 → bridge/memory → 门禁文档**。  
禁止未 validate 先宣称知识闭环完成。
