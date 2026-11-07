# 运筹建模与学术论文规范 SOP（OR-Path Paper Rubric）

> **权威层级：** 本 SOP 是 **Verifier / Writer 智能体**撰写与评审运筹优化（OR）论文的**软指引（Soft Rubric）**。
> **上游契约：** `specs/paper-and-review.md` · ADR-0004 · `orpath/paper_protocol.py` · `specs/engineering-hygiene.md`
> **配套硬门：** `tools/r1_cite_check.py` · `tools/r2_numeric_check.py` · `tools/r1_claim_map.py` · `tools/validate_solution.py`
> **版本：** 1.0（由旧架构 R1/R2 代码门禁 + Claim 证据链机制升维而来）

---

## 一、引言与核心原则

### 1.1 从「死板代码门禁」到「智能体软指引」

旧架构中，论文质量由**离线脚本硬门**裁决：R1 校验引用白名单、R2 校验数字是否落在 `solution.json` 的 token 集合内。硬门只有两种状态（PASS / FAIL），它**能阻止谎言，却不能教会 Writer 写出好论文**。

本 SOP 的升维逻辑：

| 维度 | 旧 R1/R2 硬门 | 本 SOP 软指引 |
|------|---------------|----------------|
| 作用对象 | 文本 token / URL 集合 | 写作决策、结构完整度、论证力度 |
| 判定方式 | 二值（PASS/FAIL） | 分档评分（缺失 / 勉强 / 充分 / 优秀） |
| 触发时机 | 论文环末尾（`review_pack`） | 写作前（`draft_paper`）即内联 |
| 对 LLM 的价值 | 只报错 | 既报错又给出「如何改进」的示范 |
| 失败模式 | 打回重写，浪费轮次 | 前置约束，避免返工 |

**核心理念：** 硬门是**底线（floor）**，软指引是**天花板（ceiling）**。Verifier/Writer 必须先在思维里内化本 SOP 的六章结构，让生成的草稿**一次逼近可发表状态**，再用 R1/R2 硬门做终检。**软指引不是硬门的替代品**——两者叠加使用：软指引塑造叙事与论证，硬门守住真实性红线。

### 1.2 两条不可妥协的铁律

1. **数字真实性（Numbers Truth）：** 论文中每一个目标值、代价、长度、调度时间、粒子数、覆盖率等**结果性数字**，必须严格来自求解器产物 `solution.json`（并由 `tools/validate_solution.py` 独立重算确认）。LLM **严禁虚构、外推、美化或「凑数」**任何最优值。见第三章。
2. **证据链闭环（Evidence-Chain Closure）：** 每一个核心事实主张（Claim）必须可溯源到**求解器数值、算法库文献、题目附件或检索证据**之一，并可被第三方复算。见第四章。

### 1.3 诚实声明（Honesty Statement）优先原则

论文**必须**在摘要与结果两处明确标注求解性质：

- 若 `solution.meta.proven_optimal == true` → 可写「在求解器模型下证明全局最优」。
- 若为搜索/可行轨（`exact == false`）→ **必须**写「搜索/可行轨，未证明全局最优」，禁止使用「全局最优 / 数学证明最优 / 保证最优」等肯定性措辞。
- 未标注时按最保守口径处理。**肯定性最优措辞 + 无 proven 标记 = FATAL 打回。**（对应 `tools/r1_claim_map.py::affirmative_global_opt_hits`）

### 1.4 软指引的适用边界

- 本 SOP 面向**运筹优化建模类**论文（最短路/TSP/VRP/JSSP/装箱/多目标芯片布局/微电网/圆管展开等）。
- 叙事质量（文笔、排版、图表美观）由**独立 polish 通道**负责，**不与数字真实性混算**。
- 软指引鼓励 Writer 发挥，但**绝不放宽** R1/R2/Claim 三条硬红线。

---

## 二、运筹优化学术报告标准结构

一篇合格的 OR 论文须依次包含以下六节。每节标注**必做项（MUST）**与**加分项（SHOULD）**，Verifier 依此打分。

### 2.1 摘要与关键指标速览

- **MUST**：一句话点明问题类与实例 ID（`problem_id` / `problem_class`）。
- **MUST**：直接给出目标值（objective）、求解状态（`status`：OPTIMAL / FEASIBLE / BLOCKED）、求解器（`solver`）。
- **MUST**：一句话诚实声明求解性质（精确/启发式/未证明全局最优）。
- **SHOULD**：关键指标速览表（目标值、运行时间、关键约束满足率、验证状态）。
- **禁止**：摘要中出现未在正文/结果中复现的数字；禁止营销式「首次解决」措辞。

### 2.2 问题重述与工程/物理假设

- **MUST**：重述原始题目来源（附件路径、题目编号），**不得凭记忆转述**。
- **MUST**：列出全部**建模假设**（连续性、确定性、无等待、容量约束、时间窗、批次余料可跨批继承等），并说明每条假设对结论的影响。
- **MUST**：定义符号表（决策变量、参数、集合），符号须与模型建立一节一致。
- **SHOULD**：说明假设的工程/物理合理性来源（引用题目附件或文献）。

### 2.3 数学规划模型建立（决策变量、目标函数、约束集合）

> 本节是论文的**学术核心**，Verifier 重点核查。

- **MUST**：显式给出三类要素：
  1. **决策变量**：`x_ij ∈ {0,1}`（路径选择）、`s_j ≥ 0`（开工时间）、`q_k`（批次余料量）等，含定义域与类型。
  2. **目标函数**：明确写出方向（min/max）与各项权重；多目标须给出标量化或 Pareto 处理方式。
  3. **约束集合**：逐条编号（C1、C2…），每条注明物理/工程含义（容量、时间窗、无重叠、覆盖完整、边界条件等）。
- **MUST**：说明模型**不含最优值**——模型建立一节只写结构，最优值留给结果一节。
- **SHOULD**：给出模型规模（变量数、约束数、非零元数），便于读者评估可解性。
- **禁止**：模型一节直接写「最优值为 X」（属结果性数字，须绑定 `solution.json`）。

### 2.4 求解策略与算子选型说明（算法复杂度与收敛性）

- **MUST**：说明求解器/算法选型及理由（例如：小规模精确轨用 CP-SAT/NetworkX/HiGHS；大规模用 OR-Tools Routing / ALNS）。
- **MUST**：定性或定量说明**复杂度**与**收敛性**（CP-SAT 分支定界/割平面、启发式不可回退全局最优、滚动时域 MPC 的可行性等）。
- **MUST**：声明求解参数（时间上限、迭代次数、随机种子），保证可复现。
- **SHOULD**：给出求解耗时与规模的关系曲线；对比不同算子的解质量/耗时权衡。
- **禁止**：声称启发式结果为全局最优；禁止用「调参后大幅提升」而无对照数据支撑。

### 2.5 数值计算结果与敏感性分析（必须附带真实重算数字与图表）

- **MUST**：所有数值**仅来自 `solution.json`**，且经 `tools/validate_solution.py` 独立重算。报告须写「重算值 = 求解器值」。
- **MUST**：核心结果表（目标值、关键子指标、对基准的提升率）——提升率等派生量须基于**已报告的实数**现场计算，不得另造。
- **MUST**：敏感性分析：至少变动一个关键参数（价格、容量、时间窗松紧、需求波动），报告目标值的**真实重算**变化；不可用推断代替。
- **SHOULD**：附折线图/柱状图/甘特图（如 JSSP 的逐机甘特图）；图表数据须与正文数字一致。
- **禁止**：LLM 自造表格、自造曲线、自造对比基线。

### 2.6 模型评价、优缺点与工业落地建议

- **MUST**：客观列出模型**优点**（线性性好、可扩展、精确可证）与**缺点**（线性化近似、规模爆炸、随机性未建模）。
- **MUST**：给出**局限性**清单，至少覆盖：固定规模、固定分布、求解时间上界、未建模因素。
- **SHOULD**：提出可操作的**工业落地建议**（分阶段部署、在线重优化、容错冗余）。
- **MUST**：明确区分「本文已解决」与「未来工作」，避免过度承诺。

---

## 三、数字真实性核验规范（原 R2 升维）

> **硬红线。** 本节由 `tools/r2_numeric_check.py` 强制执行，本 SOP 负责向 Writer 解释其背后的**设计意图**。

### 3.1 三类必须绑定 solution 的数字

1. **目标性声明（objective-like）：** 出现「objective / optimal cost / total cost / 最短路 / 目标值 / 最优值」等关键词后紧跟的数字，**必须**出现在 `solution.json` 中。
2. **大整数结果（big numeric）：** 超过阈值的整数/小数（如材料长度、调度时间、覆盖率百分比），若非年份、非路径、非流程计数器，**必须**落在 solution 的 token 集合内。
3. **派生量：** 提升率、相对误差、规模数等，须由 solution 中已有数值**现场推导**，并在文中给出算式。

### 3.2 允许豁免的数字类型（避免误报）

硬门通过**掩码（mask）**机制豁免以下数字，Writer 须知晓以免误以为可随意写：

| 类别 | 例子 | 为何豁免 |
|------|------|----------|
| 年份 | 2026 | 参考文献/时间标注，非结果 |
| arXiv/DOI | `2401.00001`、`10.1234/abc` | 文献标识符 |
| 路径 token | `C:\Users\...`、`runs/20260801/...` | 溯源信息，非结果 |
| 流程计数器 | `claims_recorded: 309`、`duration_ms` | 日志元数据，非结果 |

> **关键：** 豁免是为了**防误报**，不是给编造数字开后门。任何**结果性**数字都不得伪装成上述类别。

### 3.3 Writer 自查动作（写作时）

1. 在写任何数字前，先确认它能在 `solution.json` 中找到对应字段。
2. 派生量在文中标注重算算式，例如 `提升率 = (baseline - proposed) / baseline × 100%`。
3. 不写「约为」「接近」等模糊词来掩盖未重算的数字——要么给精确重算值，要么删掉该句。
4. 提交前运行 `tools/r2_numeric_check.py --draft <draft> --solution <solution>` 自检。

### 3.4 Verifier 评分要点

- **充分：** 所有结果数字可追溯、派生量有算式、有重算确认。
- **勉强：** 数字正确但缺少重算说明或算式。
- **缺失/FATAL：** 出现 solution 之外的数值，或用模糊词掩盖未重算值。

---

## 四、事实主张与证据溯源（原 Claim 机制升维）

> 由 `orpath/claim_ledger.py` 的 Claim Ledger 与 `tools/r1_claim_map.py` 的 claim map 升维而来。

### 4.1 Claim 的三种来源与状态

| 来源 | 说明 | 可溯源证据 |
|------|------|-----------|
| **求解器声明** | 目标值、状态、形状 | `solution.json` |
| **外部主张** | 算法性质、复杂度、文献结论 | 算法库文档、arXiv/DOI、检索 chunk_id |
| **结构主张** | 面积/覆盖/可行性 sanity | `validate.json`、fixture |

每个 Claim 有稳定状态：`unverified` → `verified` → `failed`，合并规则为 **failed > verified > unverified**（一旦被证伪即不可翻转为可信）。

### 4.2 强制可溯源的主张类型

1. **最优性主张：** 「全局最优/证明最优」必须绑定 `solution.meta.proven_optimal == true`；否则必须改写为「可行/搜索轨」。
2. **规模/面积主张：** 如多格骨牌 `piece_count × 4 ≥ cells`（tetromino 最大面积 sanity），违反即结构 FATAL。
3. **检索引用主张：** 当 `knowledge_mode ∈ {seed, hybrid}` 且有检索 id 时，研究/正文须至少引用一个 `chunk_id` 或 `seed_id`，否则视为「检索未被消费」。
4. **URL 主张：** 每个 HTTP(S)/notes:// URL 必须落在白名单内（见第五章）。

### 4.3 写作纪律

- **每段核心论点**开头用 `Claim:` / `Finding:` / `Verified:` 标记，后接可溯源证据（路径或 chunk_id）。
- 不得写「张三（2023）证明……」而无可核验来源——**假染色证明**与**无源引用**同罪。
- 主张应**精确到可判定**：避免「显著提升」「大幅优化」而无量化口径。

### 4.4 证据链闭环的验收

- **闭环（CLOSED）：** 每个核心 Claim 都有 `evidencePaths` + `claimId`，且 `verificationState ∈ {verified, partial}`。
- **断裂（OPEN）：** 存在 `unverified` 且无证据的核心主张 → 须补证或降级措辞。
- **证伪（FAILED）：** 存在 `failed` Claim → 禁止进入 provenance，须回环重写。

---

## 五、文献引用与数据溯源规范（原 R1 升维）

> 由 `tools/r1_cite_check.py`（本地白名单）与 `tools/r1_online_check.py`（在线 arXiv/DOI 验证）升维而来。

### 5.1 三级引用纪律

| 级别 | 来源 | 要求 |
|------|------|------|
| **L1 题目附件** | `fixtures/**/problem.md`、原始附件 | 最高权威；引用时给出相对路径 |
| **L2 算法库文献** | OR-Tools / CP-SAT / HiGHS / NetworkX / PyVRP 文档与论文 | 引用真实存在的库版本/文献 |
| **L3 检索证据** | 知识库命中的 `chunk_id` / `seed_id` | 须在正文或证据表出现对应 id |

### 5.2 URL 白名单机制（R1 本地）

- 正文所有 HTTP(S)/notes:// URL 必须出现在 `whitelist.json` 收集的允许集合内。
- 白名单来源：`fixtures/**`、`knowledge/**`、官方文档域名、`notes://` 本地证据。
- 规范化：忽略末尾 `.` `,` `;` `/` 等标点差异后再比较。

### 5.3 在线标识符验证（R1 在线，可选）

- 若正文引用 arXiv（`arxiv.org/abs/YYYY.NNNNN`）或 DOI（`10.xxxx/...`），须能通过在线 API 验证其**真实存在**。
- Writer 不得凭空构造 DOI/arXiv 号；拿不准时**不写**，改为描述算法思想。

### 5.4 数据溯源要求

- **原始数据**（题目附件、字段值）引用路径，不粘贴大段原始 blob。
- **求解产物**引用 `solution.json` / `validate.json` 的**路径**，而非把整个 JSON 抄进正文。
- **图表**引用生成脚本或导出路径，保证可复现。

### 5.5 禁止清单

- ❌ 伪造/臆造作者-年份引用（如「Smith 2023」无源）。
- ❌ 用假 DOI/arXiv 号伪装权威。
- ❌ 引用与本题无关的文献凑数。
- ❌ 把 `notes://` 内部 id 当作外部文献。

---

## 六、Verifier / Reviewer 智能体自审核对清单（Review Rubric Checklist）

> 供 Verifier/Reviewer 智能体在 `review_pack` 阶段**逐条自评**。每项给出 **PASS / WARN / FAIL** 三档，**任一 FAIL 触发打回**。

| # | 自审项 | 判据 | 档位标准 |
|---|--------|------|----------|
| 1 | **结构完整** | 摘要、问题重述、模型建立、求解策略、结果与敏感性、评价建议六节齐全 | PASS=六节齐全；WARN=缺 SHOULD 内容；FAIL=整节缺失 |
| 2 | **数字真实性（Numbers Truth）** | 所有结果数字 ⊆ `solution.json`，派生量有算式 | PASS=全可溯源；WARN=缺算式；FAIL=出现 solution 外数值 |
| 3 | **独立重算** | `validate_solution.py` 重算目标值/可行性与求解器一致 | PASS=一致；WARN=仅目标一致；FAIL=不一致或未跑 |
| 4 | **最优性诚实声明** | 肯定性最优措辞 ↔ `proven_optimal` 严格匹配 | PASS=匹配；WARN=措辞含糊；FAIL=夸大最优性 |
| 5 | **数学规划模型自洽** | 决策变量/目标/约束完整，符号一致，模型不含最优值 | PASS=完整自洽；WARN=符号/编号小瑕疵；FAIL=约束缺失或含最优值 |
| 6 | **Claim 证据链闭环** | 核心主张均有 `evidencePaths`/`claimId`，无 unverified 核心主张 | PASS=CLOSED；WARN=partial；FAIL=OPEN/FAILED |
| 7 | **引用合规（R1）** | 所有 URL ⊆ 白名单，标识符真实，无无源作者-年份 | PASS=全合规；WARN=格式瑕疵；FAIL=超白名单/伪造 |
| 8 | **敏感性分析真实** | 至少一项参数变动，且目标值来自真实重算 | PASS=真实重算；WARN=仅定性；FAIL=编造曲线/数字 |
| 9 | **求解策略说明** | 算子选型理由、复杂度、收敛性、参数与种子齐备 | PASS=齐备；WARN=缺参数；FAIL=错误声称收敛性 |
| 10 | **局限性与落地建议** | 缺点、局限、工业建议、未来工作区分清晰 | PASS=清晰；WARN=略简；FAIL=过度承诺或缺失 |

### 6.1 打回与升级规则

- **任一 FAIL** → 打回 Writer 重写，`revise_count ≤ 2`；不得修改 `solution.json` 数字，数错回环 A（求解环）。
- **WARN 项 ≥ 3** → 综合评分降级，建议人工复核。
- **全部 PASS** → 允许进入 `provenance`；最终 `verificationState` 由 Claim Ledger 汇总。
- **流程可观测：** 每次打回须在 `outputs/<slug>-review.md` 与时间线标注 `repair_edge`（process-visibility）。

### 6.2 Reviewer 的诚实边界

LLM 评审 ≠ 真实期刊审稿。Verifier 输出应标注为「代理评审」，**不得宣称**已达到顶会/期刊发表水平，不得使用「保证录用」等措辞。

---

## 附：工具与路径速查

| 用途 | 路径 |
|------|------|
| 数字硬门 | `tools/r2_numeric_check.py` |
| 引用硬门（本地） | `tools/r1_cite_check.py` |
| 引用硬门（在线） | `tools/r1_online_check.py` |
| Claim map | `tools/r1_claim_map.py` |
| Claim Ledger | `orpath/claim_ledger.py` |
| 独立校验器 | `tools/validate_solution.py` |
| 论文协议入口 | `orpath/paper_protocol.py` |
| 论文渲染/评审 | `orpath/paper_workflow.py` |
| 论文结构契约 | `templates/paper/or-mcm.md` |
| 论文环规范 | `specs/paper-and-review.md` |

> **提醒：** 本 SOP 为软指引，与上述硬门协同生效。**软指引提升上限，硬门守住底线。**
