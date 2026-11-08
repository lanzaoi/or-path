#!/usr/bin/env python3
"""OR-Path four permanent elite specialist factories built on
``langgraph.prebuilt.create_react_agent``.

The lean 4-agent architecture composes the OR research pipeline with four
permanent LLM specialists, each operating in an isolated fresh message list
and a narrow tool surface so the control plane can route work without granting
every agent every capability:

  * ``create_analyst_agent``    — ``or_analyst``: intensive problem-statement
    reading, preflight data profile consumption, mathematical class
    confirmation, modeling advice and complexity tiering (Tier-A/B/C). Never
    writes solver code and never guesses solutions.
  * ``create_modeler_agent``    — ``or_modeler`` (mathematical programming /
    algorithm expert: schema.json construction, mature-solver dispatch or
    controlled sandbox scripts, relaxation lower-bound & gap analysis). Only
    transports solver output; never hand-writes solution JSON values.
  * ``create_writer_agent``     — ``or_writer`` (academic report author):
    writes the rigorous 6-chapter paper (``docs/or-paper-sop.md``) strictly
    around Python-prerendered verified truth tables and figures.
  * ``create_reviewer_agent``   — ``or_reviewer`` (adversarial peer reviewer):
    10-point audit rubric with graded defects (FATAL/MAJOR/MINOR).

Each factory accepts dynamic per-call injections for pluggable domain
capability: ``cartridge_tools`` mounts the DomainCartridge-bound domain tools
(``profile_<domain>_data`` / ``inspect_<domain>_solution`` / …) and
``domain_directive`` appends a domain-specific modeling prompt fragment. Domain
capability is injected by mounting real tools, never by cloning agent graphs.

Numbers Truth: objective values and physical metrics come strictly from the
solvers + independent validators; no agent may state an optimum the
validators cannot reproduce.

The module is import-safe offline: agents are constructed against
``orpath.control_plane.get_chat_model()`` which falls back to a placeholder
key, so unit tests can build (not invoke) the graphs without network access.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import create_react_agent

from orpath.control_plane import get_chat_model
from orpath.agents.tools_or import (
    consult_or_skill,
    execute_or_solver,
    execute_python_sandbox,
    get_problem_formulation_template,
    list_available_solvers,
    validate_solution_tool,
)

__all__ = [
    "READ_PROBLEM_FILE_MAX_CHARS",
    "ANALYST_NAME",
    "MODELER_NAME",
    "WRITER_NAME",
    "REVIEWER_NAME",
    "VERIFIER_NAME",
    "WORKER_AGENT_NAMES",
    "ACADEMIC_WORKER_NAMES",
    "create_analyst_agent",
    "create_modeler_agent",
    "create_verifier_agent",
    "create_writer_agent",
    "create_reviewer_agent",
    "get_default_workers",
    "get_academic_workers",
    "append_domain_directive",
    "read_problem_file",
    "export_paper_markdown",
    "search_or_knowledge",
]


def _resolve_root() -> Path:
    """Resolve active case workdir (honouring ORPATH_WORKDIR) or fall back to cwd."""
    raw = (os.environ.get("ORPATH_WORKDIR") or "").strip().strip('"')
    if raw:
        try:
            from orpath.paths import orpath_home

            raw_path = Path(raw).expanduser().resolve()
            home_path = orpath_home().resolve()
            cwd_path = Path.cwd().resolve()
            # If ORPATH_WORKDIR was polluted with home but cwd is an isolated test/case dir, prefer cwd.
            if raw_path == home_path and cwd_path != home_path:
                return cwd_path
            return raw_path
        except Exception:
            return Path(raw).expanduser().resolve()
    return Path.cwd()

#: Default character budget for ``read_problem_file``.
READ_PROBLEM_FILE_MAX_CHARS = 8000

#: Canonical agent names (stable identifiers for a supervisor / routing layer).
ANALYST_NAME = "or_analyst"
MODELER_NAME = "or_modeler"
WRITER_NAME = "or_writer"
REVIEWER_NAME = "or_reviewer"
#: Retained for the legacy academic flow; the standalone LLM verifier role is
#: being replaced by deterministic validation gates.
VERIFIER_NAME = "or_verifier"
WORKER_AGENT_NAMES = (ANALYST_NAME, MODELER_NAME, WRITER_NAME, REVIEWER_NAME)
ACADEMIC_WORKER_NAMES = (
    ANALYST_NAME,
    MODELER_NAME,
    VERIFIER_NAME,
    WRITER_NAME,
    REVIEWER_NAME,
)


def make_compact_handoff(
    role_note: str,
    pointers: dict[str, str],
    summary: str,
) -> str:
    """Build a Feynman compact handoff packet for worker-to-worker dispatch.

    Enforces zero-truncation of stored files while stopping the O(N^2) chat
    token explosion across multi-agent handoffs.
    """
    lines = [
        "【Fast-Path Handoff Pointer Packet】",
        f"Target Role: {role_note}",
        "Verified Artifact Pointers (load on demand from disk):",
    ]
    for k, v in sorted((pointers or {}).items()):
        if v:
            lines.append(f"  - {k}: {v}")
    lines.append("Executive State Summary:")
    lines.append(str(summary or "").strip()[:800])
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Small file-facing tools shared by the workers
# --------------------------------------------------------------------------- #
@tool
def read_problem_file(file_path: str, max_chars: int = READ_PROBLEM_FILE_MAX_CHARS) -> str:
    """Read a problem statement / fixture file as text, with a hard size limit.

    Used by every worker to ground its reasoning in the raw problem data rather
    than a paraphrase. The file is resolved against the current working directory
    (absolute paths are honoured). Binary / undecodable bytes are replaced so the
    call never raises; oversized files are truncated with an explicit marker.

    Args:
        file_path: Path to the problem document or fixture (``.txt``, ``.md``,
            ``.json``, ``.py``, ...). Relative paths resolve against ``cwd``.
        max_chars: Maximum number of characters returned. Must be > 0.

    Returns:
        A text block of the form:

            file_path=<abs path>
            size=<bytes> returned=<chars> truncated=<bool> max_chars=<int>
            ---
            <file contents>

        On failure a ``file_path=... error=...`` block is returned instead.
    """
    try:
        limit = int(max_chars)
    except (TypeError, ValueError):
        limit = READ_PROBLEM_FILE_MAX_CHARS
    if limit <= 0:
        limit = READ_PROBLEM_FILE_MAX_CHARS

    root = _resolve_root()
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = root / path

    # Self-healing path resolution: check plausible candidate locations if not found
    if not path.is_file():
        candidates = [
            root / file_path,
            root / "inbox" / Path(file_path).name,
            root / "fixtures" / file_path,
            root / "fixtures" / "t3" / file_path,
            root / "outputs" / Path(file_path).name,
            root / "papers" / Path(file_path).name,
            root / "notes" / Path(file_path).name,
            Path.cwd() / file_path,
        ]
        found = next((c for c in candidates if c.is_file()), None)
        if found is not None:
            path = found

    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        # Provide nearby hint if available
        nearby = []
        try:
            target_name = Path(file_path).name.lower()
            for p in (root / "fixtures").rglob("*"):
                if p.is_file() and target_name in p.name.lower():
                    nearby.append(str(p.relative_to(root)))
                    if len(nearby) >= 3:
                        break
        except Exception:
            pass
        hint_str = f" candidate_suggestions={nearby}" if nearby else ""
        return f"file_path={path}\nerror=file_not_found{hint_str}"
    except IsADirectoryError:
        return f"file_path={path}\nerror=is_a_directory"
    except PermissionError:
        return f"file_path={path}\nerror=permission_denied"
    except OSError as exc:  # noqa: BLE001 - tools must never raise
        return f"file_path={path}\nerror={type(exc).__name__}: {exc}"

    text = raw.decode("utf-8", errors="replace")
    truncated = len(text) > limit
    body = text[:limit]
    lines = [
        f"file_path={path}",
        f"size={len(raw)} returned={len(body)} truncated={str(truncated).lower()} max_chars={limit}",
        "---",
        body,
    ]
    return "\n".join(lines)


@tool
def export_paper_markdown(output_path: str, content: str) -> str:
    """Write an academic report (Markdown) to disk.

    The final writer worker calls this once the paper text is assembled, so the
    deliverable is persisted as a real artifact (``papers/``, ``outputs/``) rather
    than trapped inside the agent transcript.

    Args:
        output_path: Target file path. Parent directories are created as needed.
            Relative paths resolve against ``cwd``.
        content: Full Markdown document to persist.

    Returns:
        JSON string: ``{"success": bool, "output_path": str, "bytes": int,
        "lines": int, "detail": str}``. Never raises for I/O problems; failures
        are reported through ``success``/``detail``.
    """
    try:
        path = Path(output_path).expanduser()
        if not path.is_absolute():
            path = _resolve_root() / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - tools must never raise
        return json.dumps(
            {"success": False, "output_path": str(output_path), "bytes": 0, "lines": 0,
             "detail": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )

    data = content or ""
    return json.dumps(
        {
            "success": True,
            "output_path": str(path),
            "bytes": path.stat().st_size,
            "lines": len(data.splitlines()),
            "detail": "",
        },
        ensure_ascii=False,
    )


@tool
def search_or_knowledge(query: str, topk: int = 5) -> str:
    """Search the OR-Path local knowledge base (RAG) for algorithms, theorems, and modeling patterns.

    Args:
        query: Keywords or conceptual question (e.g. 'JSSP Taillard benchmark', 'cutting stock column generation').
        topk: Maximum number of retrieved hits (1-20).

    Returns:
        JSON string containing query, mode, hits (snippet, source_path, score), and seed_facts.
    """
    try:
        from knowledge_svc.retrieve import retrieve

        k = max(1, min(int(topk), 20))
        artifact = retrieve(query=query, topk=k, root=_resolve_root())
        return json.dumps(artifact.to_dict(), ensure_ascii=False)
    except Exception as exc:
        return json.dumps(
            {"query": query, "hits": [], "seed_facts": [], "error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )


# --------------------------------------------------------------------------- #
# Tool assembly helpers
# --------------------------------------------------------------------------- #
def _merge_tools(base: list[BaseTool], *extras: Any) -> list[BaseTool]:
    """Return ``base + extras`` de-duplicated by tool name, preserving order.

    Each extra in ``extras`` may be ``None``, a single ``BaseTool``, or a sequence
    of tools. Unknown / non-tool entries are skipped silently so a supervisor can pass a
    best-effort list without breaking agent construction.
    """
    merged: list[BaseTool] = list(base)
    seen = {t.name for t in merged}

    for extra in extras:
        if extra is None:
            continue
        candidates = extra if isinstance(extra, (list, tuple, set)) else [extra]
        for item in candidates:
            if isinstance(item, BaseTool) and item.name not in seen:
                seen.add(item.name)
                merged.append(item)
    return merged


def _resolve_model(model: Any = None) -> Any:
    """Return the supplied model or the shared OR-Path chat model factory output."""
    return model if model is not None else get_chat_model()


def append_domain_directive(prompt: str, domain_directive: str = "") -> str:
    """Append a ``DomainCartridge``-supplied domain directive fragment to a prompt.

    The directive carries domain-specific modeling conventions (e.g. JSSP 换模时延,
    microgrid SOC/power-balance conventions, cutting-stock residual ledgers)
    injected by the routing layer at construction time. An empty directive is a
    no-op so factory calls without cartridge context stay byte-identical.
    """
    directive = (domain_directive or "").strip()
    if not directive:
        return prompt
    return prompt.rstrip() + "\n\n【领域专业建模指令 (Domain Expertise Directive)】\n" + directive.strip() + "\n"


# --------------------------------------------------------------------------- #
# Worker agent factories
# --------------------------------------------------------------------------- #
def create_analyst_agent(
    model: Any = None,
    cartridge_tools: Any = None,
    domain_directive: str = "",
) -> Any:
    """Create the ``or_analyst`` agent (problem-statement / data-profile analyst).

    Args:
        model: Chat model instance. Defaults to ``get_chat_model()``.
        cartridge_tools: Optional ``DomainCartridge``-bound tools (e.g.
            ``profile_<domain>_data``) mounted onto this analyst at call time.
        domain_directive: Optional domain-specific modeling prompt fragment
            appended to the system prompt.

    Returns:
        Compiled ``create_react_agent`` graph named ``or_analyst``.
    """
    tools = _merge_tools(
        [read_problem_file, search_or_knowledge, consult_or_skill, get_problem_formulation_template],
        cartridge_tools,
    )
    prompt = (
        "你是 OR-Path 流水线中的【运筹学问题分析专家】(Analyst)。\n\n"
        "【工具优先 (Tool-First) 指令】\n"
        "在输出任何分析结论前，必须首先调用 read_problem_file 工具读取原始题面与数据文件"
        "（若任务简报提供了 profile_path / 前置数据画像文件，必须一并读取），"
        "必要时调用 search_or_knowledge / consult_or_skill 检索知识库与建模范式，"
        "绝不允许在未调用工具读取原始文件的情况下凭空臆测题意或数据规模。\n\n"
        "核心职责：\n"
        "1. 题面精读：用 read_problem_file 读取原始题面/数据文件，逐条拆解真实需求，绝不臆测；\n"
        "2. 数据画像：读取确定性前置探针产出的数据画像文件（outputs/<slug>-profile.json），"
        "确认行列规模、字段语义与规模量级；\n"
        "3. 数学分类确认：明确问题的数学类别（LP/MILP/QP/CP-SAT/最短路/网络流/匹配/"
        "TSP/CVRP/VRPTW/JSSP/RCPSP/CFLP/排班/装箱/切割/库存/随机规划/凸优化等）并给出依据；\n"
        "4. 复杂度分档：给出 Tier-A（精确易解：LP/凸QP/最短路/最大流/DP）、"
        "Tier-B（组合难解：VRPTW/JSSP/RCPSP/排班/装箱/选址等）、"
        "Tier-C（多问递进大型赛题）的分档建议；\n"
        "5. 建模建议：输出交由 Modeler 承接的建模建议清单（决策变量、约束骨架、"
        "数据接口、已注册求解器线索）。\n\n"
        "【防角色越界与字数收敛 (Anti-Overstepping)】\n"
        "- 严禁编写任何求解代码、求解器脚本或 schema.json（这是 Modeler 的专职）；\n"
        "- 严禁猜解或试填任何目标值/最优值（Numbers Truth 铁律）；\n"
        "- 严禁撰写学术论文草稿（这是 Writer 的专职）；\n"
        "- 输出必须结构化且极度精炼（严格控制在 500 字以内），包含：① 问题对象与决策目标、"
        "② 数据画像与规模量级、③ 数学分类确认、④ Tier 复杂度分档建议、⑤ 建模建议与歧义/风险提示。\n\n"
        "硬性纪律：\n"
        "- 不输出任何未经原始数据支持的结论，不虚构最优值；\n"
        "- 若题意模糊，明确列出需要澄清的歧义点，而不是自行假设；\n"
        "- 严控篇幅在 500 字以内，输出结构化、可被 Modeler 直接消费的紧凑中文研判。"
    )
    return create_react_agent(
        _resolve_model(model), tools, prompt=append_domain_directive(prompt, domain_directive), name=ANALYST_NAME
    )


def create_modeler_agent(
    model: Any = None,
    cartridge_tools: Any = None,
    domain_directive: str = "",
    extra_tools: Any = None,
) -> Any:
    """Create the ``or_modeler`` agent (mathematical-programming / algorithm expert).

    Args:
        model: Chat model instance. Defaults to ``get_chat_model()``.
        cartridge_tools: Optional ``DomainCartridge``-bound tools (e.g.
            ``inspect_<domain>_solution`` or domain solver helpers) mounted onto
            this modeler at call time.
        domain_directive: Optional domain-specific modeling prompt fragment
            appended to the system prompt.

    Returns:
        Compiled ``create_react_agent`` graph named ``or_modeler``.
    """
    tools = _merge_tools(
        [list_available_solvers, execute_or_solver, execute_python_sandbox, read_problem_file],
        [cartridge_tools, extra_tools],
    )
    prompt = (
        "你是 OR-Path 流水线中的【数学规划与算法实现专家】(Modeler)。\n\n"
        "核心专职：排他性聚焦于 schema.json 建模与算法求解工件生成。\n"
        "1. 显式建模工件：承接 Analyst 的研判结论，首先产出可被求解器消费的 schema.json 模型文档"
        "（决策变量与定义域、目标函数、逐条编号约束集合 C1/C2...），"
        "严禁在模型文档或对话中提前填入最优值；\n"
        "2. 探明算子：必须先用 list_available_solvers 探明系统内已注册的成熟算子，"
        "优先复用成熟求解器；\n"
        "3. 算子派发：匹配上已注册 mode 时，直接用 execute_or_solver 求解，"
        "准确传入 problem_id / mode / extra_args；\n"
        "4. 沙箱建模：当系统内没有成熟算子时，用 execute_python_sandbox 在受控沙箱中"
        "构建并求解模型（如 OR-Tools CP-SAT / HiGHS / NetworkX），把建模逻辑与求解跑通；\n"
        "5. 下界与 Gap 分析：分析松弛下界（LP relaxation / bound）与最优性 Gap；"
        "若求解器标记 proven_optimal=False，如实报告 gap 或可行解性质，严禁声称全局最优；\n"
        "6. 产出有效解工件：必须产出可被独立校验的真实解（包括 solution_path 解文件路径、"
        "目标值、关键决策量），交由确定性校验门与 Writer 核验。\n\n"
        "【防角色越界 (Anti-Overstepping)】\n"
        "- 严禁重复开展文献综述、题面背景研判或复杂度分档（由 Analyst 专职负责）；\n"
        "- 严禁撰写整篇学术论文正文或终结任务报告（由 Writer 专职负责）；\n"
        "- 严禁手写解 JSON 数值或口算填数：所有数值必须来自求解器真实输出。\n\n"
        "硬性纪律：\n"
        "- 目标函数值与约束必须来自真实求解输出，严禁编造最优解或凭空填数；\n"
        "- 求解失败时如实报告 detail，并给出可执行的降级策略（缩小规模、换算法族、"
        "放宽间隙），而不是伪造成功；\n"
        "- 若需长时间求解，主动设置 timeout/gap 等超时参数；\n"
        "- 输出结构化、紧凑的建模求解报告，标明 schema/solution_path 与目标值、下界与 Gap，供下游直接消费。"
    )
    return create_react_agent(
        _resolve_model(model), tools, prompt=append_domain_directive(prompt, domain_directive), name=MODELER_NAME
    )


def create_verifier_agent(model: Any = None, extra_tools: Any = None) -> Any:
    """Create the dedicated ``or_verifier`` agent (independent physical/mathematical auditor).

    Focuses strictly on numeric truth and constraint verification:
    1. Independent Recomputation: invokes ``validate_solution_tool`` to recompute
       all objectives and balance constraints directly from problem data;
    2. Optimality Honesty: checks whether the solver marked ``proven_optimal``;
       forbids marketing prose claiming global optimality without proof;
    3. Constraint & Bound Auditing: checks SOC bounds, power balances, material
       chains, no-overlap constraints, producing a structured verification report.
    """
    tools = _merge_tools([validate_solution_tool, read_problem_file], extra_tools)
    prompt = (
        "你是 OR-Path 流水线中的【物理/数学真实性独立验算与打假专家】(Verifier)。\n\n"
        "【核心定位与专职】\n"
        "你的唯一职责是对 Modeler 产出的解工件进行无情的独立重算与数学证伪，"
        "绝不撰写大段论文，绝不修改求解器数字，遵循 Numbers Truth 铁律。\n\n"
        "核心职责：\n"
        "1. 独立重算优先：必须首先调用 validate_solution_tool 对 solution_path 进行独立重算，"
        "逐条核对目标函数值与各项物理/经济约束（功率平衡、SOC容量、容量限制、互斥条件等）；\n"
        "2. 证伪优于相信：主动寻找解中的矛盾、违约、不可行与目标值不实之处；若求解器未通过校验，"
        "立即判定 ok: false 并列出具体的违规约束与数值偏差；\n"
        "3. 最优性诚实度审核：核实 solution 是否包含明确的 proven_optimal 凭证；若属于启发式搜索、"
        "局部极值或未证明最优，明确标注『可行解/搜索轨，未证明全局最优』，严禁使用虚假夸大营销词；\n"
        "4. 输出校验报告：输出紧凑的核验结论，包含：① 独立校验状态 (ok: true/false)、"
        "② 目标值重算一致性证明、③ 约束满足清单、④ 供 Writer 消费的数值权威表。\n\n"
        "硬性纪律：\n"
        "- 严禁编造任何数字，所有数字以 validate_solution_tool 独立重算结果为准；\n"
        "- 严禁代写学术论文（成文是 Writer 的职责）；\n"
        "- 严禁擅自修改解文件；若校验失败，退回并要求 Modeler 重新求解。"
    )
    return create_react_agent(_resolve_model(model), tools, prompt=prompt, name=VERIFIER_NAME)


def create_writer_agent(
    model: Any = None,
    extra_tools: list[Any] | None = None,
    cartridge_tools: list[Any] | None = None,
    domain_directive: str = "",
) -> Any:
    """Create the dedicated ``or_writer`` agent (academic scientific report author).

    Transforms validated solution evidence into publication-grade OR papers
    adhering strictly to ``docs/or-paper-sop.md``:
    1. Standard 6-Section Rubric (Abstract, Problem & Assumptions, Formulation,
       Algorithm & Complexity, Computational Results & Sensitivity, Limitations & Deployment);
    2. Numbers Truth: all result numbers ⊆ solution.json;
    3. LaTeX Math & Structured Tables;
    4. Persists the deliverable to disk via ``export_paper_markdown``.

    Args:
        model: Chat model instance. Defaults to ``get_chat_model()``.
        extra_tools: Optional extra tools.
        cartridge_tools: Optional domain-specific tools (DomainCartridge mount).
        domain_directive: Optional domain-specific modeling prompt fragment
            appended to the system prompt (DomainCartridge mount).
    """
    tools = _merge_tools(
        [read_problem_file, export_paper_markdown, search_or_knowledge, get_problem_formulation_template],
        extra_tools,
        cartridge_tools,
    )
    prompt = (
        "你是 OR-Path 流水线中的【高水平运筹学学术论文撰写专家】(Writer)。\n\n"
        "【真数据来源声明】：论文中的所有表格与图必须以 Python 预渲染的核验真值表/真值图"
        "（如 outputs/<slug>-tables.md、outputs/<slug>-*.png）为唯一数据来源，"
        "你只负责成文与排版组织，严禁重算或臆造任何数值。\n" + ""
        "【核心定位与专职】\n"
        "严格遵循《运筹建模与学术论文规范 SOP》（docs/or-paper-sop.md），在 Verifier 确认"
        "校验通过 (ok: true) 后，基于真实解与研判工件撰写结构严密、公式规范、论证充分的高质量学术报告。\n\n"
        "标准六章学术规范（必须严格包含以下结构）：\n"
        "1. 摘要与关键指标速览 (MUST)：明确问题对象、目标值（objective）、求解器与状态、"
        "并包含诚实求解性质声明（若未证明最优，必须明确标注『搜索/可行轨，未证明全局最优』）；\n"
        "2. 问题重述与建模假设 (MUST)：精准引用原始题面数据，列出完整工程/物理假设及其对模型的影响，"
        "给出清晰的符号说明表（决策变量、参数、集合）；\n"
        "3. 数学规划模型建立 (MUST)：严格使用 LaTeX 公式分别给出决策变量及定义域、"
        "目标函数方向与权重、逐条编号约束集合（C1, C2...）并阐明物理含义；模型中严禁提前填入最优值；\n"
        "4. 求解策略与算子选型说明 (MUST)：论证算法选型理由、定性/定量分析算法复杂度与收敛性、"
        "明确求解器参数（时间上限、间隙 gap、随机种子）；\n"
        "5. 数值计算结果与敏感性分析 (MUST)：所有结果数值必须严格来自 solution.json 并标注重算一致；"
        "给出核心指标汇总表；至少变动一项关键参数进行敏感性分析，汇报真实重算变化；\n"
        "6. 模型评价、优缺点与工业落地建议 (MUST)：客观剖析模型优缺点与局限性清单，"
        "给出可落地的工业工程部署方案，清晰区分『本文已解决』与『未来工作』。\n\n"
        "硬性纪律（不可妥协）：\n"
        "- Numbers Truth：论文中的所有目标值、开销、指标必须严格来自 solution.json，严禁虚构、外推或凑数；\n"
        "- 完整论文必须调用 export_paper_markdown 写入 papers/<slug>.md（或指定路径），严禁在对话截断输出；\n"
        "- 对话返回仅保留一句话总结及导出的论文路径。"
    )
    return create_react_agent(
        _resolve_model(model), tools, prompt=append_domain_directive(prompt, domain_directive), name=WRITER_NAME
    )


def create_reviewer_agent(
    model: Any = None,
    domain_directive: str = "",
) -> Any:
    """Create the dedicated ``or_reviewer`` agent (adversarial internal peer reviewer).

    Audits the generated paper and solution against the 10-point SOP rubric:
    1. Checks numeric consistency (Numerics ⊆ solution.json);
    2. Flags unproven optimality hype as FATAL defects;
    3. Detects zombie sections, missing constraints, or unverified claims;
    4. Emits structured peer-review report (Summary, Strengths, Weaknesses with
       FATAL/MAJOR/MINOR tags, Questions, Verdict, Revision Plan) to outputs/<slug>-review.md.

    Args:
        model: Chat model instance. Defaults to ``get_chat_model()``.
        domain_directive: Optional domain-specific modeling prompt fragment
            appended to the system prompt (DomainCartridge mount).
    """
    tools = _merge_tools([read_problem_file, export_paper_markdown, validate_solution_tool])
    prompt = (
        "你是 OR-Path 流水线中的【严苛对立同行评审专家】(Reviewer)。\n\n"
        "【核心定位与专职】\n"
        "扮演顶尖期刊资深审稿人，坚持批判性思维，专门寻找论文与模型中的漏洞、数字不实与逻辑硬伤。\n\n"
        "十项严苛自审核对清单（依据 docs/or-paper-sop.md §6）：\n"
        "1. 结构完整度：摘要、重述与假设、数学模型、求解策略、结果与敏感性、评价建议六节是否齐全；\n"
        "2. 数字真实性 (Numbers Truth)：文中所有数值是否 100% 落在 solution.json 内，有无臆造数字；\n"
        "3. 独立重算状态：是否有 validate_solution_tool 独立重算通过证明；\n"
        "4. 最优性诚实声明：启发式算法是否夸大声称全局最优（未证明最优却声称最优直接判 FATAL）；\n"
        "5. 数学模型自洽性：决策变量、目标函数与约束是否完备，符号是否前后一致，模型是否违规夹带最优值；\n"
        "6. 证据链闭环：核心主张是否有数据/文献/算例支持；\n"
        "7. 引用合规性：有无伪造文献、虚构作者年份或无关引用；\n"
        "8. 敏感性分析真实性：敏感性分析是否基于真实重算而非定性脑补；\n"
        "9. 求解策略说明：是否给出复杂度、收敛性及参数说明；\n"
        "10. 局限性与落地建议：是否有明确客观的局限性清单与切实可行的工业落地建议。\n\n"
        "输出规范（必须调用 export_paper_markdown 写入 outputs/<slug>-review.md）：\n"
        "## Summary（论文总体工作概述）\n"
        "## Strengths（至少列出 2 项核心亮点 [S1], [S2]）\n"
        "## Weaknesses（明确标注缺陷等级）：\n"
        "  - [W1] **FATAL:** （致命缺陷，如数字不实、夸大最优、模型缺核心约束）\n"
        "  - [W2] **MAJOR:** （重大缺陷，如敏感性分析薄弱、符号冲突）\n"
        "  - [W3] **MINOR:** （轻微瑕疵，如排版、文字不通顺）\n"
        "## Questions for Authors（向作者提出的技术质疑 [Q1]...）\n"
        "## Verdict（结论：PASS 接受 / REVISE 打回修改）\n"
        "## Revision Plan（切实可行的修改指引）\n\n"
        "硬性纪律：\n"
        "- 严禁任何形式主义吹捧，发现 FATAL 必须坚决判定 REVISE 并要求修改；\n"
        "- 评审全文写入 outputs/<slug>-review.md，对话只返回裁决结论与审稿报告路径。"
    )
    return create_react_agent(
        _resolve_model(model), tools, prompt=append_domain_directive(prompt, domain_directive), name=REVIEWER_NAME
    )


def get_default_workers(model: Any = None) -> list[Any]:
    """Return the default four-elite roster ``[analyst, modeler, writer, reviewer]``.

    Args:
        model: Shared chat model instance for all workers. Defaults to
            ``get_chat_model()``.

    Returns:
        A list of compiled ``create_react_agent`` graphs in pipeline order.
    """
    return [
        create_analyst_agent(model=model),
        create_modeler_agent(model=model),
        create_writer_agent(model=model),
        create_reviewer_agent(model=model),
    ]


def get_academic_workers(model: Any = None) -> list[Any]:
    """Return the 5-worker gold-standard academic roster.

    Roster order:
      1. ``or_analyst``    — problem-statement analysis & data characteristics
      2. ``or_modeler``    — formal math formulation & solver execution
      3. ``or_verifier``   — independent recomputation & constraint auditing
      4. ``or_writer``     — 6-section publication-grade academic paper
      5. ``or_reviewer``   — adversarial peer review & FATAL/MAJOR/MINOR audit

    Args:
        model: Shared chat model instance. Defaults to ``get_chat_model()``.

    Returns:
        A list of five compiled ``create_react_agent`` graphs in pipeline order.
    """
    return [
        create_analyst_agent(model=model),
        create_modeler_agent(
            model=model,
            cartridge_tools=[consult_or_skill, get_problem_formulation_template],
        ),
        create_verifier_agent(model=model),
        create_writer_agent(model=model),
        create_reviewer_agent(model=model),
    ]


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    import warnings

    warnings.simplefilter("ignore")
    for worker in get_default_workers():
        print(type(worker).__name__, "->", worker.name)
