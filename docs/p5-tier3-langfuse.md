# P5 Tier-3：可选 Langfuse 表面

Langfuse **不替脸**。OR-Path 的产品主界面仍是 `orpath.bat watch` / `watch-run`；即使没有 Langfuse，Watch 也必须展示阶段、lead/sub 轨迹和 solution/validate 路径。

当前实现只提供诚实的可选开关与状态提示：

```bat
set ORPATH_LANGFUSE=1
```

打开后，Watch 的 `tier3.enabled` 会变为 true，并可显示 `LANGFUSE_HOST` / `LANGFUSE_BASE_URL`。这**不代表**控制面已经完成自动 span 埋点，也不会自动上传模型轨迹。

边界：

- 已做：Watch Tier-3 状态、开关、说明入口。
- 未做：LangGraph/Pi 全链路 span、云端项目初始化、多租户权限。
- 密钥不得进入 Git；默认 gate 使用 `ORPATH_LANGFUSE=0`，不访问云端。
