# Problem Intake — 题面 OCR 与自主审读（OR-Path **1.1**）

**状态：** LAW（**1.1 CLOSED/PASS**；行为变更须先改本文件）  
**里程碑：** **1.1**（在 1.0 之上；**不重开** T1/T2/T3/1.0 DoD）  
**总流程对齐：** `product-flow-sdd.md` · `control-plane.md` · `contracts.md`  
**过程可视：** intake 站必须出现在 timeline L0（`process-visibility.md`）  
**主题：** 扫描图 / PDF / 已解压附件 → **OCR** → **自主审题 brief** →（可选人确认）→ 再进入 `orchestrate…` 环。

---

## 1. 一句话

**题面 intake 是产品前端竖切：** 工具负责 OCR，结构化审读产出 **无数字** 的 brief + `intake.json`；  
**objective / path / tour / routes 仍只能来自 solve + validate。**

---

## 2. 动机与边界

### 2.1 1.0 缺口

1.0 闭环默认从 **已有 `problem_id` / fixture / 人手 brief** 进入 `orchestrate`。  
竞赛/数模场景里，真实输入常是：

- 题面截图 / 扫描 PDF  
- 附件 zip（csv / xlsx / 模板）  
- 人工 `notes/*-OCR-BRIEF.md`（例：圆管 B 题）

这些 **不应**继续依赖会话里 Hermes 手写 brief 才算「能做题」。

### 2.2 In scope（1.1）

1. **OCR 工具路径：** 本地图/PDF → 原文落盘  
2. **自主审读：** raw → `problem-brief.md` + `intake.json`（子问全覆盖、数据资产、约束文字、歧义）  
3. **禁数字门：** intake 制品不得含 solution 形状键 / 宣称最优  
4. **可选人确认门：** 竞赛默认建议开；CI/fixture 可关  
5. **CLI + LG 可选节点：** 老路径 `skip_intake` 不变绿  
6. **门禁：** `scripts/intake_gate.py` 覆盖契约与负例  
7. **class_hint：** 可软提示；**未注册 class 不得假绿求解**（见 1.2 / solvers 域注册法）  

### 2.3 Out of scope（1.1 明确不做）

| 非目标 | 说明 |
|--------|------|
| 在 intake 内建模/求解/写 solution | 仍归 model / solve |
| 把 MinerU 知识竖切与题面 intake 合成一体 | MinerU = corpus；intake = 题面 |
| 宣称 OCR 100% 正确 | 要可审计 + 歧义外显 |
| 本地下载多 GB OCR 模型作默认 | 云/MCP/已有运行时优先 |
| OpenPi 完整 GUI 导入面板 | 已删除；menu/intake CLI |
| 重开 T1/T2/T3/1.0 门禁 DoD | 回归保持绿即可 |
| Compose/K8s/codegen sandbox | 仍 OUT |
| 自制 SOTA 评测集叙事 | 禁止 |
| 未注册域 intake 后绑 SP 金标 | **禁止**（1.2） |

---

## 3. 阶段图（相对 control-plane 的增量）

```text
START
  → [optional] intake_ocr      # 工具：图/PDF → ocr.raw + meta
  → [optional] intake_parse    # 审读：raw(+附件清单) → brief + intake.json
  → [optional] human_confirm_intake
        ├─ reject / 未确认 → HUMAN_REQUIRED 或停在 intake（实现可选）
        └─ ok / skip → orchestrate
  → orchestrate → retrieve → …（产品图其余）
```

| 模式 | 行为 |
|------|------|
| **Legacy / CI** | `skip_intake=1` 或未提供 `source_paths` → 直接 `orchestrate`（默认兼容） |
| **Intake on** | 提供题面源 → 必须产出 brief + intake.json 且过 `gate_intake` 才可进 orchestrate |
| **竞赛谨慎** | `human_confirm_intake=1`（默认建议 **on** 当且仅当 intake on） |
| **M0 Demo** | 可用 fixture 文本 stub，不必强依赖扫描图 |

**禁止：** intake 节点调用 solve；intake 写 `objective`；用 memory 补最优值。

字段 owner 增量见 §7；总表仍以 `control-plane.md` 为准，本文件冲突时 **intake 字段以本文件为准**。

---

## 4. OCR 层（工具，非 Agent）

### 4.1 后端优先级（实现必须按序尝试）

| 优先级 | 后端 id | 何时用 |
|--------|---------|--------|
| 1 | `pdf_text` / `manual_stub` | PDF 文字层非空；或 `.md`/`.txt` 测试原文 |
| 2 | `ppocr` / `paddleocr`（`ORPATH_PADDLEOCR_PYTHON`） | 图片/扫描；本机 paddle |
| 3 | `paddleocr_mcp` / api token | 本地 paddle 失败且有 token |
| 4 | **`rapidocr`** | 最终本地回退；**诚实写 backend=rapidocr** |
| — | placeholder | **禁止**当成功 |

**禁止默认：**

- 把 **MinerU Cloud** 当竞赛题面主 OCR（可日后「可选增强」，不得替代 §4.1 主序）  
- 为 1.1 强制用户本机装巨型本地 OCR 权重  
- backend 撒谎

### 4.2 输入

- 一或多文件：`.png` `.jpg` `.jpeg` `.webp` `.tif` `.tiff` `.pdf` `.md` `.txt`  
- 可选：已解压附件根目录（只登记路径，不在 OCR 步解析数值最优）  
- CLI 示例形态：

```bat
orpath.bat intake --slug demo-b --in path\to\problem.png --in path\to\more.pdf --assets path\to\unzipped
```

（bat 子命令可在实现时接入；最小验收允许直接 `python tools/intake_ocr.py`。）

### 4.3 输出（OCR）

| 制品 | 路径（约定） | 说明 |
|------|----------------|------|
| 原文 | `notes/<slug>-ocr.raw.md` | 页/文件分隔；尽量保序 |
| 元数据 | `notes/<slug>-ocr.meta.json` | 见 §6.1 |

OCR **不得**改写为「解题摘要」；摘要属于 parse。

---

## 5. 自主审读（parse）

### 5.1 目标

从 OCR 原文 + 可选附件目录列出信息，生成：

1. **人类可读** `notes/<slug>-problem-brief.md`  
2. **机器可读** `outputs/<slug>-intake.json`  

### 5.2 Brief 必选章节（标题可中英，语义必须有）

```markdown
# Problem brief — <slug>

## Sources
## Full problem statement (normalized)
## Subproblems (Q1…Qn)     # 全覆盖；禁止只列最简单一问
## Data assets               # 路径、表、单位、模板
## Objectives (qualitative)  # 主/次/再次 — 文字 only
## Constraints (qualitative)
## Deliverables              # xlsx/json/报告等
## Ambiguities / OCR gaps    # 看不清、冲突、缺页 — 禁止默填
## Non-goals for intake
```

**硬纪律：**

1. **全题覆盖：** `subproblems` 必须反映题面全部子问；若 OCR 缺页，在 Ambiguities 声明，不得假装完整。  
2. **禁止解答数字：** 不得出现声称最优的 objective、路径长度、利用率终值、共切收益终值等。  
3. **单位与模板：** mm/m、result 模板路径等必须写清（若原文有）。  
4. **软提示可有：** 候选 `problem_class_hint`、约束类型关键词 — **不是** modeler schema，**不可**当作已建模。  
5. **Hermes/会话辅助**若仍用于紧急 OCR，产出必须落成 **同构 brief**，不得只留在 chat。

### 5.3 谁执行 parse

| 档 | 做法 | 1.1 |
|----|------|-----|
| A | 确定性模板 + 规则/轻量 LLM 填充章节 | **允许（默认优先可测）** |
| B | 短 Pi lead / `or-orchestrator` 只写 brief+json | 允许 |
| C | 派 `or-modeler` / 调 solve | **禁止** |

Live 多 Agent **不是** intake 硬 DoD。

### 5.4 人确认门（可选）

当 `human_confirm_intake=1`：

1. 写出 brief + intake.json 后 **停止**自动进入 research/model  
2. 等待显式确认（CLI flag、状态字段 `intake_confirmed=true`、或计划账本勾选）  
3. 确认前 **禁止** solve  

CI：`human_confirm_intake=0` 且可用 fixture 原文，避免人工阻塞门禁。

---

## 6. 数据契约

### 6.1 `notes/<slug>-ocr.meta.json`

```json
{
  "slug": "demo-b",
  "backend": "pdf_text | paddleocr_mcp | paddleocr | manual_stub",
  "sources": [
    {
      "path": "fixtures/.../page1.png",
      "sha256": "optional-but-recommended",
      "kind": "image | pdf | text",
      "pages": 1
    }
  ],
  "created_at": "ISO-8601",
  "warnings": [],
  "raw_path": "notes/<slug>-ocr.raw.md"
}
```

### 6.2 `outputs/<slug>-intake.json`（权威机器契约）

**必填逻辑字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `slug` | string | |
| `schema_version` | string | 1.1 初始 `"1.1.0"` |
| `status` | string | `ok` \| `needs_human` \| `error` |
| `sources` | array | 与 OCR 源对齐（path 必填） |
| `subproblems` | array | 至少 1；元素见下 |
| `data_assets` | array | 可为 []；有附件时应非空 |
| `constraints_text` | string | 自然语言约束摘要 |
| `objectives_text` | string | 定性目标层级 |
| `deliverables` | string[] | 交付物列表 |
| `ambiguities` | string[] | 可空数组；`needs_human` 时建议非空 |
| `brief_path` | string | `notes/<slug>-problem-brief.md` |
| `ocr_raw_path` | string | |
| `ocr_meta_path` | string | |
| `ocr_backend` | string | |
| `problem_class_hint` | string \| null | 软提示，可 null |
| `problem_id_hint` | string \| null | 软提示，可 null |

**`subproblems[]` 元素：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 如 `Q1` |
| `title` | string | |
| `must_deliver` | string[] | 该问必须交付 |
| `data_refs` | string[] | 相关资产 path 或逻辑名 |
| `notes` | string | 可选 |

**`data_assets[]` 元素：**

| 字段 | 类型 |
|------|------|
| `path` | string |
| `kind` | `csv` \| `xlsx` \| `stp` \| `pdf` \| `image` \| `other` |
| `role` | 如 `demand_table` \| `geometry` \| `result_template` \| `unknown` |
| `notes` | string 可选 |

### 6.3 禁止键（intake.json 与 brief 正文）

对 `intake.json`：**递归扫 key**（大小写不敏感），命中则 `gate_intake` **失败**：

```text
objective, optimal, objective_value, optima, optimal_value, optimal_cost,
proven_optimal, best_cost, best_objective,
tour, routes
path   # 解答形状；但 sources[] / data_assets[] 元素上的文件 path 字段允许
```

实现：`tools/gate_intake.py` 的 `walk_forbidden_intake_keys` — `path` **仅**在
`sources` / `data_assets` 数组元素内放行；顶层或其它嵌套 `path`（答案节点序列）仍红。

说明：

- brief 里允许出现题面 **参数**（如「母材 9m」「n=8」）——那是题面数据，不是 solver 最优解。  
- brief / json **禁止**出现「最优总长 = 12345」这类 **解答断言**。  
- 实现门禁：json 禁键硬拦；brief 用启发式禁答（如 `objective\s*=`、`最优[解值为]` + 数字）允许有限误报，但 **金负例必须拦**。

### 6.4 与 ProblemSchema 的关系

- intake **不是** modeler schema。  
- `problem_class_hint` 仅供 research/model 参考。  
- modeler 仍只写 `outputs/<slug>-schema.json`，且遵守 `contracts.md` 禁键。

---

## 7. 状态字段 owner（增量）

| 字段 / 制品 | 唯一写者 |
|-------------|----------|
| `notes/<slug>-ocr.raw.md` | `intake_ocr` 工具 |
| `notes/<slug>-ocr.meta.json` | `intake_ocr` 工具 |
| `notes/<slug>-problem-brief.md` | `intake_parse` |
| `outputs/<slug>-intake.json` | `intake_parse` |
| `intake_ok` / `gate_intake_ok` | intake gate 代码 |
| `intake_confirmed` | 人 或 CLI 显式确认 |
| `skip_intake` | runner / 初始 seed |

**禁止：** research/model/solve 节点改写 intake 禁键门结果来「消红」。

---

## 8. 实现落点（路径白名单指引）

| 路径 | 职责 |
|------|------|
| `tools/intake_ocr.py` | OCR CLI/库入口 |
| `tools/intake_parse.py` | 审读 → brief + intake.json |
| `tools/gate_intake.py` | 契约 + 禁键 + 最小结构 |
| `tools/schema_models.py` | 可选：Intake* pydantic |
| `contracts/intake.json` | 可选：JSON Schema 导出 |
| `scripts/intake_gate.py` | 1.1 门禁（单元+fixture+负例） |
| `orpath/nodes.py` | 可选节点 `intake_ocr` / `intake_parse` |
| `orpath/graph_product.py` + `stage_map.json` | 仅当挂 LG 时更新 |
| `orpath/control_plane.py` / `run_orpath.py` | seed 字段、CLI |
| `orpath.bat` | 可选 `intake` 子命令 |
| `fixtures/t1_intake/` 或 `fixtures/intake/` | 文本 stub + 负例 json（**小**；勿塞大 PDF 进 git） |
| `docs/1.1-smoke.md` | 操作说明（closeout 时） |

**不写：** `pi-main/`、`openpi/` 深改、`vendor/`、`inquisitive*`。

---

## 9. 门禁与 DoD（1.1）

### 9.1 命令（目标）

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONNOUSERSITE=1
.venv-314\Scripts\python.exe scripts\intake_gate.py
```

回归（不得因 1.1 变红）：

```bat
.venv-314\Scripts\python.exe scripts\t1_gate.py
.venv-314\Scripts\python.exe scripts\t3_lg_gate.py
```

（`t2_gate` / paper / subagent 门禁按改动触及面跑；未改动的可不阻塞 1.1 日常，但 release 宣称前应绿。）

### 9.2 `intake_gate` 必检

实现入口：`scripts/intake_gate.py`（S4 起打印 DoD 勾选；`INTAKE_GATE_FAST=1` 可跳过 t1/t3 回归）。

- [x] `manual_stub`：纯文本题面 → raw + meta  
- [x] parse：→ brief 必备章节语义 + `intake.json` schema_version  
- [x] `subproblems` 长度 ≥ 题面声明的子问数（fixture 金标）  
- [x] 禁键：含 `objective` 的 intake.json → **失败**  
- [x] brief 金负例：夹带「最优解 objective=42」类 → **失败**  
- [x] `status=needs_human` 当 ambiguities 非空（fixture 约定时）  
- [x] legacy：`skip_intake` 路径不要求 intake 文件（`intake_s4_checks.legacy_skip_intake_ok` + t1 无 intake 依赖）  
- [x] 结构 smoke：多子问 Q1…Q4（`fixtures/intake/structure_q4`）  

### 9.3 1.1 CLOSED 硬清单

- [x] 本 spec 已合入且与实现一致  
- [x] `scripts/intake_gate.py` PASS  
- [x] t1_gate + t3_lg_gate 仍 PASS（默认 skip_intake；S5 验收）  
- [x] 至少一条 **真实赛题** smoke：圆管 B2026 OCR brief → intake（`docs/archive/closeouts/1.1-closeout.md` + `docs/archive/evidence/1.1-tube-cut-intake-smoke.json`）  
- [x] 结构回归：圆管 Q1–Q4 + `structure_q4` fixture  
- [x] claim ladder 诚实：不宣称 OCR 完美、不宣称 intake 替代求解  
- [x] `docs/archive/closeouts/1.1-closeout.md` PASS  
- [x] 无密钥进 git；大 PDF/扫描件不进 git（题面用 md stub 固化）  

### 9.4 非门禁（1.1）

- OpenPi 拖拽导入 UI  
- Live Pi 多 Agent 做 parse  
- MinerU 题面增强  
- 全自动无确认直接求解竞赛全卷  

---

## 10. Claim ladder（话术）

**可以说：**

- 支持题面图/PDF OCR + 结构化审题 brief  
- 子问清单与交付物可审计；歧义外显  
- intake 与求解分离；数字仍来自 solve+validate  

**不可以说：**

- OCR/审题保证无错  
- 自动审题后即得全局最优  
- 已替代数模专家读题  
- MinerU 与题面 OCR 已统一为同一生产引擎（若仅 stub/分轨）  

---

## 11. 与相邻法条

| Spec | 关系 |
|------|------|
| `control-plane.md` | 阶段插入点；本文件定义 intake 增量 |
| `contracts.md` | Solution/Schema 禁键精神延伸至 intake |
| `knowledge-and-retrieval.md` | MinerU/corpus ≠ 本 intake |
| `multi-agent.md` | parse 可用 lead；禁止假求解 |
| `gates-and-dod.md` | 挂 1.1 门禁入口 |
| `product-scope.md` | 里程碑 1.1 |
| `docs/archive/closeouts/1.0-closeout.md` | 前置 PASS；1.1 不重开 |

---

## 12. 实现顺序（建议切片，非法外加需求）

1. **S0** 本 spec + README/索引回写（本变更）  
2. **S1** `gate_intake` 契约 + 禁键单测（可先红）  
3. **S2** `intake_ocr`：`manual_stub` + `pdf_text`；Paddle 适配  
4. **S3** `intake_parse`：brief 模板 + intake.json  
5. **S4** `scripts/intake_gate.py` 绿  
6. **S5**（可选）LG 节点 + `stage_map` + bat  
7. **S6** 真实题面 smoke + closeout  

**默认开工从 S1 起；S5 不挡 1.1 最小 PASS（最小 PASS = S4 + 回归门禁 + 一条真实 smoke）。**

---

## 13. Freeze 摘要（2026-07-30）

| ID | 锁 |
|----|-----|
| F1 | 1.1 = OCR + 自主审读；不重开 1.0 DoD |
| F2 | OCR 主序：pdf_text → paddle → manual_stub；MinerU 非主 |
| F3 | 制品：ocr.raw + ocr.meta + problem-brief + intake.json |
| F4 | intake 禁 solution 键；数字只认 solve+validate |
| F5 | 子问全覆盖；歧义外显 |
| F6 | 竞赛建议 human_confirm；CI 可 skip |
| F7 | 最小 DoD 不强制 LG 挂载 / OpenPi UI |
| F8 | 实现通道：Hermes 按 specs 直接实现 |
