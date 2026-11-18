"""Deep Mode Multi-Round Experiment Ledger, Incumbent Ratchet & Safe Fenced-Code Extractor.

Tracks every autonomous sandbox round (up to max_rounds=10, script cap=600s), enforces
a monotonic Numbers-Truth incumbent ratchet (``best_solver.py`` & ``best_solution.json``),
and extracts Fenced Markdown Python blocks with AST syntax pre-checking so models like
Spark never stall serializing long escaped code inside JSON tool calls.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

MAX_DEEP_ROUNDS = 10
MAX_SCRIPT_TIMEOUT_SEC = 600
VALID_TARGET_PRESETS = (3, 5, 8)
_ALLOWED_REL_PREFIXES = ("outputs/", "custom_solvers/", "notes/")

_FENCED_PY_RE = re.compile(
    r"```(?:python|py)\s*(?:\r?\n)(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_FILE_HEADER_RE = re.compile(
    r"^\s*#\s*(?:file|path|target)\s*:\s*([^\s\r\n]+)",
    re.IGNORECASE,
)

STAGE_PLAYBOOK: dict[int, tuple[str, str]] = {
    1: (
        "R1_BASELINE_AND_VERIFIER",
        "建立端到端可校验基线：先写简洁可读的模型脚本（优先导入 tools.or_kernels）与独立纯 Python 验证器（*-custom-validate.py，严禁导入优化器），跑通首个 validation_ok=True 可行解并建立物理校验真值。",
    ),
    2: (
        "R2_VECTORIZE_AND_BOUNDS",
        "性能剖析与向量化收界：基于上一轮耗时与日志，用 edit_file 增量补丁将瓶颈循环改为 NumPy 向量化网格/广播、数学推导收紧变量上下界并加密采样扫描，严禁重写整个文件。",
    ),
    3: (
        "R3_MATHEMATICAL_REFORMULATION",
        "数学结构重构：审视变量耦合与对称性，尝试离散/连续两阶段解耦（solve_minlp_decomposed 或 CP-SAT + SLSQP）、破对称约束（如时间递增 t1 < t2 < ...）或区间精确并集重表述，消除局部零梯度平台。",
    ),
    4: (
        "R4_GLOBAL_PLUS_LNS_HYBRID",
        "全局+大邻域混合攻坚：从当前 best_solution 注入热启动初始点（initial_points / AddHint），组合 Differential Evolution / Dual Annealing + LNS 局部破坏重修（run_lns_loop / select_max_union_subset / --lns-window），跳出局部极值。",
    ),
    5: (
        "R5_INTENSIFICATION_AND_AUDIT",
        "热启动高压收敛与 Gap 收口：基于 best_solver.py 局部增量调大搜索预算（最高可用到 600s/轮），针对薄弱子问题或高残差约束做多起点 SLSQP/L-BFGS-B 精细抛光，确认灵敏度与可行域边界。",
    ),
}


def get_stage_directive(round_idx: int) -> tuple[str, str]:
    """Return ``(stage_code, concise_instruction)`` for round index (1..10)."""
    r = max(1, int(round_idx))
    if r <= 5:
        return STAGE_PLAYBOOK[r]
    return (
        f"R{r}_DEEP_INTENSIFICATION",
        f"第 {r} 轮深度延展收敛：基于当前最优快照 best_solver.py，仅针对上一轮实验账本中仍有改进空间的子问题/Gap 区域做微创增量补丁（edit_file），追加高密度局部精修或邻域搜索（单轮上限 600s）。",
    )


def round_timeout_budget(round_idx: int, *, max_cap: int = MAX_SCRIPT_TIMEOUT_SEC) -> int:
    """Progressive per-round script timeout schedule capped at ``600s``."""
    r = max(1, int(round_idx))
    cap = min(MAX_SCRIPT_TIMEOUT_SEC, max(30, int(max_cap)))
    schedule = {1: 90, 2: 180, 3: 300, 4: 450}
    return min(cap, schedule.get(r, MAX_SCRIPT_TIMEOUT_SEC))


def normalize_target_rounds(raw: Any, *, default: int = 5) -> int:
    """Normalize requested Deep target rounds (clamped cleanly within 1..MAX_DEEP_ROUNDS)."""
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(MAX_DEEP_ROUNDS, val))


def ledger_path(workdir: Path | str, slug: str) -> Path:
    return Path(workdir) / "notes" / f"{slug}-experiments.json"


def best_solver_path(workdir: Path | str, slug: str) -> Path:
    return Path(workdir) / "outputs" / f"{slug}-best_solver.py"


def best_solution_path(workdir: Path | str, slug: str) -> Path:
    return Path(workdir) / "outputs" / f"{slug}-best_solution.json"


def load_ledger(
    workdir: Path | str,
    slug: str,
    *,
    minimize: bool = True,
    target_rounds: int = 5,
    max_rounds: int = MAX_DEEP_ROUNDS,
) -> dict[str, Any]:
    """Load existing evolution ledger or initialize a fresh structure."""
    lp = ledger_path(workdir, slug)
    if lp.is_file():
        try:
            doc = json.loads(lp.read_text(encoding="utf-8"))
            if isinstance(doc, dict) and isinstance(doc.get("rounds"), list):
                return doc
        except (OSError, json.JSONDecodeError):
            pass
    t_r = normalize_target_rounds(target_rounds, default=5)
    m_r = max(t_r, min(MAX_DEEP_ROUNDS, int(max_rounds)))
    return {
        "schema": "orpath.evolution_ledger.v1",
        "slug": slug,
        "minimize": bool(minimize),
        "target_rounds": t_r,
        "max_rounds": m_r,
        "incumbent": None,
        "rounds": [],
    }


def save_ledger(workdir: Path | str, slug: str, ledger: dict[str, Any]) -> Path:
    lp = ledger_path(workdir, slug)
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return lp


def is_strictly_better(
    new_obj: float,
    old_obj: float | None,
    *,
    minimize: bool,
    tol: float = 1e-6,
) -> bool:
    """Return True if ``new_obj`` strictly improves over ``old_obj`` beyond ``tol``."""
    if old_obj is None:
        return True
    return (new_obj < old_obj - tol) if minimize else (new_obj > old_obj + tol)


def _sha256_file(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def record_experiment(
    workdir: Path | str,
    slug: str,
    *,
    round_idx: int,
    strategy_stage: str,
    hypothesis: str,
    timeout_budget_s: int,
    wall_time_s: float,
    objective: float | None,
    best_bound: float | None = None,
    gap: float | None = None,
    proven_optimal: bool = False,
    validation_ok: bool = False,
    minimize: bool | None = None,
    target_rounds: int = 5,
    solver_script: Path | None = None,
    solution_path: Path | None = None,
    error_summary: str = "",
) -> dict[str, Any]:
    """Append round result and promote incumbent ONLY when validated and strictly better."""
    wd = Path(workdir).resolve()
    ledger = load_ledger(
        wd,
        slug,
        minimize=True if minimize is None else bool(minimize),
        target_rounds=target_rounds,
    )
    if minimize is not None:
        ledger["minimize"] = bool(minimize)
    eff_min = bool(ledger.get("minimize", True))

    inc = ledger.get("incumbent") if isinstance(ledger.get("incumbent"), dict) else None
    inc_obj = float(inc["objective"]) if (inc and inc.get("objective") is not None) else None

    promoted = False
    if validation_ok and objective is not None:
        cand_obj = float(objective)
        if is_strictly_better(cand_obj, inc_obj, minimize=eff_min):
            promoted = True
            inc = {
                "round": int(round_idx),
                "strategy_stage": strategy_stage,
                "objective": cand_obj,
                "best_bound": float(best_bound) if best_bound is not None else None,
                "gap": float(gap) if gap is not None else None,
                "proven_optimal": bool(proven_optimal),
                "wall_time_s": round(float(wall_time_s), 3),
                "solver_sha256": _sha256_file(solver_script),
            }
            ledger["incumbent"] = inc
            if solver_script and solver_script.is_file():
                b_solv = best_solver_path(wd, slug)
                b_solv.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(solver_script, b_solv)
            if solution_path and solution_path.is_file():
                b_sol = best_solution_path(wd, slug)
                b_sol.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(solution_path, b_sol)

    entry = {
        "round": int(round_idx),
        "strategy_stage": strategy_stage,
        "hypothesis": str(hypothesis or "")[:300],
        "timeout_budget_s": int(timeout_budget_s),
        "wall_time_s": round(float(wall_time_s), 3),
        "objective": float(objective) if objective is not None else None,
        "best_bound": float(best_bound) if best_bound is not None else None,
        "gap": float(gap) if gap is not None else None,
        "proven_optimal": bool(proven_optimal),
        "validation_ok": bool(validation_ok),
        "promoted": promoted,
        "solver_sha256": _sha256_file(solver_script),
        "error_summary": str(error_summary or "")[:400],
        "ts": int(time.time()),
    }
    ledger["rounds"].append(entry)
    save_ledger(wd, slug, ledger)
    return {"entry": entry, "ledger": ledger, "promoted": promoted}


def format_ledger_summary(ledger: dict[str, Any]) -> str:
    """Render a compact Markdown experiment ledger table for the modeler's next round."""
    inc = ledger.get("incumbent") if isinstance(ledger.get("incumbent"), dict) else None
    sense = "最小化" if ledger.get("minimize", True) else "最大化"
    lines = [
        f"### 实验账本 (Optimization Sense: {sense}, Target={ledger.get('target_rounds')}, Max={ledger.get('max_rounds')})",
    ]
    if inc:
        lines.append(
            f"- **当前最优纪录 (Incumbent)**: `R{inc.get('round')}` objective=`{inc.get('objective')}`, "
            f"bound=`{inc.get('best_bound')}`, gap=`{inc.get('gap')}`, proven_optimal=`{inc.get('proven_optimal')}`"
        )
    else:
        lines.append("- **当前最优纪录 (Incumbent)**: 尚无通过校验的可行解")
    rounds = ledger.get("rounds") or []
    if rounds:
        lines.extend([
            "",
            "| Round | Stage | Valid | Objective | Gap | Time(s) | Promoted | Error/Note |",
            "|---|---|---|---|---|---|---|---|",
        ])
        for r in rounds[-8:]:
            lines.append(
                f"| R{r.get('round')} | `{r.get('strategy_stage')}` | {'✅' if r.get('validation_ok') else '❌'} "
                f"| {r.get('objective')} | {r.get('gap')} | {r.get('wall_time_s')} "
                f"| {'★' if r.get('promoted') else '-'} | {(r.get('error_summary') or r.get('hypothesis') or '')[:60]} |"
            )
    return "\n".join(lines)


def extract_and_write_fenced_code(
    workdir: Path | str,
    text: str,
    *,
    default_rel_path: str = "",
) -> list[dict[str, Any]]:
    """Extract ```python blocks tagged with `# file: <rel_path>`, AST-check syntax, and write safely.

    Never overwrites a valid on-disk script if the extracted code fails ``ast.parse``.
    """
    wd = Path(workdir).resolve()
    results: list[dict[str, Any]] = []
    for match in _FENCED_PY_RE.finditer(text or ""):
        code = match.group(1)
        lines = code.splitlines()
        rel_target = ""
        if lines:
            hdr = _FILE_HEADER_RE.match(lines[0])
            if hdr:
                rel_target = hdr.group(1).strip().strip("`\"'")
        if not rel_target:
            rel_target = default_rel_path.strip()
        if not rel_target:
            continue
        norm_rel = rel_target.replace("\\", "/").lstrip("./")
        if ".." in norm_rel.split("/") or not any(norm_rel.startswith(p) for p in _ALLOWED_REL_PREFIXES):
            results.append({"ok": False, "path": norm_rel, "error": f"disallowed target path: {norm_rel}"})
            continue
        try:
            ast.parse(code, filename=norm_rel)
        except SyntaxError as exc:
            results.append({"ok": False, "path": norm_rel, "error": f"SyntaxError line {exc.lineno}: {exc.msg}"})
            continue
        target = (wd / norm_rel).resolve()
        try:
            target.relative_to(wd)
        except ValueError:
            results.append({"ok": False, "path": norm_rel, "error": "path escapes workdir"})
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code.rstrip() + "\n", encoding="utf-8")
        results.append({"ok": True, "path": norm_rel, "abs_path": str(target), "bytes": target.stat().st_size})
    return results
