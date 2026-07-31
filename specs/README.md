# OR-Path `specs/` — 规范索引（SDD）

**地位：** 本目录是产品与工程的 **硬法（living law）**。  
实现、评审、closeout 与 chat 冲突时，优先级如下。

## 冲突优先级

```text
1. 可运行代码 + 门禁真实输出（t1_gate / t2_gate / t2_gate_cloud）
2. specs/**（本目录）
3. AGENTS.md（短指针 + Pi 会话纪律）
4. .hermes/plans/*（施工单；可过期）
5. docs/**（给人看的操作/证据，不发明新法）
6. IDEA.md / README 叙事
7. 聊天记录
```

Hermes `MEMORY.md` **不是**产品法，不得覆盖本目录。

## 阅读顺序（实现前）

1. `product-scope.md` — 做什么 / 不做什么 / 话术边界  
2. `architecture.md` — LG / Pi / gate / 双路径  
3. `control-plane.md` — 阶段图、字段 owner、回修阶梯  
4. `contracts.md` — JSON 形状  
5. `solvers-and-validate.md` — 求解与校验  
6. `multi-agent.md` — 角色与手递  
7. `knowledge-and-retrieval.md` — 知识竖切与 claim ladder  
8. `paper-and-review.md` — R1/R2/在线引用  
9. `memory.md` — 记忆分层  
10. `gates-and-dod.md` — T1/T2/T3/1.1 完成条  
11. `t3-lg-skeleton.md` — **T3 主法：LG 产品骨架 freeze**  
12. `t3-vrp-tw.md` — CVRPTW 叶（矩阵用）  
13. **`problem-intake.md` — 1.1 题面 OCR + 自主审读（intake）**  
14. **`1.2-architecture-soak.md` — 1.2 架构 soak（C 题试跑 / 圆管回退；非交卷 PASS）**  
15. `git-and-ai-hygiene.md` + `coding-conventions.md`  

## 与其他层的分工

| 层 | 路径 | 内容 |
|----|------|------|
| **Specs** | `specs/` | 稳定约束、非目标、验收定义 |
| **Plans** | `.hermes/plans/` | 本次任务切片与顺序 |
| **Docs** | `docs/` | 活：smoke / ADR / 1.0-closeout；历史：`docs/archive/`；导航：`docs/README.md` |
| **Code** | `orpath/`, `tools/`, `knowledge_svc/` | 实现 |
| **Harness** | 不建 `.agents/`（T2 锁 B） | Gemini 通道未启用 |

## SDD 循环

```text
读 specs → 按 plan 一个 Task → 路径白名单实现 → 真命令验收 → 行为变则改 specs
```

每个 Task 结束自检：

- [ ] diff 未越权  
- [ ] 验收命令已跑且如实记录  
- [ ] 无 `git add .` / 无密钥 / 无无关大重构  
- [ ] 若行为变化：已更新对应 spec  

## T2 grill 冻结

权威冻结表见 `gates-and-dod.md` §T2 Freeze，以及计划  
`.hermes/plans/2026-07-29_105620-t2-thick-full-stack.md`（实现前以 **specs 为准** 回写差异）。

**Grill 确认日：** 2026-07-29  
**实现通道：** Hermes 按 specs + plan 直接实现（Q9-A）。

## 维护

- 小行为变更：改对应单文件 + 本 README 索引若新增文件  
- 大范围重冻：先 grill / 更新 freeze 表，再改 specs，最后改 plan  
- 禁止在 skill 里复制大段产品法（易漂移）；skill 只指针到 `specs/`
