#!/usr/bin/env python3
"""Deterministic Zero-LLM Knowledge Pack & Error-Remediation Engine.

Turns OR-Path's local knowledge assets (`knowledge/` + `knowledge_svc/`) from
passive optional tools into a deterministic, sub-50ms push-and-feedback
backbone:

  1. ``assemble_preflight_knowledge_pack`` — runs during ``run_preflight_probe``
     (0 LLM tokens, <50ms) to assemble DomainCartridge checklists, skill
     highlights, canonical LaTeX formulations from ``or-problems.md``, hybrid /
     FTS corpus method hits, historical ``orpath.lesson.v1`` lessons, user
     pinned knowledge from ``human-steer.json``, and authoritative bibliography
     entries from ``or_papers_top500.json`` into ``notes/<slug>-knowledge-pack.md``.
  2. ``build_error_remediation_pack`` — runs when ``deterministic_validator``
     rejects a candidate solution, performing targeted error-driven retrieval
     against lessons & modeling-pattern notes into ``notes/<slug>-remediation.md``.
  3. ``match_top_literature`` — deterministically matches domain-aligned top
     journal papers from ``knowledge/or_papers_top500.json`` for truth tables
     and academic paper citation anchoring.

Strict invariants:
  * **Zero LLM imports** — never imports ``langchain`` / ``langchain_core`` /
    ``langgraph`` (verified by AST unit test).
  * **Numbers Truth** — never embeds instance-specific objective values, optimal
    tours, or routes as authoritative answers.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

__all__ = [
    "assemble_preflight_knowledge_pack",
    "build_error_remediation_pack",
    "extract_formulation_snippet",
    "extract_skill_highlights",
    "load_pinned_knowledge",
    "match_top_literature",
]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}")

# Process-level caches for static read-only knowledge catalogs
_TOP500_CACHE: dict[Path, list[dict[str, Any]]] = {}
_HANDBOOK_CACHE: dict[Path, list[str]] = {}

#: Map OR-Path problem_class / domain_cartridge -> or_papers_top500.json domain tags
_LIT_DOMAIN_MAP: dict[str, tuple[str, ...]] = {
    "shortest_path": ("network_flows", "graph_or"),
    "network_flow": ("network_flows", "graph_or", "linear_programming"),
    "tsp": ("tsp_routing", "combinatorial_optimization", "integer_programming"),
    "vrp": ("tsp_routing", "metaheuristics", "column_generation_decomp"),
    "cvrp": ("tsp_routing", "metaheuristics", "column_generation_decomp"),
    "vrptw": ("tsp_routing", "constraint_programming", "column_generation_decomp"),
    "pyvrp": ("tsp_routing", "metaheuristics"),
    "routing": ("tsp_routing", "metaheuristics", "network_flows"),
    "jssp": ("scheduling", "constraint_programming"),
    "fjssp": ("scheduling", "constraint_programming", "metaheuristics"),
    "job_shop": ("scheduling", "constraint_programming"),
    "scheduling": ("scheduling", "constraint_programming"),
    "rcpsp": ("scheduling", "constraint_programming", "integer_programming"),
    "project": ("scheduling", "constraint_programming"),
    "staff_rostering": ("scheduling", "integer_programming", "constraint_programming"),
    "rostering": ("scheduling", "integer_programming"),
    "tube_cut": ("cutting_packing", "column_generation_decomp", "dynamic_programming"),
    "tube": ("cutting_packing", "column_generation_decomp"),
    "polyomino_cover": ("cutting_packing", "constraint_programming", "combinatorial_optimization"),
    "polyomino": ("cutting_packing", "constraint_programming"),
    "bin_packing": ("cutting_packing", "column_generation_decomp", "combinatorial_optimization"),
    "facility_location": ("integer_programming", "combinatorial_optimization"),
    "hub_location": ("integer_programming", "network_flows"),
    "qap": ("combinatorial_optimization", "integer_programming", "metaheuristics"),
    "facility": ("integer_programming", "combinatorial_optimization"),
    "lot_sizing": ("inventory_supply_chain", "dynamic_programming", "integer_programming"),
    "inventory": ("inventory_supply_chain", "dynamic_programming"),
    "portfolio_opt": ("nonlinear_convex", "multiobjective", "stochastic_or"),
    "finance": ("nonlinear_convex", "multiobjective"),
    "portfolio": ("nonlinear_convex", "multiobjective"),
    "stochastic_lp": ("stochastic_or", "linear_programming"),
    "pricing": ("stochastic_or", "linear_programming"),
    "microgrid_dispatch": ("linear_programming", "dynamic_programming", "stochastic_or"),
    "microgrid": ("linear_programming", "dynamic_programming"),
    "qubo_ising": ("combinatorial_optimization", "graph_or", "metaheuristics"),
    "graph_coloring": ("graph_or", "constraint_programming", "combinatorial_optimization"),
    "max_clique": ("graph_or", "combinatorial_optimization", "integer_programming"),
    "game_theory": ("game_theory_or", "linear_programming"),
}

#: Deterministic section keywords in knowledge/skills/or-problems.md
_FORMULATION_KEYS: dict[str, tuple[str, ...]] = {
    "shortest_path": ("最短路径", "3.1"),
    "network_flow": ("最大流", "3.2", "最小费用流"),
    "tsp": ("旅行商", "2.1", "tsp"),
    "vrp": ("车辆路径", "2.2", "vrp"),
    "cvrp": ("车辆路径", "2.2", "vrp"),
    "vrptw": ("车辆路径", "2.2", "vrp"),
    "pyvrp": ("车辆路径", "2.2", "vrp"),
    "bin_packing": ("装箱", "2.3", "bin packing"),
    "tube_cut": ("装箱", "2.3", "下料"),
    "polyomino_cover": ("装箱", "2.3", "整数规划"),
    "jssp": ("调度问题", "2.4", "scheduling"),
    "fjssp": ("调度问题", "2.4", "scheduling"),
    "job_shop": ("调度问题", "2.4", "scheduling"),
    "rcpsp": ("调度问题", "2.4", "scheduling"),
    "staff_rostering": ("整数规划", "1.2", "调度问题"),
    "facility_location": ("选址", "3.4", "11."),
    "hub_location": ("选址", "3.4", "11."),
    "qap": ("整数规划", "1.2", "选址"),
    "lot_sizing": ("库存优化", "6.", "动态规划"),
    "portfolio_opt": ("非线性规划", "1.3", "多目标"),
    "stochastic_lp": ("随机规划", "4.", "报童问题"),
    "microgrid_dispatch": ("滚动时域", "13.3", "17.2", "线性规划"),
    "microgrid": ("滚动时域", "13.3", "17.2", "线性规划"),
    "game_theory": ("博弈论", "9."),
    "qubo_ising": ("整数规划", "1.2"),
    "graph_coloring": ("整数规划", "1.2"),
    "max_clique": ("整数规划", "1.2"),
}

#: Targeted remediation playbooks triggered by validator error signatures
_ERROR_PLAYBOOKS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (
        ("recompute_objective", "objective mismatch", "expected=", "目标值"),
        "recompute_objective validator law",
        "目标值独立重算不一致：严禁手填或缩放近似目标值；必须用原始输入矩阵/价格表按验证器同一口径精确求和重算 objective，并核对单位换算（如 m vs mm、kW vs kWh）。",
    ),
    (
        ("subtour", "circuit", "disconnected", "cycle", "tour", "子回路", "连通"),
        "tsp subtour elimination circuit cpsat",
        "路径连通性/子回路违约：TSP/VRP 必须显式施加消除子回路约束（CP-SAT 使用 AddCircuit / AddMultipleCircuit；MILP 使用 MTZ 辅助序变量或 DFJ 惰性割平面），并校验首尾闭合。",
    ),
    (
        ("capacity", "overload", "demand", "load", "容量", "超载"),
        "cvrp capacity constraint cumulative",
        "容量/载荷越界：核查每条路线或每个箱体/机器的累计需求 sum(d_i) <= Q，未服务客户不得遗漏。",
    ),
    (
        ("time_window", "tw", "late", "arrival", "时间窗"),
        "vrptw time window propagation",
        "时间窗违约：到达时间递推需满足 t_j >= max(e_i, t_i) + service_i + travel_ij 且 e_j <= t_j <= l_j，注意等待时间不可压缩行程。",
    ),
    (
        ("overlap", "precedence", "makespan", "machine", "工序", "紧前"),
        "jssp rcpsp no_overlap cumulative precedence",
        "工序时序/机器重叠违约：同一机器区间必须加 AddNoOverlap，同工件紧前工序必须满足 end(u) <= start(v)（含换模时延 setup_uv），makespan >= max(end)。",
    ),
    (
        ("soc", "charge", "discharge", "power", "battery", "储能", "功率平衡"),
        "microgrid soc conservation charge exclusion",
        "微电网物理守恒违约：核查各时段功率平衡 buy + pv + dis - ch >= load、SOC 状态递推 SOC(t) = SOC(t-1) + eta_c*ch*dt - dis*dt/eta_d、SOC 上下界及充放电互斥。",
    ),
    (
        ("kerf", "residual", "stock", "cutting", "overlap_poly", "余料", "刀缝"),
        "cutting stock kerf residual polyomino cover",
        "切割/排样几何违约：总下料长度须计入刀缝 (n_cuts * kerf) <= L_raw，跨批次余料继承不可透支，网格覆盖不得越界或重叠。",
    ),
    (
        ("proven_optimal", "global_optimal", "optimality", "全局最优"),
        "numbers truth optimality claim",
        "最优性诚实声明违约：启发式/元启发式或限时截断 (status=FEASIBLE) 必须设 proven_optimal=False，严禁声称全局最优。",
    ),
)


def _resolve_home(home: Path | None = None) -> Path:
    if home is not None:
        p = Path(home).resolve()
        if (p / "knowledge").is_dir():
            return p
    env_home = (os.environ.get("ORPATH_HOME") or "").strip()
    if env_home:
        p = Path(env_home).expanduser().resolve()
        if (p / "knowledge").is_dir():
            return p
    return _REPO_ROOT


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def _strip_frontmatter(md_text: str) -> str:
    if md_text.startswith("---"):
        parts = md_text.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return md_text.strip()


def _load_top500(home: Path) -> list[dict[str, Any]]:
    path = (home / "knowledge" / "or_papers_top500.json").resolve()
    if path in _TOP500_CACHE:
        return _TOP500_CACHE[path]
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        papers = raw.get("papers") if isinstance(raw, dict) else raw
        items = [p for p in (papers or []) if isinstance(p, dict)]
        _TOP500_CACHE[path] = items
        return items
    except Exception:
        return []


def match_top_literature(
    problem_class: str = "",
    domain: str = "",
    query: str = "",
    *,
    topk: int = 3,
    home: Path | None = None,
) -> list[dict[str, Any]]:
    """Deterministically rank authoritative papers from or_papers_top500.json."""
    h = _resolve_home(home)
    papers = _load_top500(h)
    if not papers:
        return []

    pc = (problem_class or "").strip().lower()
    dom = (domain or "").strip().lower()
    target_tags: list[str] = []
    for key in (pc, dom):
        for tag in _LIT_DOMAIN_MAP.get(key, ()):
            if tag not in target_tags:
                target_tags.append(tag)
    if not target_tags:
        target_tags = ["integer_programming", "combinatorial_optimization", "linear_programming"]

    q_toks = _tokens(f"{pc} {dom} {query}")
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, p in enumerate(papers):
        p_domains = [str(x).lower() for x in (p.get("domains") or [])]
        sc = 0.0
        for rank_i, t in enumerate(target_tags):
            if t in p_domains:
                sc += 6.0 if rank_i == 0 else 3.0
        title_q = f"{p.get('title') or ''} {p.get('query') or ''} {p.get('venue') or ''}"
        overlap = len(q_toks & _tokens(title_q))
        sc += overlap * 2.5
        sc += min(float(p.get("score") or 0.0) * 0.15, 2.0)
        if sc > 0:
            scored.append((sc, -idx, p))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    out: list[dict[str, Any]] = []
    for sc, _neg_idx, p in scored[: max(1, topk)]:
        authors = p.get("authors") or []
        first_author = str(authors[0]) if authors else "Author"
        cite_label = f"{first_author} et al. ({p.get('year') or 'n.d.'})" if len(authors) > 1 else f"{first_author} ({p.get('year') or 'n.d.'})"
        out.append({
            "cite_label": cite_label,
            "title": str(p.get("title") or ""),
            "year": p.get("year"),
            "venue": str(p.get("venue") or ""),
            "doi": str(p.get("doi") or ""),
            "cited_by_count": p.get("cited_by_count"),
            "score": round(sc, 3),
        })
    return out


def extract_formulation_snippet(
    problem_class: str,
    *,
    home: Path | None = None,
    max_chars: int = 1300,
) -> str:
    """Extract canonical mathematical formulation from knowledge/skills/or-problems.md."""
    h = _resolve_home(home)
    hb = (h / "knowledge" / "skills" / "or-problems.md").resolve()
    if hb in _HANDBOOK_CACHE:
        sections = _HANDBOOK_CACHE[hb]
    elif hb.is_file():
        text = hb.read_text(encoding="utf-8", errors="replace")
        sections = re.split(r"\n(?=###? )", text)
        _HANDBOOK_CACHE[hb] = sections
    else:
        return ""

    pc = (problem_class or "").strip().lower()
    keys = _FORMULATION_KEYS.get(pc) or (pc, "1.2", "整数规划")
    for key in keys:
        kl = key.lower()
        for sec in sections:
            first_line = sec.splitlines()[0].lower() if sec.splitlines() else ""
            if kl and kl in first_line:
                return sec.strip()[:max_chars]
    # Fallback to MIP section 1.2
    for sec in sections:
        first_line = sec.splitlines()[0].lower() if sec.splitlines() else ""
        if "1.2" in first_line or "整数规划" in first_line:
            return sec.strip()[:max_chars]
    return ""


def extract_skill_highlights(
    domain: str = "",
    problem_class: str = "",
    *,
    home: Path | None = None,
    max_chars_per_skill: int = 380,
) -> tuple[list[dict[str, str]], tuple[str, ...], tuple[str, ...]]:
    """Resolve DomainCartridge skills, modeling checklist, and solver allowlist."""
    h = _resolve_home(home)
    skills_dir = h / "knowledge" / "skills"
    skill_topics: tuple[str, ...] = ("or-modeling", "or-numbers-truth")
    checklist: tuple[str, ...] = ()
    solver_modes: tuple[str, ...] = ()

    try:
        from orpath.agents.cartridges import resolve_cartridge

        cart = resolve_cartridge(problem_class or domain or "general_or")
        skill_topics = tuple(cart.skill_topics) or skill_topics
        checklist = tuple(cart.modeling_checklist)
        solver_modes = tuple(cart.solver_modes)
    except Exception:
        pass

    matched: list[dict[str, str]] = []
    seen: set[str] = set()
    for topic in skill_topics:
        t = str(topic).strip()
        if not t or t == "or-problems.md" or t in seen:
            continue
        seen.add(t)
        cand = skills_dir / t / "SKILL.md"
        if not cand.is_file():
            cand = skills_dir / f"{t}.md"
        if not cand.is_file():
            continue
        try:
            body = _strip_frontmatter(cand.read_text(encoding="utf-8", errors="replace"))
            # Collapse blank runs for high density
            compact = re.sub(r"\n{3,}", "\n\n", body)[:max_chars_per_skill]
            matched.append({
                "id": t,
                "path": str(cand.relative_to(h)),
                "excerpt": compact,
            })
        except Exception:
            continue
    return matched, checklist, solver_modes


def load_pinned_knowledge(workdir: Path, slug: str, home: Path | None = None) -> list[dict[str, str]]:
    """Read human-pinned knowledge items from notes/<slug>-human-steer.json (Numbers-Truth safe)."""
    h = _resolve_home(home)
    steer_file = Path(workdir) / "notes" / f"{slug}-human-steer.json"
    if not steer_file.is_file():
        return []
    try:
        doc = json.loads(steer_file.read_text(encoding="utf-8"))
        raw_list = (doc.get("pi") or {}).get("pinned_knowledge") or doc.get("pinned_knowledge") or []
    except Exception:
        return []
    if not isinstance(raw_list, list):
        return []

    forbidden = {"objective", "best_cost", "tour", "routes", "proven_optimal", "global_optimal", "optima", "optimal_value"}
    out: list[dict[str, str]] = []
    for item in raw_list[:10]:
        if not isinstance(item, dict):
            continue
        if any(k.lower() in forbidden for k in item):
            continue
        kid = str(item.get("id") or item.get("chunk_id") or "").strip()
        title = str(item.get("title") or kid).strip()
        kind = str(item.get("kind") or "chunk").strip()
        snippet = str(item.get("snippet") or "").strip()[:300]
        if not snippet and kind == "skill" and kid:
            sk_p = h / "knowledge" / "skills" / kid / "SKILL.md"
            if sk_p.is_file():
                snippet = _strip_frontmatter(sk_p.read_text(encoding="utf-8", errors="replace"))[:300]
        if not snippet and kid:
            try:
                from knowledge_svc.fts_index import FTSIndex

                fts = FTSIndex(root=h)
                hits = fts.search(title or kid, topk=2)
                for fh in hits:
                    if fh.chunk_id == kid or title.lower() in (fh.source_path or "").lower():
                        snippet = fh.snippet[:300]
                        break
                if not snippet and hits:
                    snippet = hits[0].snippet[:300]
            except Exception:
                pass
        if kid or title:
            out.append({"id": kid, "title": title, "kind": kind, "snippet": snippet})
    return out


def _retrieve_fast_or_hybrid(
    query: str,
    problem_class: str,
    home: Path,
    topk: int = 5,
) -> dict[str, Any]:
    """Run hybrid retrieval if vector sidecar/cache is warm; otherwise <15ms FTS+Seed."""
    mode_env = (os.environ.get("ORPATH_KNOWLEDGE_MODE") or "hybrid").strip().lower()
    if mode_env == "off":
        return {"query": query, "knowledge_mode": "off", "hits": [], "seed_facts": []}

    npy_sidecar = home / "knowledge" / "lightrag_ws" / "semantic_stub" / "stub_vectors.npy"
    try:
        if mode_env == "seed" or npy_sidecar.is_file():
            from knowledge_svc.retrieve import artifact_to_payload, retrieve as ks_retrieve

            art = ks_retrieve(
                query,
                mode="seed" if mode_env == "seed" else "hybrid",
                topk=topk,
                root=home,
                problem_class=problem_class or None,
            )
            return artifact_to_payload(art)
    except Exception:
        pass

    # Ultra-fast cold path (<15ms) via SQLite FTS5 + Seed Graph
    hits_dict: list[dict[str, Any]] = []
    seed_facts: list[dict[str, Any]] = []
    try:
        from knowledge_svc.fts_index import FTSIndex

        fts = FTSIndex(root=home)
        for fh in fts.search(query, topk=topk):
            hits_dict.append(fh.to_dict())
    except Exception:
        pass
    try:
        from knowledge_svc.seed_graph_query import query_all_classes, query_by_class

        seed_facts = query_by_class(problem_class) if problem_class else query_all_classes()
    except Exception:
        seed_facts = []
    return {
        "query": query,
        "knowledge_mode": "hybrid_fts_fast",
        "hits": hits_dict,
        "seed_facts": seed_facts,
    }


def _collect_combined_lessons(
    workdir: Path,
    home: Path,
    slug: str,
    query: str,
    problem_class: str,
    topk: int = 3,
) -> tuple[Path, Path, list[dict[str, Any]]]:
    """Retrieve lessons from both install home seeds and case workdir local memory."""
    from orpath.process_memory import lessons_to_markdown, retrieve_lessons

    notes_dir = Path(workdir) / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    jpath = notes_dir / f"{slug}-lessons.json"
    mpath = notes_dir / f"{slug}-lessons.md"

    seen_ids: set[str] = set()
    merged: list[dict[str, Any]] = []
    for root_cand in (Path(workdir), home):
        try:
            for item in retrieve_lessons(query, root=root_cand, problem_class=problem_class or None, topk=topk):
                lid = str(item.get("id") or "")
                if lid and lid not in seen_ids:
                    seen_ids.add(lid)
                    merged.append(item)
        except Exception:
            continue
    merged.sort(key=lambda d: float(d.get("score") or 0.0), reverse=True)
    merged = merged[: max(1, topk)]

    art = {
        "schema": "orpath.lessons_retrieve.v1",
        "query": query,
        "problem_class": problem_class or "",
        "hits": merged,
    }
    jpath.write_text(json.dumps(art, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    mpath.write_text(lessons_to_markdown(merged, query=query), encoding="utf-8")
    return jpath, mpath, merged


def assemble_preflight_knowledge_pack(
    workdir: Path | str,
    slug: str,
    *,
    domain: str = "",
    problem_class: str = "",
    query_hint: str = "",
    home: Path | None = None,
) -> dict[str, Any]:
    """Deterministically assemble notes/<slug>-knowledge-pack.md + retrieval & lesson sidecars."""
    wd = Path(workdir).resolve()
    h = _resolve_home(home)
    notes_dir = wd / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    pc = (problem_class or "").strip().lower()
    dom = (domain or "").strip().lower()
    q_parts = [x.replace("_", " ") for x in (pc, dom) if x and x != "unregistered"]
    if query_hint:
        q_parts.append(re.sub(r"\s+", " ", query_hint).strip()[:120])
    query = " ".join(q_parts).strip() or "operations research mathematical programming formulation"

    # 1. Corpus RAG / FTS + Seed retrieval
    ret_payload = _retrieve_fast_or_hybrid(query, pc, h, topk=5)
    ret_path = notes_dir / f"{slug}-retrieval.json"
    ret_path.write_text(json.dumps(ret_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 2. Process memory lessons (home seeds + local workdir auto-lessons)
    _les_json, les_md, lessons = _collect_combined_lessons(wd, h, slug, query, pc, topk=3)

    # 3. DomainCartridge skills, checklist & or-problems.md canonical formulation
    skills, checklist, solver_modes = extract_skill_highlights(dom, pc, home=h)
    formulation = extract_formulation_snippet(pc, home=h)

    # 4. Authoritative top-journal literature from or_papers_top500.json
    lit_anchors = match_top_literature(pc, dom, query, topk=3, home=h)

    # 5. User-pinned knowledge from human-steer.json
    pinned = load_pinned_knowledge(wd, slug, home=h)

    # 6. Render bounded, high-signal Markdown pack (<= 6 KB)
    lines: list[str] = [
        f"# OR-Path 领域知识简报包 (`{slug}`)",
        "",
        "> 0-Token 确定性前置组装 — 仅提供数学建模范式、防坑约束与真实文献锚点；严禁将方法先验当作算例数值真值（Numbers Truth 归属独立求解器与校验器）。",
        "",
        f"- **识别领域盒 (DomainCartridge)**: `{dom or 'general_or'}` | **问题类别**: `{pc or 'general_or'}`",
    ]
    if solver_modes:
        lines.append(f"- **允许调用的求解算子 (Solver Allowlist)**: `{', '.join(solver_modes)}`")
    if checklist:
        lines.append(f"- **领域核心防坑核对项**: {'；'.join(checklist)}")
    lines.append("")

    if pinned:
        lines.append("## 0. 人工锁定优先注入项 (Pinned Knowledge from Human Steer)")
        for p_item in pinned:
            lines.append(f"- **[{p_item['kind']}] `{p_item['title']}`** (`{p_item['id']}`): {p_item['snippet']}")
        lines.append("")

    if formulation:
        lines.extend([
            "## 1. 标准数学规划范式 (`knowledge/skills/or-problems.md`)",
            "",
            formulation,
            "",
        ])

    if skills:
        lines.append("## 2. 领域技能核心规约 (`DomainCartridge.skill_topics`)")
        for sk in skills[:3]:
            excerpt_one = re.sub(r"\s+", " ", sk["excerpt"]).strip()[:280]
            lines.append(f"- **`{sk['id']}`** (`{sk['path']}`): {excerpt_one}")
        lines.append("")

    hits = ret_payload.get("hits") or []
    if hits:
        lines.append("## 3. 知识库方法切片召回 (RAG Method Hints)")
        for h_item in hits[:5]:
            sp = str(h_item.get("source_path") or "")
            title = Path(sp).stem if sp else str(h_item.get("chunk_id") or "")
            snip = re.sub(r"\s+", " ", str(h_item.get("snippet") or "")).strip()[:200]
            lines.append(f"- **`{title}`** (`chunk_id={h_item.get('chunk_id')}`, `{sp}`): {snip}")
        lines.append("")

    if lessons:
        lines.append("## 4. 历史同类赛题踩坑记忆 (`orpath.lesson.v1`)")
        for les in lessons[:3]:
            pits = "；".join(str(x) for x in (les.get("pitfalls") or [])[:2])
            decs = "；".join(str(x) for x in (les.get("key_decisions") or [])[:2])
            detail = f"决策: {decs}" if decs else str(les.get("summary") or "")[:160]
            if pits:
                detail += f" | 防坑: {pits}"
            lines.append(f"- **`{les.get('id')}`** (`class={les.get('problem_class')}`): {detail}")
        lines.append("")

    if lit_anchors:
        lines.append("## 5. 权威顶刊文献锚点 (`or_papers_top500.json` — 供论文第3/4章与参考文献真实引用)")
        for lit in lit_anchors:
            doi_str = f" DOI:{lit['doi']}" if lit.get("doi") else ""
            lines.append(f"- **{lit['cite_label']}**: *{lit['title']}*, {lit['venue']}.{doi_str}")
        lines.append("")

    pack_path = notes_dir / f"{slug}-knowledge-pack.md"
    pack_path.write_text("\n".join(lines)[:6500] + "\n", encoding="utf-8")

    return {
        "knowledge_pack_path": str(pack_path),
        "retrieval_path": str(ret_path),
        "lessons_path": str(les_md),
        "hits_count": len(hits),
        "matched_skills": [{"id": s["id"], "path": s["path"]} for s in skills],
        "literature_anchors": lit_anchors,
    }


def build_error_remediation_pack(
    workdir: Path | str,
    slug: str,
    *,
    problem_class: str = "",
    validator_errors: list[str] | None = None,
    retry_round: int = 1,
    home: Path | None = None,
) -> dict[str, Any]:
    """Build targeted error-remediation guidance on validator bounce-back (0 LLM)."""
    wd = Path(workdir).resolve()
    h = _resolve_home(home)
    notes_dir = wd / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    errs = [str(e) for e in (validator_errors or []) if str(e).strip()]
    err_blob = " | ".join(errs).lower()
    pc = (problem_class or "").strip().lower()

    matched_recipes: list[str] = []
    search_terms: list[str] = [pc] if pc else []
    for triggers, q_terms, advice in _ERROR_PLAYBOOKS:
        if any(t in err_blob for t in triggers):
            matched_recipes.append(advice)
            search_terms.append(q_terms)

    if not matched_recipes:
        matched_recipes.append(
            "逐条核对 validator_errors 指出的失败项：确保输出 JSON 结构符合 contracts/solution.json，"
            "且所有目标值与资源分配均由原始输入数据严格算得、满足全部硬约束。"
        )
        search_terms.append("milp formulation tips cpsat modeling validate recompute")

    remediation_query = " ".join(search_terms + errs[:2])[:200]
    rag_payload = _retrieve_fast_or_hybrid(remediation_query, pc, h, topk=3)
    rag_hits = rag_payload.get("hits") or []

    from orpath.process_memory import retrieve_lessons

    lesson_hits = retrieve_lessons(remediation_query, root=wd, problem_class=pc or None, topk=2)
    if len(lesson_hits) < 2:
        for lh in retrieve_lessons(remediation_query, root=h, problem_class=pc or None, topk=2):
            if all(lh.get("id") != x.get("id") for x in lesson_hits):
                lesson_hits.append(lh)

    lines = [
        f"# 校验失败靶向修复包 (`{slug}` · 第 {retry_round} 轮回弹)",
        "",
        "## 1. 独立验证器拦截错误 (`validator_errors`)",
    ]
    for e in errs[:6]:
        lines.append(f"- ❌ `{e[:260]}`")
    lines.extend(["", "## 2. 针对性数学与工程修复处方 (Targeted Remediation)"])
    for rec in matched_recipes:
        lines.append(f"- 🔧 {rec}")

    if rag_hits:
        lines.extend(["", "## 3. 知识库关联建模模式切片"])
        for rh in rag_hits[:3]:
            sp = str(rh.get("source_path") or "")
            title = Path(sp).stem if sp else str(rh.get("chunk_id") or "")
            snip = re.sub(r"\s+", " ", str(rh.get("snippet") or "")).strip()[:220]
            lines.append(f"- 📄 **`{title}`** (`{sp}`): {snip}")

    if lesson_hits:
        lines.extend(["", "## 4. 历史同类踩坑记录 (`lessons`)"])
        for lh in lesson_hits[:2]:
            pits = "；".join(str(p) for p in (lh.get("pitfalls") or [])[:2])
            lines.append(f"- 🧠 **`{lh.get('id')}`**: {lh.get('summary', '')} {('— 坑点: ' + pits) if pits else ''}")

    rem_path = notes_dir / f"{slug}-remediation.md"
    rem_path.write_text("\n".join(lines)[:4500] + "\n", encoding="utf-8")
    return {
        "remediation_path": str(rem_path),
        "remediation_summary": matched_recipes[0][:240],
    }
