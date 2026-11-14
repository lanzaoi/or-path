"""Research, retrieval, orchestration, and bridge nodes."""
from __future__ import annotations

import json
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orpath.state import ORPathState
from orpath.paper_workflow import (
    append_plan_log,
    ensure_research_coverage_section,
    gate_research_text,
    load_retrieval,
)
from orpath.pipeline.common import (
    _root,
    _ensure_dirs,
    _fixture_base,
    _infer_class,
    _replay_authorized,
)


def node_orchestrate(state: ORPathState) -> dict:
    root = _root(state)
    _ensure_dirs(root)
    slug = state["slug"]
    # D2: merge human-steer at control-plane entry
    from orpath.human_steer import apply_steer_to_state

    steer_upd = apply_steer_to_state(dict(state), workdir=root, boundary="orchestrate")
    merged = {**dict(state), **steer_upd}
    allow_fix = _replay_authorized(merged)  # type: ignore[arg-type]
    pc = _infer_class(
        root,
        merged["problem_id"],
        merged.get("problem_class"),
        allow_fixture=allow_fix,
    )
    solve_mode = merged.get("solve_mode") or state.get("solve_mode")
    plan = root / "outputs" / ".plans" / f"{slug}.md"
    steer_line = ""
    if steer_upd.get("human_steer_applied"):
        steer_line = (
            f"- human_steer: applied path={steer_upd.get('human_steer_path')} "
            f"mode={solve_mode} at={steer_upd.get('human_steer_at_stage')}\n"
        )
    elif steer_upd.get("human_steer_path"):
        steer_line = f"- human_steer: none at {steer_upd.get('human_steer_path')}\n"
    plan.write_text(
        f"""# Plan {slug}

- problem_id: {merged["problem_id"]}
- problem_class: {pc}
- solve_mode: {solve_mode}
- knowledge_mode: {merged.get("knowledge_mode")}
- started: {datetime.now(timezone.utc).isoformat()}
- paper_template: or (P1)
{steer_line}
## Task ledger
- [ ] retrieve
- [ ] research
- [ ] model
- [ ] solve
- [ ] validate
- [ ] explain
- [ ] draft
- [ ] cite
- [ ] review
- [ ] provenance

## Decision log
- Numbers only from solve+validate; paper drafts layered under outputs/.drafts/
- Human steer (if any): control→solve_mode; cognitive→research/model briefs

## Verification log
""",
        encoding="utf-8",
    )
    append_plan_log(
        root,
        slug,
        stage="orchestrate",
        status="done",
        detail="plan created",
        plan_file=plan,
    )
    out = {
        "stage": "retrieve",
        "plan_path": str(plan),
        "problem_class": pc,
        "schema_repair": int(merged.get("schema_repair") or 0),
        "validate_repair": int(merged.get("validate_repair") or 0),
        "solver_tune": int(merged.get("solver_tune") or 0),
        "last_error": str(steer_upd.get("last_error") or ""),
        "solve_mode": solve_mode,
    }
    for k in (
        "human_steer_path",
        "human_steer_applied",
        "human_steer_lg",
        "human_steer_pi",
        "human_steer_at_stage",
        "human_steer_utc",
        "human_steer_fresh",
    ):
        if k in steer_upd:
            out[k] = steer_upd[k]
    return out


def node_retrieve(state: ORPathState) -> dict:
    """Write notes/<slug>-retrieval.json for research.

    Indexes always load from **install home** (knowledge_svc corpus).
    Artifacts always write under **case root/workdir** notes/.
    """
    from orpath.paths import orpath_home

    root = _root(state)  # workdir / case root
    home = orpath_home()
    slug = state["slug"]
    mode = _resolve_knowledge_mode(state.get("knowledge_mode"))
    out = root / "notes" / f"{slug}-retrieval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    pc = str(state.get("problem_class") or "")
    pid = str(state.get("problem_id") or "")
    query = _retrieval_query(pc, pid)

    # Process memory (auto): past solve process / key points → notes/*-lessons.*
    lessons_path = ""
    try:
        from orpath.process_memory import write_retrieve_artifacts

        _j, mpath, _hits = write_retrieve_artifacts(
            root,
            slug,
            query=query,
            problem_class=str(pc) if pc else None,
            topk=5,
        )
        lessons_path = str(mpath)
    except Exception:  # noqa: BLE001
        lessons_path = ""

    if mode == "off":
        art = {
            "query": query,
            "knowledge_mode": "off",
            "hits": [],
            "seed_facts": [],
            "index_home": str(home),
        }
        out.write_text(json.dumps(art, indent=2) + "\n", encoding="utf-8")
        upd: dict = {"stage": "research", "retrieval_path": str(out)}
        if lessons_path:
            upd["lessons_path"] = lessons_path
        return upd

    # Prefer in-process knowledge_svc (same as CLI) with home indexes
    try:
        from knowledge_svc.retrieve import retrieve as ks_retrieve
        from knowledge_svc.retrieve import artifact_to_payload
        from knowledge_svc.chunk_schema import write_json

        art_obj = ks_retrieve(
            query,
            mode=mode if mode in {"seed", "hybrid", "off"} else "seed",  # type: ignore[arg-type]
            topk=5,
            root=home,
            problem_class=pc or None,
            force_stub=None,  # ORPATH_KNOWLEDGE_EMBED=auto|live|stub
        )
        payload = artifact_to_payload(art_obj)
        payload["index_home"] = str(home)
        payload["workdir_notes"] = str(out)
        write_json(out, payload)
    except Exception as exc:  # noqa: BLE001
        import subprocess
        import sys

        cmd = [
            sys.executable,
            "-m",
            "knowledge_svc.retrieve",
            "--query",
            query,
            "--mode",
            mode,
            "--topk",
            "5",
            "--out",
            str(out),
        ]
        if pc:
            cmd.extend(["--class", pc])
        r = subprocess.run(
            cmd,
            cwd=str(home),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        if r.returncode != 0 or not out.is_file():
            seed_path = home / "knowledge" / "seed_graph" / "or_domain_seed.json"
            facts = []
            if seed_path.is_file():
                seed = json.loads(seed_path.read_text(encoding="utf-8"))
                for n in seed.get("nodes") or []:
                    if n.get("type") == "ProblemClass" and n.get("id") == pc:
                        facts.append(n)
                    if n.get("type") == "Solver":
                        facts.append(n)
            art = {
                "query": query,
                "knowledge_mode": mode,
                "hits": [],
                "seed_facts": facts,
                "fallback": True,
                "index_home": str(home),
                "cli_err": (r.stderr or r.stdout or str(exc))[:500],
            }
            out.write_text(json.dumps(art, indent=2) + "\n", encoding="utf-8")

    upd = {"stage": "research", "retrieval_path": str(out), "last_error": "", "knowledge_mode": mode}
    if lessons_path:
        upd["lessons_path"] = lessons_path
    return upd


def _retrieval_query(problem_class: str, problem_id: str) -> str:
    """Class-aware hybrid query so research gets relevant corpus hits."""
    pc = (problem_class or "").strip().lower()
    pid = (problem_id or "").strip()
    table = {
        "shortest_path": "shortest path Dijkstra networkx solver label-setting",
        "tsp": "TSP tour OR-Tools routing CP-SAT circuit MTZ subtour",
        "vrp": "CVRP capacity multi vehicle column generation set covering OR-Tools",
        "polyomino_cover": "polyomino cover CP-SAT exact cover dancing links board",
        "polyomino": "polyomino cover CP-SAT exact cover board schema",
        # cutting-stock / tube: force method vocabulary into RAG (CG, residual, co-cut…)
        "tube_cut": (
            "one-dimensional cutting stock column generation residual problem "
            "irregular tube co-cut nesting bin packing pattern generation "
            "sequence-dependent setup remnant reuse"
        ),
        "cutting_stock": (
            "cutting stock column generation Gilmore Gomory residual knapsack "
            "bin packing pattern generation remnant"
        ),
        "cut_stock": "cutting stock column generation residual knapsack bin packing",
    }
    base = table.get(pc) or (
        f"operations research {problem_class or pid or 'optimization'} "
        f"column generation branch and price heuristics modeling"
    )
    if pid and pid not in base:
        return f"{base} {pid}"
    return base


def _resolve_knowledge_mode(raw: str | None) -> str:
    """Product default = hybrid RAG (not empty seed). Env ORPATH_KNOWLEDGE_MODE overrides.

    Set ORPATH_KNOWLEDGE_MODE=seed|off to opt out (CI smoke may still pass hybrid).
    """
    env = (os.environ.get("ORPATH_KNOWLEDGE_MODE") or "").strip().lower()
    if env in {"off", "seed", "hybrid"}:
        return env
    m = (raw or "").strip().lower()
    if m in {"off", "seed", "hybrid"}:
        # legacy CLI default was seed — promote bare seed to hybrid for product depth
        if m == "seed" and (os.environ.get("ORPATH_KNOWLEDGE_FORCE_HYBRID") or "1").strip() not in {
            "0",
            "false",
            "no",
        }:
            return "hybrid"
        return m
    return "hybrid"


# --------------------------------------------------------------------------- #
# Phase 3.1 — deterministic preflight probe + or_analyst research
# --------------------------------------------------------------------------- #


def _profile_attachment_table_md(profile: dict[str, Any]) -> str:
    """Deterministic attachment table: real headers / row counts from the probe."""
    items = profile.get("input_files") or []
    if not items:
        return "- （探针未发现可画像的附件文件）\n"
    lines: list[str] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        f = str(it.get("file", "?"))
        fmt = str(it.get("format", "?"))
        bytes_ = it.get("bytes", "?")
        sha = str(it.get("sha256") or "")[:12]
        sheets = it.get("sheets") if isinstance(it.get("sheets"), dict) else {}
        if sheets:
            for sname, sm in sheets.items():
                fields: list[str] = []
                nrows = "?"
                if isinstance(sm, dict):
                    fields = [str(x) for x in (sm.get("fields") or []) if str(x).strip()]
                    nrows = sm.get("rows", "?")
                disp = ", ".join(fields[:12])
                if len(fields) > 12:
                    disp += ", …"
                lines.append(
                    f"| {f} | {fmt} | {sname} | {nrows} | {len(fields)} | "
                    f"{disp or '(空表头)'} | {bytes_} | {sha} |"
                )
        else:
            fields = [str(x) for x in (it.get("fields") or []) if str(x).strip()]
            nrows = it.get("rows", "?")
            disp = ", ".join(fields[:12])
            if len(fields) > 12:
                disp += ", …"
            lines.append(
                f"| {f} | {fmt} | - | {nrows} | {len(fields)} | "
                f"{disp or '(无表头字段)'} | {bytes_} | {sha} |"
            )
    header = "| 附件 | 格式 | Sheet/对象 | 数据行数 | 列数 | 表头字段(前12) | 字节 | sha256(12) |"
    sep = "|---|---|---|---|---|---|---|---|"
    return "\n".join([header, sep, *lines]) + "\n"


_CONSTRAINT_FIELD_VOCAB: dict[str, tuple[str, ...]] = {
    "demand / 需求": ("demand", "需求", "需求量", "orders", "订单"),
    "capacity / 容量": ("capacity", "容量", "载重", "vehicle_count", "车辆数"),
    "cost / 成本": ("cost", "成本", "费用", "price", "价格", "利润", "profit"),
    "duration / 时序": ("time", "时间", "时长", "工期", "duration", "deadline", "截止"),
    "resource / 资源": ("resource", "资源", "工时", "产能", "机器", "machine", "worker"),
    "inventory / 库存": ("stock", "库存", "inventory", "订货", "批次", "batch"),
    "precedence / 工序偏序": ("pred", "前置", "依赖", "precedence", "工序"),
    "geometry / 区位": ("location", "坐标", "位置", "distance", "距", "depot", "仓库"),
    "probability / 概率": ("概率", "probability", "scenario", "情景", "random"),
    "workpiece / 工件规格": ("workpiece", "工件", "管材", "stock_length", "母材"),
}


def _profile_constraint_mapping_md(profile: dict[str, Any]) -> str:
    """Deterministic field→constraint mapping from probe headers (no speculation)."""
    items = profile.get("input_files") or []
    lines: list[str] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        f = str(it.get("file", "?"))
        fields: list[str] = []
        sheets = it.get("sheets") if isinstance(it.get("sheets"), dict) else {}
        for sm in sheets.values():
            if isinstance(sm, dict):
                fields += [str(x) for x in (sm.get("fields") or [])]
        fields += [str(x) for x in (it.get("fields") or [])]
        low = " ".join(fields).lower()
        hits = [
            label
            for label, kws in _CONSTRAINT_FIELD_VOCAB.items()
            if any(k in low for k in kws)
        ]
        if hits:
            lines.append(f"- `{f}` → " + "；".join(hits))
        else:
            lines.append(
                f"- `{f}` → （表头未命中常见约束词表；以题面逐条约束为准，不臆测）"
            )
    if not lines:
        return "- （无附件可映射）\n"
    return "\n".join(lines) + "\n"


def _probe_document(
    root: Path, slug: str, pid: str, pc: str, data_files: list[str],
    problem_file: str = "",
    *,
    allow_fixture: bool = True,
) -> dict[str, Any]:
    """Deterministic preflight probe → outputs/<slug>-profile.json (Phase 3.1)."""
    from orpath.agents.deterministic_nodes import run_preflight_probe

    probe_state = {
        "slug": slug,
        "workdir": str(root),
        "problem_class": pc or "",
        "problem_file": str(problem_file or ""),
        "data_files": list(data_files or []),
    }
    # explicit problem_file from state is rare here; collect via probe itself
    upd: dict[str, Any] = {}
    try:
        upd = dict(run_preflight_probe(probe_state))
    except Exception:  # noqa: BLE001 - fixture-only case has no inbox files
        upd = {}
    ppath = Path(str(upd.get("profile_path") or (root / "outputs" / f"{slug}-profile.json")))
    if not ppath.is_file():
        upd = _minimal_profile(root, slug, pid, pc, data_files, allow_fixture=allow_fixture)
        ppath = Path(str(upd.get("profile_path")))
    return {"profile_path": str(ppath), **{
        k: v for k, v in upd.items() if k != "profile_path"
    }}


def _minimal_profile(
    root: Path,
    slug: str,
    pid: str,
    pc: str,
    data_files: list[str],
    *,
    allow_fixture: bool = True,
) -> dict[str, Any]:
    """No inbox files: profile fixture/intake files deterministically (still writes profile.json)."""
    from orpath.agents.deterministic_nodes import (
        collect_input_files,
        file_overview,
        guess_domain,
        guess_problem_class,
    )

    files, notes = collect_input_files(root, slug, data_files)
    fb = _fixture_base(root, pid, allow_fixture=allow_fixture)
    if fb and fb.is_dir():
        seen = {str(p) for p in files}
        for p in sorted(fb.rglob("*")):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".json", ".csv", ".tsv", ".md", ".txt", ".docx", ".xlsx", ".xlsm", ".pdf"}:
                continue
            if str(p) not in seen:
                files.append(p)
                seen.add(str(p))
    manifest: list[dict[str, Any]] = []
    for p in files:
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        item = {"file": rel, "abs_path": str(p)}
        item.update({k: v for k, v in file_overview(p).items() if k != "abs_path"})
        manifest.append(item)
    domain = guess_domain(slug, *[m.get("file", "") for m in manifest])
    cls = guess_problem_class(pc or "", slug, *[m.get("file", "") for m in manifest])
    profile = {
        "slug": slug,
        "generated_by": "orpath.pipeline.research._minimal_profile",
        "root": str(root),
        "input_files": manifest,
        "notes": notes,
        "summary": {
            "num_files": len(manifest),
            "total_bytes": sum(int(m.get("bytes") or 0) for m in manifest),
            "guessed_domain": domain,
            "guessed_problem_class": cls,
        },
    }
    (root / "outputs").mkdir(parents=True, exist_ok=True)
    ppath = root / "outputs" / f"{slug}-profile.json"
    ppath.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "profile_path": str(ppath),
        "data_files": [m["file"] for m in manifest][:512],
        "problem_class": (cls or pc or ""),
        "domain_cartridge": domain,
        "preflight_ok": True,
    }


def _live_research_enabled(state_m: dict[str, Any]) -> bool:
    """or_analyst research only under explicit live deep mode + real LLM credentials."""
    if str(state_m.get("run_mode") or "deep").strip().lower() == "fast":
        return False
    if (
        os.environ.get("PYTEST_CURRENT_TEST")
        and not state_m.get("force_live_agent")
    ):
        return False
    raw = state_m.get("live_subagent")
    if raw is None:
        env = (os.environ.get("ORPATH_LIVE_SUBAGENT") or "").strip().lower()
        raw = env in {"1", "true", "yes", "on"}
    if not raw:
        return False
    try:
        from orpath.control_plane import is_real_llm_configured

        return is_real_llm_configured()
    except Exception:  # noqa: BLE001
        return False


def _invoke_last_ai_text(resp: Any) -> str:
    msgs = resp.get("messages") if isinstance(resp, dict) else None
    if not msgs:
        return ""
    from langchain_core.messages import AIMessage

    for msg in reversed(list(msgs)):
        if isinstance(msg, AIMessage):
            text = msg.content
            if isinstance(text, list):
                text = json.dumps(text, ensure_ascii=False, default=str)
            return str(text)[:7000]
    return ""


def _run_analyst_research(
    state_m: dict[str, Any],
    root: Path,
    slug: str,
    pc: str,
    domain_key: str,
    tier: str,
    profile_path: str,
    retrieval_path: str,
) -> str:
    """Wake or_analyst for a deep, high-density research brief (online mode)."""
    from langchain_core.messages import HumanMessage

    from orpath.agents.workers import create_analyst_agent

    try:
        from orpath.control_plane import get_tiered_chat_model

        model = get_tiered_chat_model("fast")
    except Exception:  # noqa: BLE001 - 3.4 factory not present yet
        from orpath.control_plane import get_chat_model

        model = get_chat_model()
    cartridge_tools = None
    try:
        from orpath.agents.cartridges import cartridge_tools

        cartridge_tools = cartridge_tools(domain_key)
    except Exception:  # noqa: BLE001
        cartridge_tools = None
    agent = create_analyst_agent(model=model, cartridge_tools=cartridge_tools)
    brief = f"""[OR-Path 深度研判任务 (Phase 3.1)]
workdir={root} slug={slug} problem_id={state_m.get('problem_id')} problem_class={pc}
domain_cartridge={domain_key} complexity_tier={tier}

已就绪的确定性工件:
- 数据画像(profile): {profile_path}
- 混合知识库检索(retrieval): {retrieval_path}

任务:
1. 先读取 profile 产物, 逐列核对每个附件的真实表头字段与数据行数, 严禁臆造任何数值;
2. 用 read_problem_file 打开原始题面/数据文件, 识别题型并拆解: 决策变量/目标层级(单目标/分层/多问)/硬约束/软约束/数据歧义点;
3. 校验或反拨复杂度分档 (Tier-A/B/C), 确认 DomainCartridge;
4. 输出一份高信息密度 research.md 正文, 使用以下标题: '# Research: {slug}'、'## 摘要研判'、'## 数据附件画像'、'## 决策变量与目标层级'、'## 约束映射'、'## 数学分类与装备包'、'## 建模建议与歧义';
5. 禁止: 不得输出任何最优值/目标值答案(仅方法与建模结构); 不得编造未在附件中出现的字段名; 输出控制在 1200 字以内, 中文、紧凑、表格化。"""
    from orpath.control_plane import invoke_with_backoff

    resp = invoke_with_backoff(agent, {"messages": [HumanMessage(brief)]})
    return _invoke_last_ai_text(resp)


def _deterministic_skeleton(
    state_m: dict[str, Any],
    root: Path,
    slug: str,
    pid: str,
    pc: str,
    mode: str,
    retrieval: dict[str, Any],
    profile: dict[str, Any],
    domain_key: str,
    tier: str,
    cartridge_name: str,
    checklist: tuple[str, ...],
) -> str:
    """Offline CI research skeleton — attachment tables + constraint mappings (zero speculation)."""
    from orpath.human_steer import format_pi_steer_block

    allow_fix = _replay_authorized(state_m)  # type: ignore[arg-type]
    fb = _fixture_base(root, pid, allow_fixture=allow_fix)
    problem = (
        (fb / "problem.md").read_text(encoding="utf-8")
        if fb and (fb / "problem.md").is_file()
        else ""
    )
    hits = retrieval.get("hits") or []
    seed_facts = retrieval.get("seed_facts") or []
    cite_rows = []
    for i, h in enumerate(hits[:5], 1):
        cite_rows.append(
            f"| {i} | chunk | {h.get('chunk_id')} | {str(h.get('snippet', ''))[:80]} | retrieval | med |"
        )
    if not cite_rows:
        cite_rows.append(
            f"| 1 | Problem | {(fb.as_posix() + '/problem.md') if fb else 'n/a'} | fixture primary | primary | high |"
        )
    for j, s in enumerate(seed_facts[:3], len(cite_rows) + 1):
        cite_rows.append(
            f"| {j} | seed | {s.get('id')} | {s.get('label', s.get('name', ''))} | seed | high |"
        )
    steer_block = format_pi_steer_block(state_m)
    steer_section = f"\n## Human steer\n{steer_block}\n" if steer_block else ""
    checklist_md = "\n".join(f"- {item}" for item in checklist) or "- 无领域核对清单 (按题面逐条约束建模)"
    return f"""# Research: {slug}

## 摘要研判
- 问题: `{pc}` / `{pid}`; 装备包={cartridge_name}; 复杂度分档=Tier-{tier}。
- 数据画像: {profile.get('summary', {}).get('num_files', '?')} 个附件 (见下表); retrieval mode={retrieval.get('knowledge_mode', mode)}。
- 数学分类: {pc or '待研判'} (由确定性探针与检索命中共同佐证, 无任何臆测最优值)。
{steer_section}
## 数据附件画像（确定性探针 outputs/<slug>-profile.json）
{_profile_attachment_table_md(profile)}
## 决策变量与目标层级
- 决策变量/目标层级以题面为准（未求解，仅建模引导）；严禁在此预填任何数值答案。

## 约束映射
- 字段→约束映射（由探针表头关键词确定性推导）：
{_profile_constraint_mapping_md(profile)}
- 领域核对清单 ({cartridge_name}):
{checklist_md}

## 数学分类与装备包
- problem_class: {pc}
- DomainCartridge: {cartridge_name} ({domain_key})
- complexity_tier: {tier}

## Method candidates (from RAG / domain)
- Prefer algorithms named in retrieval snippets (column generation, pattern generation, BFD, CP-SAT, ...).
- Map each candidate to which subproblem it might serve.
- If hits empty, say so explicitly and fall back to classical OR vocabulary for the class.

## Evidence table
| # | Source | Path/URL | Key claim | Type | Confidence |
|---|--------|----------|-----------|------|------------|
{chr(10).join(cite_rows)}

## Findings
1. Use deterministic solvers (networkx/cpsat/highs/ortools); never LLM optima.
2. Validate must recompute objective.
3. Seed/retrieval chunk_ids when present must be cited in this table.
4. Attachment headers above are probe-truth (file + sha); 缺列时以题面为准并在歧义清单声明。

## Modeling recommendations
- problem_class: {pc}
- no objective/tour/routes/path answers in schema
- preferred_solve_mode hint: {state_m.get('solve_mode') or 'n/a'}

## Retrieval artifact
`{state_m.get('retrieval_path') or ('notes/' + slug + '-retrieval.json')}`

## Process memory (lessons)
`{state_m.get('lessons_path') or (root / 'notes' / f'{slug}-lessons.md')}`
(Process tips only - not authoritative optima.)

## Problem excerpt
{problem[:800]}
"""


def node_research(state: ORPathState) -> dict:
    root = _root(state)
    # D2: re-merge steer + optional pause before research
    from orpath.human_steer import apply_steer_to_state, format_pi_steer_block

    steer_upd = apply_steer_to_state(dict(state), workdir=root, boundary="research")
    if steer_upd.get("steer_pause"):
        return steer_upd
    state_m = {**dict(state), **steer_upd}
    slug = state_m["slug"]
    pid = state_m["problem_id"]
    allow_fix = _replay_authorized(state_m)  # type: ignore[arg-type]
    pc = str(state_m.get("problem_class") or "").strip() or _infer_class(
        root, pid, None, allow_fixture=allow_fix
    )
    mode = _resolve_knowledge_mode(state_m.get("knowledge_mode"))
    fb = _fixture_base(root, pid, allow_fixture=allow_fix)
    path = root / "notes" / f"{slug}-research.md"
    rp = state_m.get("retrieval_path")
    retrieval = load_retrieval(rp)

    # --- Phase 3.1 step 1: deterministic preflight probe -> outputs/<slug>-profile.json
    probe = _probe_document(
        root, slug, pid, pc, list(state_m.get("data_files") or []),
        str(state_m.get("problem_file") or ""),
        allow_fixture=allow_fix,
    )
    profile_path = str(probe.get("profile_path") or (root / "outputs" / f"{slug}-profile.json"))
    profile: dict[str, Any] = {}
    try:
        profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        profile = {}
    probe_class = str(probe.get("problem_class") or "").strip().lower()
    if not pc or pc in {"unknown", "none"}:
        if probe_class and probe_class != "unknown":
            pc = probe_class
    try:
        from orpath.domain_registry import is_known_class

        if not is_known_class(pc):
            if probe_class and is_known_class(probe_class):
                pc = probe_class
    except Exception:  # noqa: BLE001
        pass

    # --- Phase 3.1 step 2: DomainCartridge + complexity tier selection
    try:
        from orpath.agents.cartridges import cartridge_tier, resolve_cartridge

        cartridge = resolve_cartridge(pc)
        domain_key = str(cartridge.domain)
        tier = str(cartridge_tier(pc))
        checklist = tuple(cartridge.modeling_checklist or ())
    except Exception:  # noqa: BLE001
        domain_key = str(probe.get("domain_cartridge") or "general_or")
        tier = "B"
        checklist = ()
    cartridge_name = domain_key

    # --- Deterministic scaffold if no research file yet
    if not path.is_file() or path.stat().st_size < 40:
        if _live_research_enabled(state_m):
            try:
                text = _run_analyst_research(
                    state_m, root, slug, pc, domain_key, tier, profile_path, str(rp or "")
                )
                if text and len(text) >= 40:
                    path.write_text(text.rstrip() + "\n", encoding="utf-8")
            except Exception as exc:  # noqa: BLE001 - never block online mode on LLM failure
                warnings.warn(
                    f"or_analyst research failed, deterministic fallback: {exc}", stacklevel=2
                )
        if not path.is_file() or path.stat().st_size < 40:
            body = _deterministic_skeleton(
                state_m, root, slug, pid, pc, mode, retrieval, profile, domain_key, tier,
                cartridge_name, checklist,
            )
            path.write_text(body, encoding="utf-8")

    ret_disk_p = Path(str(state_m.get("retrieval_path") or (root / "notes" / f"{slug}-retrieval.json")))
    if ret_disk_p.is_file():
        try:
            retrieval = json.loads(ret_disk_p.read_text(encoding="utf-8"))
        except Exception:
            pass
    body = path.read_text(encoding="utf-8")
    body2 = ensure_research_coverage_section(body, retrieval or {"knowledge_mode": mode})
    # inject steer section if missing
    sb = format_pi_steer_block(state_m)
    if sb and "## Human steer" not in body2:
        body2 = body2.rstrip() + "\n\n## Human steer\n" + sb + "\n"
    # deterministic guarantee tail for the research gate (evidence table + attachment grounding)
    ok_probe, errs_probe = gate_research_text(body2, knowledge_mode=mode, retrieval=retrieval)
    if not ok_probe:
        tail_items: list[str] = []
        hits = retrieval.get("hits") or []
        for i, h in enumerate(hits[:5], 1):
            tail_items.append(
                f"| {i} | chunk | {h.get('chunk_id')} | {str(h.get('snippet', ''))[:80]} | retrieval | deterministic |"
            )
        for j, s in enumerate(retrieval.get("seed_facts") or [], len(tail_items) + 1):
            tail_items.append(
                f"| {j} | seed | {s.get('id')} | {s.get('label', s.get('name', ''))} | seed | high |"
            )
        tail = (
            "\n## Evidence table (deterministic guarantee)\n\n"
            "| # | Source | Path/URL | Key claim | Type | Confidence |\n"
            "|---|--------|----------|-----------|------|------------|\n"
            + "\n".join(tail_items or ["| - | - | - | retrieval absent — honest empty | deterministic | - |"])
            + "\n"
        )
        if "## 数据附件画像" not in body2:
            tail += "\n## 数据附件画像（确定性探针）\n\n" + _profile_attachment_table_md(profile)
            tail += "\n## 约束映射（确定性）\n\n" + _profile_constraint_mapping_md(profile)
        body2 = body2.rstrip() + "\n" + tail
    if body2 != body:
        path.write_text(body2, encoding="utf-8")
        body = body2

    ok, errs = gate_research_text(body, knowledge_mode=mode, retrieval=retrieval)

    append_plan_log(
        root,
        slug,
        stage="research",
        status="pass" if ok else "fail",
        detail=(
            "; ".join(errs)
            if errs
            else f"evidence+coverage ok profile={Path(profile_path).name}"
        ),
        plan_file=state_m.get("plan_path"),
    )
    base_out = {
        k: steer_upd[k]
        for k in steer_upd
        if k.startswith("human_steer") or k in {"solve_mode"}
    }
    # persist Phase 3.1 pointers for downstream model stage
    state_out = {
        **base_out,
        "stage": "model",
        "research_path": str(path),
        "profile_path": profile_path,
        "data_files": list(probe.get("data_files") or []),
        "domain_cartridge": domain_key,
        "complexity_tier": tier,
        "cartridge_domain": domain_key,
        "gate_subagent_ok": None,
        "last_error": "",
    }
    if not ok and mode in {"seed", "hybrid"}:
        state_out["stage"] = "human_stop"
        state_out["human_required"] = True
        state_out["last_error"] = "research_gate: " + "; ".join(errs)
    return state_out
