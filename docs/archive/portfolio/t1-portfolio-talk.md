# T1 portfolio talk track (~30s)

**One-liner:** 带验证关卡的 Supervisor–Worker 流水线——Pi 真子 Agent 隔离研究/建模，LangGraph 管阶段，OR 数字只来自求解工具。

**30 秒口述：**

1. **问题：** LLM 直接算最短路会幻觉；我们要可检多 Agent + 确定性数字。  
2. **做法：** `or-researcher` / `or-modeler` 等是 **pi-subagents 真子会话**（有 transcript）；建模 schema **禁止 objective**；`solve_mock` / NetworkX 出 **42**。  
3. **关卡：** schema 门、R1 引用、R2 数字 ⊆ solution；论文最多改 2 轮否则 HUMAN_REQUIRED。  
4. **流程老板：** LangGraph `orpath/run_t1.py` 管 now→next；OpenPi/Pi 做 live 委派。  
5. **证据：** `docs/t1-evidence.md` + `.pi-subagents/artifacts/*_transcript.jsonl`。

**不要说：** 我们用 Hermes 当 OR 运行时；Feynman 是主壳；Agent Teams/消息总线是主架构。
