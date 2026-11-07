#!/usr/bin/env python3
"""Deterministic pre/post nodes of the OR-Path lean 4-elite pipeline (Plan 1.4).

The retired LLM "Lead" (transfer-to-* polling supervisor) and LLM "Verifier"
roles are downgraded to **pure Python nodes** with **zero LLM token
consumption**:

  * ``run_preflight_probe(state)``      — front probe: scan ``inbox/<slug>/``
    (or the case directory), compute SHA-256 fingerprints of raw input files,
    extract row/column scales and field overviews from CSV / Excel / JSON,
    auto-run the DomainCartridge profiler (``profile_<domain>_data``) when the
    domain is given or can be deterministically guessed, and persist the
    profile to ``outputs/<slug>-profile.json``;
  * ``run_deterministic_validator(state)`` — hard back gate: recompute every
    objective / schedule / route / cutting plan from raw problem data through
    ``tools.validate_solution`` (the engine behind ``tools.solve_dispatch
    .validate``), plus DomainCartridge ``inspect_<domain>_solution`` physical
    conservation / capacity / precedence checks, then extract ``ok``,
    ``recomputed_objective``, ``proven_optimal`` and the concrete ``errors``
    list into the pipeline state.

Design contracts (Plan 1.4 acceptance):

  * a single front-probe / back-gate run takes ``< 0.5 s`` for lightweight
    problems (heavy simulation-backed XXL validations are explicitly out of
    scope — the module never launches simulators);
  * **LLM token consumption is exactly 0** — this module deliberately does not
    import ``langchain`` / ``langgraph`` / any chat model; agent LLM calls are
    owned exclusively by ``orpath.agents.workers`` and
    ``orpath.agents.adaptive_graph``.

Every failure is reported through state fields (``last_error``,
``preflight_ok`` / ``validation_ok``) rather than raised, so the graph keeps a
single control plane.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping

# Repo root: <root>/orpath/agents/deterministic_nodes.py
_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Suffixes treated as "parseable input payloads" by the front probe.
DATA_SUFFIXES = {
    ".csv", ".tsv", ".txt", ".md", ".json", ".jsonl", ".xlsx", ".xls",
    ".dat", ".xml", ".py",
}
#: Directories never scanned inside a case folder (harness state, not inputs).
_SKIP_DIRS = {"outputs", "notes", "papers", "runs", "__pycache__", ".git", "tools"}
#: Files larger than this are fingerprinted but not parsed (heavy-simulation
#: boundary of the 0.5s acceptance budget).
_MAX_PARSE_BYTES = 64 * 1024 * 1024

#: Domain keyword table — deterministic filename/text domain guess (mirrors
#: ``scripts/guess_intake_domain.py`` but extended to all 10 cartridges).
DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "routing": ("vrp", "cvrp", "vrptw", "pdptw", "routing", "vehicle", "solomon", "配送", "车辆", "路径"),
    "scheduling": ("jssp", "fjssp", "jobshop", "job_shop", "scheduling", "taillard", "调度", "排产", "gantt", "工序"),
    "rostering": ("rostering", "shift", "staff", "排班", "值班"),
    "inventory": ("inventory", "lot_sizing", "lotsizing", "wagner", "库存", "订货", "eoq"),
    "facility": ("facility", "cflp", "flp", "选址", "cap41", "cap61", "warehouse"),
    "pricing": ("stochastic", "pricing", "farmer", "two_stage", "two-stage", "随机", "定价", "两阶段"),
    "project": ("rcpsp", "psplib", "project_scheduling", "工期", "cumulative", "j30", "j60"),
    "portfolio": ("portfolio", "markowitz", "risk_parity", "投资组合", "资产配置"),
    "microgrid": ("microgrid", "micro_grid", "smart_grid", "photovoltaic", "pv", "储能", "光伏", "电网", "battery", "soc", "dispatch"),
    "tube": ("tube", "圆管", "cutting", "bfd", "cutting_stock", "余料"),
    "polyomino": ("polyomino", "tiling", "骨牌", "多联", "覆盖", "铺放"),
}

#: problem_class keyword guess (canonical names only, via domain registry).
CLASS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "shortest_path": ("shortest", "最短路", "dijkstra", "dial"),
    "network_flow": ("max_flow", "maxflow", "最大流", "min_cost_flow", "flow"),
    "tsp": ("tsp", "旅行商"),
    "vrp": ("cvrp", "vrp", "车辆路径"),
    "pyvrp": ("pyvrp", "vrptw", "vrp_tw"),
    "jssp": ("jssp", "fjssp", "job_shop", "jobshop", "作业车间"),
    "rcpsp": ("rcpsp", "project_scheduling", "psplib"),
    "staff_rostering": ("rostering", "排班"),
    "bin_packing": ("binpack", "bin_packing", "装箱"),
    "facility_location": ("cflp", "facility", "选址"),
    "hub_location": ("hub", "p-hub"),
    "portfolio_opt": ("portfolio", "markowitz", "投资组合"),
    "lot_sizing": ("lot_sizing", "lotsizing", "wagner", "库存"),
    "stochastic_lp": ("stochastic_lp", "two_stage", "两阶段随机"),
    "qubo_ising": ("qubo", "ising", "max_cut", "maxcut"),
    "game_theory": ("bimatrix", "nash", "博弈"),
    "tube_cut": ("tube", "圆管", "cutting"),
    "polyomino_cover": ("polyomino", "骨牌", "tiling"),
    "microgrid_dispatch": ("microgrid", "微网", "储能"),
}

__all__ = [
    "run_preflight_probe",
    "run_deterministic_validator",
    "validate_artifact",
    "guess_domain",
    "guess_problem_class",
    "collect_input_files",
    "file_overview",
    "file_sha256",
    "domain_tool_registry",
    "DOMAIN_KEYWORDS",
]


# --------------------------------------------------------------------------- #
# Import seams (no LLM deps on purpose)
# --------------------------------------------------------------------------- #
def _import_tools() -> Path:
    """Insert ``tools/`` and repo root onto ``sys.path`` for solver seams."""
    for p in (_REPO_ROOT / "tools", _REPO_ROOT):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
    return _REPO_ROOT


def domain_tool_registry() -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``({domain: profile_<domain>_data tool}, {domain: inspect_<domain>_solution tool})``.

    Built lazily from ``orpath.agents.domain_analytics`` (import-safe offline).
    Domains without registered tools (e.g. microgrid / tube / polyomino) simply
    do not appear in these maps — their physical checks run through the
    ``tools/validators/`` engine invoked by ``validate_artifact`` instead.
    """
    profilers: dict[str, Any] = {}
    inspectors: dict[str, Any] = {}
    try:
        from orpath.agents import domain_analytics as _da  # noqa: PLC0415
    except Exception:  # pragma: no cover - never mask downstream failures
        return profilers, inspectors
    for name in dir(_da):
        try:
            obj = getattr(_da, name)
        except Exception:
            continue
        if name.startswith("profile_") and name.endswith("_data") and callable(getattr(obj, "invoke", None)):
            profilers[name[len("profile_"):-len("_data")]] = obj
        elif name.startswith("inspect_") and name.endswith("_solution") and callable(getattr(obj, "invoke", None)):
            inspectors[name[len("inspect_"):-len("_solution")]] = obj
    return profilers, inspectors


# --------------------------------------------------------------------------- #
# Generic file fingerprinting / overview
# --------------------------------------------------------------------------- #
def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_workdir(state: Mapping[str, Any]) -> Path:
    raw = (state.get("workdir") or "").strip()
    if not raw:
        raw = os.environ.get("ORPATH_WORKDIR") or ""
    if raw:
        try:
            return Path(raw).expanduser().resolve()
        except OSError:
            return Path(raw).expanduser()
    return Path.cwd()


def collect_input_files(root: Path, slug: str = "", extra: Any = None) -> tuple[list[Path], list[str]]:
    """Collect raw input files from ``inbox/<slug>/`` (or the case dir).

    Priority: ``root/inbox/<slug>/**`` when present, else the case directory
    itself; explicit ``state["data_files"]`` / ``problem_file`` entries are
    appended when they exist. Harness directories and >64MB binaries are
    skipped (but reported via the ``notes`` list).
    """
    notes: list[str] = []
    seen: dict[Path, None] = {}

    def _add(p: Path) -> None:
        rp = p.resolve()
        if rp not in seen and p.is_file():
            seen[rp] = None

    inbox = root / "inbox"
    if slug:
        case_dir = inbox / slug
        if not case_dir.is_dir():
            case_dir = root / slug
    else:
        case_dir = inbox if inbox.is_dir() else root

    if case_dir.is_dir():
        for p in sorted(case_dir.rglob("*")):
            if p.is_dir() or any(part in _SKIP_DIRS for part in p.relative_to(case_dir).parts[:-1]):
                continue
            if p.stat().st_size > _MAX_PARSE_BYTES:
                notes.append(f"skipped heavy file: {p}")
                continue
            _add(p)
    for extra_raw in extra or []:
        if isinstance(extra_raw, str) and extra_raw:
            _add(Path(extra_raw).expanduser() if Path(extra_raw).is_absolute() else root / extra_raw)
    files = list(seen.keys())
    return files, notes


def _overview_csv(path: Path) -> dict[str, Any]:
    delim = "\t" if path.suffix.lower() in {".tsv"} else ","
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh, delimiter=delim)
        try:
            header = next(reader, [])
        except Exception:
            return {"format": "csv", "rows": 0, "cols": 0, "fields": [], "error": "unreadable"}
        rows = 1
        preview: list[list[str]] = []
        for row in reader:
            if row:
                rows += 1
                if len(preview) < 3:
                    preview.append([str(c)[:40] for c in row[:12]])
    truncated_cols = len(header) > 50
    fields = [str(h).strip() for h in header[:50]]
    return {
        "format": "csv",
        "rows": rows,
        "cols": len(header),
        "fields": fields,
        "header": fields if len(header) <= 60 else fields + ["..."],
        "cols_truncated": truncated_cols,
        "preview_rows": preview,
    }


def _overview_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {"format": "json", "rows": 0, "cols": 0, "error": f"{type(exc).__name__}: {exc}"}
    if isinstance(data, list):
        first = data[0] if data else None
        return {
            "format": "json",
            "rows": len(data),
            "cols": len(first) if isinstance(first, dict) else 0,
            "element_type": type(first).__name__ if first is not None else "null",
            "fields": list(first)[:50] if isinstance(first, dict) else [],
            "top_level": "list",
        }
    if isinstance(data, dict):
        scal_types = sorted({type(v).__name__ for v in data.values()})
        return {
            "format": "json",
            "top_level": "dict",
            "rows": len(data),
            "cols": len(data),
            "fields": list(data)[:50],
            "value_types": scal_types,
        }
    return {"format": "json", "top_level": type(data).__name__, "rows": 1, "cols": 0}


def _overview_xlsx(path: Path) -> dict[str, Any]:
    try:
        import openpyxl  # imported lazily — only needed when a workbook is present
    except ImportError:
        return {"format": "xlsx", "error": "openpyxl not available"}
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        return {"format": "xlsx", "error": f"{type(exc).__name__}: {exc}"}
    sheets: dict[str, dict[str, Any]] = {}
    total_rows = 0
    try:
        for ws in wb.worksheets:
            rows = 0
            header: list[str] = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i == 0:
                    header = [str(c) if c is not None else "" for c in row][:50]
                if any(c is not None for c in row):
                    rows += 1
                if i > 100000:
                    break
            sheets[ws.title] = {"rows": rows, "fields": header}
            total_rows += rows
    finally:
        wb.close()
    return {"format": "xlsx", "sheets": sheets, "rows": total_rows, "cols": max((len(s["fields"]) for s in sheets.values()), default=0)}


def file_overview(path: Path) -> dict[str, Any]:
    """Row/column scale + field overview for one input file (never raises)."""
    suffix = path.suffix.lower()
    try:
        size = path.stat().st_size
    except OSError as exc:
        return {"format": suffix.lstrip(".") or "bin", "error": str(exc)}
    if suffix in {".csv", ".tsv"}:
        out = _overview_csv(path)
    elif suffix in {".json", ".jsonl"}:
        out = _overview_json(path)
    elif suffix in {".xlsx", ".xlsm"}:
        out = _overview_xlsx(path)
    elif suffix in {".xls"}:
        return {"format": "xls", "bytes": size, "note": "legacy xls — row scale unknown without xlrd"}
    elif suffix in {".md", ".txt", ".py", ".xml", ".dat"}:
        text = path.read_text(encoding="utf-8", errors="replace")[:200000]
        out = {"format": suffix.lstrip("."), "rows": len(text.splitlines()), "bytes": size}
    else:
        out = {"format": suffix.lstrip(".") or "bin", "bytes": size}
    out["bytes"] = out.get("bytes", size) or size
    out["sha256"] = file_sha256(path)
    return out


# --------------------------------------------------------------------------- #
# Deterministic domain / class guessing
# --------------------------------------------------------------------------- #
def guess_domain(*texts: str) -> str:
    """Keyword-based domain guess over filenames / briefs (first hit wins)."""
    blob = " ".join(t or "" for t in texts).lower()
    for domain, keys in DOMAIN_KEYWORDS.items():
        if any(k.lower() in blob for k in keys):
            return domain
    return ""


def guess_problem_class(*texts: str) -> str:
    """Canonical problem_class guess, validated through the domain registry."""
    blob = " ".join(t or "" for t in texts).lower()
    try:
        from orpath.domain_registry import is_known_class, normalize_problem_class
    except Exception:
        def is_known_class(raw: str | None) -> bool:
            return bool(raw)

        def normalize_problem_class(raw: str | None) -> str:
            return str(raw or "")
    for cls, keys in CLASS_KEYWORDS.items():
        if any(k.lower() in blob for k in keys):
            norm = normalize_problem_class(cls)
            if is_known_class(norm) and norm:
                return norm
    return ""


# --------------------------------------------------------------------------- #
# Plan 1.4 node 1 — front probe
# --------------------------------------------------------------------------- #
def run_preflight_probe(state: Mapping[str, Any]) -> dict[str, Any]:
    """Front probe: fingerprint + size/field profile of raw inputs (0 LLM).

    Side effects: writes ``outputs/<slug>-profile.json`` and returns
    pointer-only state updates (``profile_path``, ``data_files``,
    ``preflight_ok``, ``preflight_summary``, deterministic ``problem_class`` /
    ``domain_cartridge`` guesses when absent in the incoming state).
    """
    t0 = time.perf_counter()
    try:
        return _preflight(state, t0)
    except Exception as exc:  # noqa: BLE001 - single control plane: never raise
        return {
            "preflight_ok": False,
            "preflight_summary": "preflight failed",
            "last_error": f"preflight failed: {type(exc).__name__}: {exc}",
        }


def _preflight(state: Mapping[str, Any], t0: float) -> dict[str, Any]:
    root = _resolve_workdir(state)
    slug = str(state.get("slug") or "").strip() or root.name
    _import_tools()

    if not root.is_dir():
        raise ValueError(f"workdir does not exist: {root}")

    files, notes = collect_input_files(root, slug, state.get("data_files"))
    if state.get("problem_file"):
        pf = Path(state["problem_file"])
        if not pf.is_absolute():
            pf = root / pf
        if pf.is_file():
            files = [pf] + [f for f in files if f != pf]

    manifest: list[dict[str, Any]] = []
    for p in files:
        overview = file_overview(p)
        rel = os.path.relpath(p, root)
        try:
            rel = rel.replace(os.sep, "/")
        except Exception:
            rel = str(p)
        item = {"file": rel, "abs_path": str(p)}
        item.update({k: v for k, v in overview.items() if k != "abs_path"})
        manifest.append(item)

    blobs = [str(state.get("problem_text") or "")[:2000]]
    if not blobs[0]:
        blobs[0] = root.name
    for item in manifest:
        blobs.append(item.get("file", ""))
    stem = Path(root.name).name

    explicit_domain = str(state.get("domain_cartridge") or "").strip()
    guessed_domain = guess_domain(*([explicit_domain] if explicit_domain else []) + [stem] + blobs[1:])
    domain = explicit_domain or guessed_domain

    explicit_cls = str(state.get("problem_class") or "").strip()
    guessed_cls = guess_problem_class(*([explicit_cls] if explicit_cls else []) + [stem] + blobs[1:])
    problem_class = explicit_cls or guessed_cls

    # Extract compact statement snippet for fallback classification & zero-LLM knowledge pack
    stmt_hint = str(state.get("problem_text") or "")[:300]
    if not stmt_hint:
        for p in files:
            if p.suffix.lower() in {".md", ".txt"}:
                try:
                    stmt_hint = p.read_text(encoding="utf-8", errors="replace")[:300]
                    break
                except OSError:
                    continue
    if not domain and stmt_hint:
        guessed_domain = guess_domain(stmt_hint)
        domain = guessed_domain
    if not problem_class and stmt_hint:
        guessed_cls = guess_problem_class(stmt_hint)
        problem_class = guessed_cls

    total_bytes = sum(int(m.get("bytes") or 0) for m in manifest)

    domain_profile: dict[str, Any] | None = None
    profilers, _inspectors = domain_tool_registry()
    if domain in profilers:
        try:
            raw = profilers[domain].invoke({})
            try:
                parsed = json.loads(raw)
                domain_profile = parsed if isinstance(parsed, dict) else {"raw": raw}
            except Exception:
                domain_profile = {"raw": str(raw)[:4000]}
        except TypeError:
            try:
                raw = profilers[domain].invoke({})
                domain_profile = {"raw": str(raw)[:4000]}
            except Exception as exc:  # noqa: BLE001
                domain_profile = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        except Exception as exc:  # noqa: BLE001
            domain_profile = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    if not files:
        raise ValueError("no input files found under the case directory / inbox")

    # Assemble deterministic zero-LLM Knowledge Pack (notes/<slug>-knowledge-pack.md)
    kp_info: dict[str, Any] = {}
    try:
        from orpath.agents import knowledge_pack as _kp  # noqa: PLC0415

        kp_info = _kp.assemble_preflight_knowledge_pack(
            root,
            slug,
            domain=domain,
            problem_class=problem_class,
            query_hint=stmt_hint,
        )
    except Exception as exc:  # noqa: BLE001 - never fail preflight if RAG degrades
        kp_info = {"error": f"{type(exc).__name__}: {exc}"}

    profile: dict[str, Any] = {
        "slug": slug,
        "generated_by": "orpath.agents.deterministic_nodes.run_preflight_probe",
        "root": str(root),
        "input_files": manifest,
        "notes": notes,
        "summary": {
            "num_files": len(manifest),
            "total_bytes": total_bytes,
            "guessed_domain": guessed_domain,
            "active_domain": domain,
            "guessed_problem_class": guessed_cls,
        },
        "domain_profile": domain_profile,
        "knowledge": {
            k: kp_info.get(k)
            for k in ("knowledge_pack_path", "retrieval_path", "lessons_path", "hits_count", "matched_skills", "literature_anchors")
            if k in kp_info
        },
    }
    (root / "outputs").mkdir(parents=True, exist_ok=True)
    profile_path = root / "outputs" / f"{slug}-profile.json"
    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    took = time.perf_counter() - t0
    sha_head = [f"{m['file']}={m['sha256'][:12]}" for m in manifest[:3]]
    summary = (
        f"files={len(manifest)} bytes={total_bytes} domain={domain or None} "
        f"class={problem_class or None} sha={';'.join(sha_head)}took={took:.3f}s"
    )
    out_state: dict[str, Any] = {
        "slug": slug,
        "workdir": str(root),
        "profile_path": str(profile_path),
        "data_files": [m["file"] for m in manifest][:512],
        "problem_class": problem_class,
        "domain_cartridge": domain,
        "preflight_ok": True,
        "preflight_summary": summary[:4000],
        "last_error": "",
    }
    for ptr_key in ("knowledge_pack_path", "retrieval_path", "lessons_path"):
        if kp_info.get(ptr_key):
            out_state[ptr_key] = str(kp_info[ptr_key])
    return out_state


# --------------------------------------------------------------------------- #
# Plan 1.4 node 2 — hard back-gate validator
# --------------------------------------------------------------------------- #
def validate_artifact(
    root: Path,
    problem_id: str,
    solution_path: Path,
    out: Path | None = None,
    *,
    in_process: bool = True,
) -> tuple[bool, dict[str, Any], str]:
    """Validate one solution artifact (the single numeric-truth engine).

    Primary path: in-process ``tools/validate_solution.validate`` — the exact
    engine backing ``tools.solve_dispatch.validate`` (same gold resolution and
    check set, no interpreter-spawn overhead, <0.5s for lightweight cases).
    Fallback: the ``tools.solve_dispatch.validate`` subprocess seam (ADR-0002).
    """
    root = Path(root)
    solution_path = Path(solution_path)
    out = Path(out) if out is not None else root / "outputs" / "validation.json"
    if in_process:
        try:
            data, raw = _validate_in_process(root, problem_id, solution_path)
            if out.parent:
                out.parent.mkdir(parents=True, exist_ok=True)
                if not out.is_file():
                    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return bool(data.get("ok")), data, raw
        except Exception as exc:  # noqa: BLE001 - fall back to the dispatch seam
            err = f"in-process validate failed ({type(exc).__name__}: {exc})"
    else:
        err = "in-process validation disabled"

    from tools import solve_dispatch  # noqa: PLC0415 (guarded import)
    code_ok, data, raw = solve_dispatch.validate(root, problem_id, solution_path, out)
    if not (code_ok and data.get("ok")) and err:
        raw = (raw + "\n" + err).strip()
    return bool(data.get("ok")), data, raw


def _validate_in_process(root: Path, problem_id: str, solution_path: Path) -> tuple[dict[str, Any], str]:
    _import_tools()
    import json as _json

    from validate_solution import fixture_file as vs_fixture_file  # noqa: PLC0415
    from validate_solution import validate as vs_validate  # noqa: PLC0415

    sol = _json.loads(Path(solution_path).read_text(encoding="utf-8"))
    gold = None
    try:
        gold_path = vs_fixture_file(problem_id, "solution.json")
        if gold_path and Path(gold_path).is_file():
            gold = _json.loads(Path(gold_path).read_text(encoding="utf-8"))
    except Exception:
        gold = None
    report = vs_validate(problem_id, sol, gold, solution_path=Path(solution_path))
    return report, _json.dumps(report, ensure_ascii=False, indent=2)


def _extract_verdict(sol: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Pull ``ok`` / ``recomputed_objective`` / ``proven_optimal`` / ``errors``."""
    ok = bool(data.get("ok"))
    errors = [str(e) for e in (data.get("errors") or [])]
    meta = sol.get("meta") if isinstance(sol.get("meta"), dict) else {}
    prov = meta.get("proven_optimal")
    if not isinstance(prov, bool):
        prov = sol.get("proven_optimal")
    if not isinstance(prov, bool):
        meth = sol.get("method") if isinstance(sol.get("method"), dict) else {}
        prov_flag = meth.get("proven_optimal") if isinstance(meth, dict) else None
        prov = prov_flag if isinstance(prov_flag, bool) else None
    if prov is None:
        # Never assume proven optimal from status alone if method indicates heuristic
        m_cls = str(meta.get("method_class") or "").lower()
        if m_cls in ("heuristic", "metaheuristic", "simulation"):
            prov = False
        else:
            prov = str(sol.get("status") or "").upper() == "OPTIMAL"
    prov = bool(prov)

    recomputed: float | None = None
    for check in data.get("checks") or []:
        if not isinstance(check, dict):
            continue
        if check.get("name") == "recompute_objective" and check.get("expected") is not None:
            try:
                recomputed = float(check["expected"])
                break
            except (TypeError, ValueError):
                continue
    if recomputed is None:
        for check in data.get("checks") or []:
            if not isinstance(check, dict):
                continue
            name = str(check.get("name") or "").lower()
            if "objective" in name and check.get("expected") is not None:
                try:
                    recomputed = float(check["expected"])
                    break
                except (TypeError, ValueError):
                    continue

    decl: float | None = None
    try:
        if sol.get("objective") is not None:
            decl = float(sol["objective"])
    except (TypeError, ValueError):
        decl = None
    if recomputed is None:
        recomputed = decl if ok else None

    gap: float | None = None
    checks = data.get("checks") or []
    for check in checks:
        if isinstance(check, dict) and check.get("name") == "gold_gap":
            try:
                gap = abs(float(check.get("got")) - float(check.get("expected")))
                break
            except (TypeError, ValueError):
                gap = None
    return {
        "validation_ok": ok,
        "proven_optimal": prov,
        "objective_value": decl,
        "recomputed_objective": recomputed,
        "optimality_gap": gap,
        "validator_errors": errors,
    }


def run_deterministic_validator(state: Mapping[str, Any]) -> dict[str, Any]:
    """Hard back gate: recompute truth from raw data (0 LLM tokens).

    Validates ``state["solution_path"]`` through the deterministic engine,
    then runs the DomainCartridge ``inspect_<domain>_solution`` conservation /
    capacity / precedence audit (kept offline-safe; failures degrade to
    ``validator_errors`` annotations instead of raising).
    """
    t0 = time.perf_counter()
    root = _resolve_workdir(state)
    slug = str(state.get("slug") or "").strip() or root.name
    solution_raw = state.get("solution_path") or ""
    if not solution_raw:
        return {
            "validation_ok": False,
            "proven_optimal": False,
            "objective_value": None,
            "validator_errors": ["missing solution_path"],
            "last_error": "missing solution_path",
        }
    solution_path = Path(solution_raw).expanduser()
    if not solution_path.is_absolute():
        solution_path = root / solution_path
    if not solution_path.is_file():
        return {
            "validation_ok": False,
            "proven_optimal": False,
            "objective_value": None,
            "validator_errors": [f"solution not found: {solution_path}"],
            "last_error": f"solution not found: {solution_path}",
        }
    _import_tools()

    problem_id = str(state.get("problem_id") or "").strip() or slug
    out = root / "outputs" / f"{slug}-validation.json"
    try:
        ok, data, raw = validate_artifact(root, problem_id, solution_path, out)
    except Exception as exc:  # noqa: BLE001 - single control plane
        return {
            "validation_ok": False,
            "proven_optimal": False,
            "objective_value": None,
            "validator_errors": [f"{type(exc).__name__}: {exc}"],
            "last_error": f"validator crashed: {type(exc).__name__}: {exc}",
        }

    # Domain physical / capacity / precedence audit (cartridge inspect tool).
    domain = str(state.get("domain_cartridge") or "").strip()
    _profilers, inspectors = domain_tool_registry()
    domain_audit: dict[str, Any] | None = None
    if domain in inspectors:
        try:
            raw_insp = inspectors[domain].invoke({"solution_path": str(solution_path)})
            try:
                pay = json.loads(raw_insp)
            except Exception:
                pay = {"raw": str(raw_insp)[:4000]}
            domain_audit = pay if isinstance(pay, dict) else {"raw": pay}
            if domain_audit.get("ok") is False:
                for err in domain_audit.get("errors") or domain_audit.get("error") or []:
                    data.setdefault("errors", []).append(f"domain:{domain}:{err}")
        except Exception as exc:  # noqa: BLE001
            domain_audit = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            data.setdefault("errors", []).append(f"domain:{domain}:inspect crashed")

    sol: dict[str, Any] = {}
    try:
        sol = json.loads(solution_path.read_text(encoding="utf-8"))
    except Exception:
        sol = {}
    verdict = _extract_verdict(sol, data)
    pc_eff = str(state.get("problem_class") or sol.get("problem_class") or "").strip()

    if verdict["validation_ok"]:
        verdict["remediation_path"] = ""
        try:
            from orpath import process_memory as _pm  # noqa: PLC0415

            _pm.auto_draft_after_validate(
                root,
                {
                    **dict(state),
                    "slug": slug,
                    "problem_class": pc_eff or "general_or",
                    "domain_cartridge": domain,
                    "validate_path": str(out),
                    "solve_mode": str(sol.get("solver") or state.get("solve_mode") or "solver"),
                },
                gate_ok=True,
            )
        except Exception:  # noqa: BLE001 - never fail validator on memory write
            pass
    else:
        try:
            from orpath.agents import knowledge_pack as _kp  # noqa: PLC0415

            rem_info = _kp.build_error_remediation_pack(
                root,
                slug,
                problem_class=pc_eff,
                validator_errors=verdict["validator_errors"],
                retry_round=int(state.get("model_retry_count") or 0) + 1,
            )
            verdict["remediation_path"] = str(rem_info.get("remediation_path") or "")
        except Exception:  # noqa: BLE001
            verdict["remediation_path"] = ""

    took = time.perf_counter() - t0
    verdict["validator_took_sec"] = round(took, 4)
    verdict["validate_path"] = str(out)
    verdict["domain_audit"] = domain_audit
    verdict["last_error"] = "; ".join(verdict["validator_errors"][:5])
    return verdict


if __name__ == "__main__":  # pragma: no cover - manual smoke
    print(json.dumps({"nodes": [n for n in (__all__ if isinstance(__all__, list) else [])]}, ensure_ascii=False))
