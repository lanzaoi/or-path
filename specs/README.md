# OR-Path `specs/` — 核心系统规范索引（SDD 全册）

**地位：** 本目录是 OR-Path 产品的 **核心硬法（Living Law）**。所有的代码实现、智能体调度、求解器集成与门禁逻辑必须无条件服从本规范群。  
**版本更新：** 2026-11（全量升级为精简 4 智能体 + 10 领域装备包 + 27 工业求解器 + Web Studio 架构）

---

## 1. 冲突优先级（Conflict Priority）

任何行为或实现产生歧义时，依以下严格递减顺序裁定：

```text
1. 可运行源码 + 独立物理门禁真实输出（Numbers Truth）
2. specs/product-flow-sdd.md     ← 产品总流程与主契约
3. specs/architecture.md         ← 系统架构法（5 大支柱）
4. specs/process-visibility.md   ← 过程透明度与 Live Watch 契约
5. specs/solvers-and-validate.md ← 27 求解器与 DIMO 独立验算
6. specs/multi-agent.md          ← 4 常驻特种兵与上下文隔离规范
7. AGENTS.md                     ← 根目录常驻开发公约
8. specs/** 其它分册
9. docs/**                       ← 用户指南、SOP 与操作手册
10. docs/archive/*               ← 历史归档（仅供参考，不具法律效力）
```

---

## 2. 规范分册地图（Specification Directory）

| 规范文件 | 核心主题 | 何时必读 |
|----------|----------|----------|
| **[`architecture.md`](architecture.md)** | ★ 5 大支柱、LangGraph 控制面与端到端系统架构 | 重构、修改拓扑或理解系统全貌前 |
| **[`product-flow-sdd.md`](product-flow-sdd.md)** | ★ 题目摄入至论文评审的完整产品主数据流 | 新增工作流或修改阶段流转前 |
| **[`process-visibility.md`](process-visibility.md)** | ★ Web Studio 与 Live Watch 全量透明过程看板规范 | 调整前端展示或过程埋点前 |
| **[`multi-agent.md`](multi-agent.md)** | ★ 4 常驻特种兵、10 装备包与上下文单向传递规范 | 修改智能体 Prompt、工具绑定或调用逻辑前 |
| **[`solvers-and-validate.md`](solvers-and-validate.md)** | ★ 27 工业求解器矩阵、接口契约与 DIMO 5 类变异验算 | 新增/修改求解器或校验逻辑前 |
| **[`control-plane.md`](control-plane.md)** | 阶段状态机、确定性条件边分支与失败重试上限 | 调整状态流转、分支路由或重修计数前 |
| **[`paper-and-review.md`](paper-and-review.md)** | 六章学术论文标准结构、预渲染表格与 R1/R2 审核 | 修改论文生成 Prompt 或评审门禁前 |
| **[`problem-intake.md`](problem-intake.md)** | 文件夹拖拽、多模态 OCR、结构化数据探针规范 | 调整题目摄入、解析或前置探针前 |
| **[`contracts.md`](contracts.md)** | JSON 输入/输出契约（Problem / Schema / Solution） | 变动数据通信格式前 |
| **[`engineering-hygiene.md`](engineering-hygiene.md)** | 编码规范、Git 卫生与大模型辅助开发自律 | 编写代码与提交 Git 仓库前 |
| **[`gates-and-dod.md`](gates-and-dod.md)** | 全量回归门禁定义与 Definition of Done 准则 | 任务收尾与版本发布前 |
| **[`knowledge-and-retrieval.md`](knowledge-and-retrieval.md)** | 本地 ONNX `bge-m3` + BM25 混合检索与 Skills 知识库 | 修改运筹技能库或知识向量化前 |
| **[`memory.md`](memory.md)** | L0–L1 任务工件沉淀、禁止存储口头假最优解 | 处理工作流持久化与上下文缓存前 |
| **[`human-steer-and-pi-guidance.md`](human-steer-and-pi-guidance.md)** | Web Studio 人机协同交互确认与断点控制规范 | 调整参数覆盖弹窗或离线人控机制前 |
| **[`product-scope.md`](product-scope.md)** | 业务能力边界、宣称天花板与技术限制说明 | 对外宣称能力或编写里程碑前 |

---

## 3. 推荐阅读路径（新手与新会话）

```text
1. architecture.md          ── 掌握 5 大支柱与系统全貌
2. product-flow-sdd.md      ── 掌握题目流转主干逻辑
3. solvers-and-validate.md  ── 掌握 27 工业求解器与 Numbers Truth 铁律
4. multi-agent.md           ── 掌握 4 常驻专家与 10 领域装备包
5. control-plane.md         ── 掌握 LangGraph 状态机与确定性流转分支
6. process-visibility.md    ── 掌握 Web Studio 实时看板数据源
7. paper-and-review.md      ── 掌握 6 章学术论文生成标准与评审规范
```

---

## 4. 规范维护守则

1. **唯一真相原则**：当代码与规范发生冲突，且代码逻辑更加健全经门禁验证，必须立即同步更新对应 `specs/` 规范文件。
2. **严禁大段复制**：各类 Skill 与 Doc 严禁全文粘贴规范法条，必须以 Markdown 链接指向本目录。
3. **退役标记清晰**：任何废弃机制（如旧 Node CLI 依赖、旧单域复制智能体）必须明确标记退役或归档，严禁死灰复燃。
