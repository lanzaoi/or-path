#!/usr/bin/env python3
"""OR-Path Live Watch HTTP face (V0 Tier-1 + P1 poll + model pref).

  GET  /                         → orpath/web/watch.html
  GET  /api/health
  GET  /api/poll
  GET  /api/snapshot
  GET  /api/stream
  GET  /api/model                → current Pi model + presets
  POST /api/model                → {provider, model} set preference
  GET  /api/steer?slug=          → load notes/<slug>-human-steer.json
  POST /api/steer                → write human steer (lg/pi split; no objective)

Bind 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orpath.human_steer import (  # noqa: E402
    ALLOWED_SOLVE_MODES,
    build_steer_cta,
    find_forbidden_keys,
    load_human_steer,
    normalize_steer_payload,
    save_human_steer,
    steer_path,
)
from orpath.paths import orpath_home, orpath_workdir  # noqa: E402
from orpath.watch_snapshot import (  # noqa: E402
    build_problem_view,
    build_snapshot,
    compute_source_fingerprint,
)

WEB_DIR = ROOT / "orpath" / "web"
HTML_NAME = "watch.html"
DEFAULT_PORT = 8765
MAX_PORT_TRIES = 20
SSE_INTERVAL_S = 0.5

PROBLEM_PRESETS: list[dict[str, Any]] = [
    {
        "id": "live-btube",
        "title": "2026 校赛 B 题：异形圆管工件激光下料优化（Q1–Q4 全链路）",
        "desc": "10 种空间三维圆管工件，4 种标准母材（9–12m），含定长下料、四模式端部共切、余料跨批排产及 16 项物理质检报告。",
        "slug": "live-btube",
        "problem_id": "b-tube-cut",
        "problem_class": "tube_cut",
        "solve_mode": "tube",
        "seed_slug": "live-btube",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/intake/tube_cut_b2026/problem-surface.md",
        "tags": ["工业激光下料", "Q1–Q4 四问", "已含完整解与论文"],
    },
    {
        "id": "tube-surface",
        "title": "异形圆管下料题面审读（从 Markdown 原文一键导入解析）",
        "desc": "从原始竞赛题面触发 OCR/结构化审读，自动提取 Q1–Q4 子问题、母材约束与交付表结构。",
        "slug": "case-btube-intake",
        "problem_id": "b-tube-cut",
        "problem_class": "tube_cut",
        "solve_mode": "tube",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/intake/tube_cut_b2026/problem-surface.md",
        "tags": ["题面审读 1.1", "圆管切割", "支持重算"],
    },
    {
        "id": "polyomino-q1",
        "title": "异形多联骨牌覆盖与板材排样（M2 Polyomino 工业排样）",
        "desc": "离散制造板材/模具网格精确覆盖问题，基于 CP-SAT 整数规划求解无重叠最优拼排方案。",
        "slug": "case-polyomino",
        "problem_id": "polyomino_b_q1",
        "problem_class": "polyomino_cover",
        "solve_mode": "polyomino",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/t3/polyomino_b_q1/problem.md",
        "tags": ["M2 主域桥", "CP-SAT 精确覆盖", "二维排样"],
    },
    {
        "id": "structure-q4",
        "title": "多批次工业下料与余料结转标准赛题（Q1–Q4 结构化模板）",
        "desc": "四问递进式工业排产题面，仅用于 1.1 题面结构化拆解验收（无对应求解器算例参数，禁止假绑金标）。",
        "slug": "case-structure-q4",
        "problem_id": "",
        "problem_class": "intake_only",
        "solve_mode": "none",
        "intake_only": True,
        "can_solve": False,
        "source_rel": "fixtures/intake/structure_q4/source.txt",
        "tags": ["四问提取", "题面解析演示", "仅审题演示 (Intake Only)"],
    },
    {
        "id": "pdf-sample",
        "title": "PDF 扫描/文本题面 OCR 导入示例（sample_text.pdf）",
        "desc": "演示真实 PDF 题面文件经 pdf_text / RapidOCR 识别并生成结构化 Problem Brief 与 intake.json（仅审题演示）。",
        "slug": "case-pdf-ocr",
        "problem_id": "",
        "problem_class": "intake_only",
        "solve_mode": "none",
        "intake_only": True,
        "can_solve": False,
        "source_rel": "fixtures/intake/ocr/sample_text.pdf",
        "tags": ["PDF 识别", "OCR 管道", "仅审题演示 (Intake Only)"],
    },
    {
        "id": "cvrp-n32",
        "title": "带容量多车物流路径优化（CVRPLIB A-n32-k5）",
        "desc": "32 节点、5 辆额定载重车队的经典工业配送车辆路径问题，OR-Tools 启发式/元启发式求解与容量重算校验。",
        "slug": "case-cvrp",
        "problem_id": "cvrplib_a_n32_k5",
        "problem_class": "vrp",
        "solve_mode": "ortools",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/t3/cvrplib_a_n32_k5/problem.md",
        "tags": ["物流调度", "CVRP", "OR-Tools"],
    },
    {
        "id": "vrp-tw",
        "title": "带时间窗准时制配送调度（VRPTW 工业物流）",
        "desc": "含严格到达时间窗与车载容量双重硬约束的厂内/城配多车路径规划问题。",
        "slug": "case-vrptw",
        "problem_id": "vrp_tw",
        "problem_class": "vrp",
        "solve_mode": "ortools",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/t3/vrp_tw/problem.md",
        "tags": ["时间窗约束", "VRPTW", "准时制排程"],
    },
    {
        "id": "tsp-n8",
        "title": "多工位设备巡检回路规划（TSP n=8）",
        "desc": "8 站点闭环最短巡检路径问题，支持 OR-Tools / HiGHS 建模求解与回路完整性独立验证。",
        "slug": "case-tsp8",
        "problem_id": "tsp_n8",
        "problem_class": "tsp",
        "solve_mode": "ortools",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/t2/tsp_n8/problem.md",
        "tags": ["设备巡检", "TSP", "闭环校验"],
    },
    {
        "id": "m0-sp",
        "title": "网络流最短路径规划（M0 基准金标案例）",
        "desc": "有向加权图最短路径标准基准案例，含完整知识检索、数学建模、求解与校验闭环。",
        "slug": "m0",
        "problem_id": "shortest_path",
        "problem_class": "shortest_path",
        "solve_mode": "networkx",
        "seed_slug": "m0",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/t1/shortest_path/problem.md",
        "tags": ["M0 金标", "网络流", "秒级验算"],
    },
    {
        "id": "taillard-ft06",
        "title": "作业车间调度优化（Taillard / FT06 基准）",
        "desc": "经典 6 工件 6 机器作业车间调度问题（JSSP），基于 CP-SAT / PyJobShop 求解最优完工时间 (Makespan=55) 与甘特图排产。",
        "slug": "case-jssp-ft06",
        "problem_id": "ft06",
        "problem_class": "job_shop",
        "solve_mode": "jssp",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/benchmarks/taillard/jssp/ft06.json",
        "tags": ["车间调度", "JSSP", "CP-SAT", "Taillard"],
    },
    {
        "id": "cflp-cap41",
        "title": "有容量限制选址分配（OR-Library CFLP cap41）",
        "desc": "16 候选厂址、50 客户需求点的经典容量选址问题（CFLP），基于 MIP 混合整数规划实现设施固定投资与运输总成本联合最优。",
        "slug": "case-cflp-cap41",
        "problem_id": "cap41",
        "problem_class": "facility_location",
        "solve_mode": "facility",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/benchmarks/orlib_cflp/cap41.txt",
        "tags": ["设施选址", "CFLP", "OR-Library", "供应链网络"],
    },
    {
        "id": "max-clique-dimacs",
        "title": "最大团与最大独立集图优化（DIMACS myciel3）",
        "desc": "DIMACS 图基准 myciel3 实例，运用 NetworkX 分支定界与 OR-Tools CP-SAT 对偶互补验证最大团 (omega=2) 与最大独立集 (alpha=5)。",
        "slug": "case-max-clique",
        "problem_id": "myciel3",
        "problem_class": "max_clique",
        "solve_mode": "max_clique",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/benchmarks/dimacs/myciel3.col",
        "tags": ["图论优化", "最大团", "DIMACS", "对偶验证"],
    },
    {
        "id": "hub-cab10",
        "title": "枢纽辐射网络选址优化（CAB 10 城市航网）",
        "desc": "美国民航局 (CAB) 10 城市客流数据集，p=3 枢纽辐射中继网络非线性转运折扣优化，基于 OR-Tools MIP 严格求解。",
        "slug": "case-hub-cab10",
        "problem_id": "CAB10",
        "problem_class": "hub_location",
        "solve_mode": "hub_location",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/benchmarks/hub_location/CAB10.json",
        "tags": ["航空物流", "p-Hub 选址", "CAB 基准", "MIP"],
    },
    {
        "id": "qap-nug12",
        "title": "二次指派与厂区设备布局优化（QAPLIB nug12）",
        "desc": "经典 12 设施 12 选址二次指派问题（QAP），基于 SciPy 快速近似二次规划与 2-opt 局部搜索混合求解物料搬运能耗最优布局。",
        "slug": "case-qap-nug12",
        "problem_id": "nug12",
        "problem_class": "qap",
        "solve_mode": "qap",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/benchmarks/qaplib/nug12.dat",
        "tags": ["车间布局", "QAPLIB", "二次指派", "物料搬运"],
    },
    {
        "id": "rcpsp-j30",
        "title": "多资源约束项目排程（PSPLib j301_1）",
        "desc": "32 工序、4 种有限可再生资源的标准 PSPLib 项目网络，CP-SAT 精确求解无资源冲突最短工期与关键路径识别。",
        "slug": "case-rcpsp-j30",
        "problem_id": "j301_1",
        "problem_class": "rcpsp",
        "solve_mode": "rcpsp",
        "intake_only": False,
        "can_solve": True,
        "source_rel": "fixtures/benchmarks/psplib/j301_1.sm",
        "tags": ["工程排期", "RCPSP", "关键路径", "PSPLib"],
    },
]


def _pick_python(home: Path) -> str:
    for rel in (
        ".venv-314/Scripts/python.exe",
        ".venv-314/bin/python",
        ".venv/Scripts/python.exe",
        ".venv/bin/python",
    ):
        cand = home / rel
        if cand.is_file():
            return str(cand)
    return sys.executable


def _sanitize_slug(raw: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", (raw or "").strip()).strip("-")
    return s[:48] or "case-1"


def _guess_domain_info(filename_or_text: str) -> dict[str, Any]:
    """Return soft class hints only for custom text/upload.

    Per specs/problem-intake.md §2.3 & specs/architecture.md §7 #11:
    NEVER invent or bind a golden fixture problem_id (shortest_path, b-tube-cut, etc.)
    from free-form text or uploaded files.
    """
    low = (filename_or_text or "").lower()
    hint_class = "unknown"
    if any(k in low for k in ("polyomino", "tiling", "guapai", "骨牌", "多联", "排样", "覆盖")):
        hint_class = "polyomino_cover"
    elif any(k in low for k in ("tube", "圆管", "母材", "共切", "下料", "cutting")):
        hint_class = "tube_cut"
    elif any(k in low for k in ("vrp_tw", "vrptw", "时间窗", "time window", "cvrp", "vrp", "车辆路径", "车队", "capacity")):
        hint_class = "vrp"
    elif any(k in low for k in ("tsp", "旅行商", "巡检")):
        hint_class = "tsp"
    elif any(k in low for k in ("shortest_path", "最短路", "dijkstra")):
        hint_class = "shortest_path"
    elif any(k in low for k in ("job_shop", "jssp", "fjssp", "taillard", "车间", "工件", "流水车间", "工序", "makespan")):
        hint_class = "job_shop"
    elif any(k in low for k in ("facility_location", "facility", "cflp", "选址", "厂址", "配送中心选址", "sscflp", "scnd")):
        hint_class = "facility_location"
    elif any(k in low for k in ("rcpsp", "psplib", "项目排程", "工期", "关键路径", ".sm")):
        hint_class = "rcpsp"
    elif any(k in low for k in ("hub_location", "hub", "枢纽", "cab10", "中继网络")):
        hint_class = "hub_location"
    elif any(k in low for k in ("qap", "quadratic_assignment", "二次指派", "设备布局", "布局优化", "qaplib")):
        hint_class = "qap"
    elif any(k in low for k in ("max_clique", "clique", "最大团", "独立集", "independent_set")):
        hint_class = "max_clique"
    elif any(k in low for k in ("graph_coloring", "vertex_coloring", "着色", "色数", "chromatic", "dsatur")):
        hint_class = "graph_coloring"
    elif any(k in low for k in ("lot_sizing", "wagner", "clsp", "ulsp", "批量", "订货批量", "ww12")):
        hint_class = "lot_sizing"
    elif any(k in low for k in ("portfolio", "markowitz", "投资组合", "sharpe", "夏普")):
        hint_class = "portfolio_opt"
    elif any(k in low for k in ("qubo", "ising", "伊辛", "max_cut", "最大割", "partitioning")):
        hint_class = "qubo_ising"
    elif any(k in low for k in ("network_flow", "min_cost_flow", "最小费用流", "二分图匹配", "多商品流")):
        hint_class = "network_flow"
    elif any(k in low for k in ("bin_packing", "binpack", "装箱", "装载")):
        hint_class = "bin_packing"
    elif any(k in low for k in ("stochastic", "farmer", "两阶段随机", "随机规划")):
        hint_class = "stochastic_lp"
    elif any(k in low for k in ("staff_rostering", "rostering", "shift", "排班", "轮班", "护士排班")):
        hint_class = "staff_rostering"
    elif any(k in low for k in ("game_theory", "nash", "纳什", "博弈", "bimatrix")):
        hint_class = "game_theory"
    elif any(k in low for k in ("microgrid", "微网", "电网", "调控", "储能", "光伏", "smart_grid")):
        hint_class = "microgrid"
    return {
        "domain": "unregistered",
        "problem_id": "",
        "problem_class": "unknown",
        "problem_class_hint": hint_class,
        "solve_mode": "none",
        "can_solve": False,
    }


IN_MEMORY_BENCHMARKS = {
    "ww12",
    "clsp60",
    "max_cut",
    "qubo",
    "ising",
    "number_partitioning",
    "min_cost_flow",
    "bipartite_matching",
    "multi_commodity_flow",
    "max_sharpe",
    "min_volatility",
    "portfolio_default",
    "portfolio_3asset",
    "rostering_toy",
    "shift_sched",
    "binpack_1d",
    "binpack_2d",
    "binpack_3d",
    "farmer_problem",
    "farmer",
    "microgrid_campus",
    "campus_microgrid",
}


def _has_runnable_fixture(home: Path, workdir: Path, problem_id: str, norm_class: str) -> bool:
    """True only if problem_id corresponds to a real fixture/case dataset on disk or recognized in-memory benchmark."""
    pid = (problem_id or "").strip()
    if not pid:
        return False
    if pid in IN_MEMORY_BENCHMARKS:
        return True
    if norm_class == "tube_cut" and pid in {"b-tube-cut", "tube_cut_b2026"}:
        return (home / "fixtures" / "t3" / "tube_cut_b2026").is_dir()
    pid_low = pid.lower()
    for base in (workdir, home):
        for tier in ("t3", "t2", "t1"):
            if (base / "fixtures" / tier / pid).is_dir():
                return True
        bm = base / "fixtures" / "benchmarks"
        if bm.is_dir():
            for p in bm.rglob("*"):
                if p.stem.lower() == pid_low or p.name.lower() == pid_low:
                    return True
    return False


_MODEL_PRESETS: list[dict[str, str]] = [
    {"provider": "xfyun", "model": "spark-x2.6", "label": "讯飞星火 · spark-x2.6"},
    {"provider": "deepseek", "model": "deepseek-reasoner", "label": "DeepSeek · deepseek-reasoner (R1)"},
    {"provider": "deepseek", "model": "deepseek-chat", "label": "DeepSeek · deepseek-chat (V3)"},
    {"provider": "deepseek", "model": "deepseek-v4-flash", "label": "DeepSeek · deepseek-v4-flash"},
]


def _get_model_pref(home: Path, workdir: Path | None = None) -> dict[str, Any]:
    pref_dir = (workdir or home) / "outputs"
    pref_path = pref_dir / ".model_pref.json"
    provider = "xfyun"
    model = os.environ.get("XFYUN_MODEL", "").strip() or "spark-x2.6"
    if pref_path.is_file():
        try:
            data = json.loads(pref_path.read_text(encoding="utf-8", errors="replace"))
            provider = str(data.get("provider") or provider).strip()
            model = str(data.get("model") or model).strip()
        except Exception:  # noqa: BLE001
            pass
    return {
        "provider": provider,
        "model": model,
        "presets": list(_MODEL_PRESETS),
        "settings_path": str(pref_path),
    }


def _set_model_pref(*, provider: str, model: str, home: Path, workdir: Path | None = None) -> dict[str, Any]:
    pref_dir = (workdir or home) / "outputs"
    pref_dir.mkdir(parents=True, exist_ok=True)
    pref_path = pref_dir / ".model_pref.json"
    payload = {
        "provider": (provider or "xfyun").strip(),
        "model": model.strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    pref_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return _get_model_pref(home=home, workdir=workdir)



def _discover_workdir_cases(workdir: Path, home: Path) -> list[dict[str, Any]]:
    slugs: set[str] = set()
    runs_dir = workdir / "runs"
    if runs_dir.is_dir():
        for d in runs_dir.iterdir():
            if d.is_dir() and not d.name.startswith("__"):
                slugs.add(d.name)
    out_dir = workdir / "outputs"
    if out_dir.is_dir():
        for p in out_dir.glob("*-intake.json"):
            slugs.add(p.name[: -len("-intake.json")])
        for p in out_dir.glob("*-solution.json"):
            slugs.add(p.name[: -len("-solution.json")])

    cases: list[dict[str, Any]] = []
    for s in sorted(slugs):
        pv = build_problem_view(workdir=workdir, home=home, slug=s)
        stages_dir = workdir / "runs" / s / "stages"
        st_count = len(list(stages_dir.glob("*.json"))) if stages_dir.is_dir() else 0
        sol = pv.get("solution_summary") or {}
        val = pv.get("validate_summary") or {}
        cases.append({
            "slug": s,
            "title": pv.get("title") or s,
            "problem_id": pv.get("problem_id") or "",
            "problem_class": pv.get("problem_class") or "",
            "has_intake": bool(pv.get("has_intake")),
            "has_problem": bool(pv.get("has_problem")),
            "has_solution": bool(sol.get("exists")),
            "solution_status": sol.get("status"),
            "objective": sol.get("objective"),
            "validate_ok": val.get("ok") if val.get("exists") else None,
            "stages_count": st_count,
            "subproblems_count": len(pv.get("subproblems") or []),
        })
    return cases


class WatchHandler(SimpleHTTPRequestHandler):
    server_version = "ORPathWatch/0.3-apple"

    def __init__(self, *args, home: Path, workdir: Path, **kwargs):
        self._home = home
        self._workdir = workdir
        super().__init__(*args, **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[watch] " + (fmt % args) + "\n")

    def _send_json(self, code: int, obj: object) -> None:
        raw = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(raw)

    def _send_html_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404, f"missing {path.name}")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _qs_slug_thread(self, qs: dict) -> tuple[str, str]:
        slug = (qs.get("slug") or ["test"])[0].strip() or "test"
        thread = (qs.get("thread") or qs.get("thread_id") or [slug])[0].strip() or slug
        return slug, thread

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid json"})
            return
        if not isinstance(body, dict):
            self._send_json(400, {"ok": False, "error": "body must be object"})
            return

        if path == "/api/steer":
            slug = str(body.get("slug") or "").strip()
            if not slug:
                qs = parse_qs(parsed.query or "")
                slug = (qs.get("slug") or ["test"])[0].strip() or "test"
            doc, errs = normalize_steer_payload(
                body, slug=slug, source=str(body.get("source") or "watch_form")
            )
            if errs or doc is None:
                self._send_json(400, {"ok": False, "errors": errs or ["invalid steer"]})
                return
            try:
                path_out = save_human_steer(self._workdir, slug, doc)
                ctas = build_steer_cta(doc, workdir=self._workdir)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "path": str(path_out),
                        "steer": doc,
                        "next_actions": ctas,
                        "note": "manual CTA only — browser never auto-resume",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/intake/import":
            self._handle_intake_import(body)
            return

        if path == "/api/intake/run":
            self._handle_intake_run(body)
            return

        if path == "/api/studio/analyze":
            self._handle_studio_analyze(body)
            return

        if path == "/api/studio/confirm":
            self._handle_studio_confirm(body)
            return

        if path != "/api/model":
            self.send_error(404, "not found")
            return
        provider = str(body.get("provider") or "").strip()
        model = str(body.get("model") or "").strip()
        if not model:
            self._send_json(400, {"ok": False, "error": "model required"})
            return
        try:
            info = _set_model_pref(
                provider=provider or "xfyun",
                model=model,
                home=self._home,
                workdir=self._workdir,
            )
            info["ok"] = True
            self._send_json(200, info)
        except Exception as exc:  # noqa: BLE001
            self._send_json(400, {"ok": False, "error": str(exc)})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        qs = parse_qs(parsed.query or "")

        if path == "/api/health":
            try:
                m = _get_model_pref(home=self._home, workdir=self._workdir)
            except Exception:  # noqa: BLE001
                m = {}
            self._send_json(
                200,
                {
                    "ok": True,
                    "root": str(self._home),
                    "workdir": str(self._workdir),
                    "html": str(WEB_DIR / HTML_NAME),
                    "html_exists": (WEB_DIR / HTML_NAME).is_file(),
                    "p1": True,
                    "model": m,
                    "endpoints": [
                        "/api/health",
                        "/api/poll",
                        "/api/snapshot",
                        "/api/stream",
                        "/api/model",
                        "/api/steer",
                        "/api/problems",
                        "/api/artifact",
                        "/api/intake/import",
                        "/api/intake/run",
                        "/api/studio/analyze",
                        "/api/studio/confirm",
                        "/api/artifact/download",
                    ],
                    "dialogue": True,
                    "problem_workbench": True,
                },
            )
            return

        if path == "/api/problems":
            try:
                cases = _discover_workdir_cases(self._workdir, self._home)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "presets": PROBLEM_PRESETS,
                        "cases": cases,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/artifact":
            slug, _thread = self._qs_slug_thread(qs)
            kind = (qs.get("kind") or ["brief"])[0].strip().lower()
            self._handle_artifact_get(slug, kind)
            return

        if path == "/api/artifact/download":
            slug, _thread = self._qs_slug_thread(qs)
            kind = (qs.get("kind") or ["solution"])[0].strip().lower()
            self._handle_artifact_download(slug, kind)
            return

        if path == "/api/steer":
            slug, _thread = self._qs_slug_thread(qs)
            doc = load_human_steer(self._workdir, slug)
            self._send_json(
                200,
                {
                    "ok": True,
                    "slug": slug,
                    "exists": doc is not None,
                    "path": str(steer_path(self._workdir, slug)),
                    "steer": doc,
                    "next_actions": build_steer_cta(doc, workdir=self._workdir)
                    if doc
                    else [],
                },
            )
            return

        if path == "/api/model":
            try:
                info = _get_model_pref(home=self._home, workdir=self._workdir)
                info["ok"] = True
                self._send_json(200, info)
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/poll":
            slug, thread = self._qs_slug_thread(qs)
            try:
                info = compute_source_fingerprint(
                    slug=slug, thread_id=thread, workdir=self._workdir
                )
                prev = (qs.get("prev_fp") or qs.get("prev_fingerprint") or [None])[0]
                info["dirty"] = True if not prev else (prev != info.get("fingerprint"))
                self._send_json(200, info)
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/snapshot":
            slug, thread = self._qs_slug_thread(qs)
            prev_fp = (qs.get("prev_fp") or qs.get("prev_fingerprint") or [None])[0]
            prev_ev_raw = (qs.get("prev_events") or [None])[0]
            prev_events = None
            if prev_ev_raw is not None and str(prev_ev_raw).strip() != "":
                try:
                    prev_events = int(prev_ev_raw)
                except ValueError:
                    prev_events = None
            try:
                snap = build_snapshot(
                    slug=slug,
                    thread_id=thread,
                    root=self._home,
                    workdir=self._workdir,
                    prev_fingerprint=prev_fp,
                    prev_events_count=prev_events,
                )
                try:
                    snap["pi_model"] = _get_model_pref(home=self._home, workdir=self._workdir)
                except Exception:  # noqa: BLE001
                    pass
                self._send_json(200, snap)
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if path == "/api/stream":
            slug, thread = self._qs_slug_thread(qs)
            self._sse_loop(slug, thread)
            return

        if path in {"/", "/index.html", "/watch.html"}:
            try:
                sys.path.insert(0, str(ROOT))
                from orpath.web.build import build
                build()
            except Exception:
                pass
            self._send_html_file(WEB_DIR / HTML_NAME)
            return

        if path.startswith("/static/") or path.startswith("/src/"):
            rel_sub = path.split("/", 2)[-1]
            cand = (WEB_DIR / "src" / rel_sub).resolve()
            src_root = (WEB_DIR / "src").resolve()
            if cand.is_file() and str(cand).startswith(str(src_root)):
                ext = cand.suffix.lower()
                ctype = "text/plain"
                if ext == ".css":
                    ctype = "text/css; charset=utf-8"
                elif ext == ".js":
                    ctype = "text/javascript; charset=utf-8"
                elif ext in {".html", ".htm"}:
                    ctype = "text/html; charset=utf-8"
                elif ext == ".json":
                    ctype = "application/json; charset=utf-8"
                elif ext == ".svg":
                    ctype = "image/svg+xml"
                data = cand.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

        self.send_error(404, "not found")

    def _handle_artifact_get(self, slug: str, kind: str) -> None:
        wd = self._workdir
        mapping: dict[str, tuple[Path, str]] = {
            "brief": (wd / "notes" / f"{slug}-problem-brief.md", "markdown"),
            "ocr_raw": (wd / "notes" / f"{slug}-ocr.raw.md", "markdown"),
            "intake": (wd / "outputs" / f"{slug}-intake.json", "json"),
            "schema": (wd / "outputs" / f"{slug}-schema.json", "json"),
            "solution": (wd / "outputs" / f"{slug}-solution.json", "json"),
            "validate": (wd / "outputs" / f"{slug}-validate.json", "json"),
            "paper": (wd / "papers" / f"{slug}.md", "markdown"),
            "explain": (wd / "notes" / f"{slug}-explain.md", "markdown"),
            "research": (wd / "notes" / f"{slug}-research.md", "markdown"),
            "provenance": (wd / "outputs" / f"{slug}.provenance.md", "markdown"),
            "plan": (wd / "outputs" / ".plans" / f"{slug}.md", "markdown"),
            "analysis": (wd / "outputs" / f"{slug}-studio-analysis.json", "json"),
            "profile": (wd / "outputs" / f"{slug}-data-profile.json", "json"),
        }
        if kind not in mapping:
            self._send_json(400, {"ok": False, "error": f"unknown artifact kind: {kind}"})
            return
        target, fmt = mapping[kind]
        if not target.is_file():
            self._send_json(404, {"ok": False, "error": f"artifact not found: {target.name}"})
            return
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
            self._send_json(
                200,
                {
                    "ok": True,
                    "slug": slug,
                    "kind": kind,
                    "format": fmt,
                    "path": str(target),
                    "content": text[:120000],
                },
            )
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": str(exc)})

    def _handle_artifact_download(self, slug: str, kind: str) -> None:
        wd = self._workdir
        mapping: dict[str, tuple[Path, str]] = {
            "brief": (wd / "notes" / f"{slug}-problem-brief.md", "text/markdown"),
            "ocr_raw": (wd / "notes" / f"{slug}-ocr.raw.md", "text/markdown"),
            "intake": (wd / "outputs" / f"{slug}-intake.json", "application/json"),
            "schema": (wd / "outputs" / f"{slug}-schema.json", "application/json"),
            "solution": (wd / "outputs" / f"{slug}-solution.json", "application/json"),
            "validate": (wd / "outputs" / f"{slug}-validate.json", "application/json"),
            "paper": (wd / "papers" / f"{slug}.md", "text/markdown"),
            "explain": (wd / "notes" / f"{slug}-explain.md", "text/markdown"),
            "research": (wd / "notes" / f"{slug}-research.md", "text/markdown"),
            "provenance": (wd / "outputs" / f"{slug}.provenance.md", "text/markdown"),
            "plan": (wd / "outputs" / ".plans" / f"{slug}.md", "text/markdown"),
            "analysis": (wd / "outputs" / f"{slug}-studio-analysis.json", "application/json"),
            "profile": (wd / "outputs" / f"{slug}-data-profile.json", "application/json"),
        }
        if kind not in mapping:
            self._send_json(400, {"ok": False, "error": f"unknown artifact kind: {kind}"})
            return
        target, mime = mapping[kind]
        if not target.is_file():
            self._send_json(404, {"ok": False, "error": f"artifact not found: {target.name}"})
            return
        try:
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": str(exc)})

    def _handle_intake_import(self, body: dict[str, Any]) -> None:
        from orpath.intake_nodes import standalone_intake

        mode = str(body.get("mode") or "preset").strip().lower()
        wd = self._workdir
        home = self._home

        try:
            if mode == "preset":
                preset_id = str(body.get("preset_id") or "").strip()
                preset = next((p for p in PROBLEM_PRESETS if p["id"] == preset_id), None)
                if not preset:
                    self._send_json(400, {"ok": False, "error": f"unknown preset_id: {preset_id}"})
                    return
                slug = _sanitize_slug(str(body.get("slug") or preset["slug"]))
                seed_slug = preset.get("seed_slug")
                if seed_slug and slug == seed_slug:
                    from scripts.install_demo_seed import install_seeds

                    install_seeds(home / "demo" / "seed", wd, slugs=(seed_slug,), force=False)
                    self._send_json(
                        200,
                        {
                            "ok": True,
                            "mode": "seed",
                            "slug": slug,
                            "thread_id": slug,
                            "preset": preset,
                        },
                    )
                    return

                src_rel = str(preset.get("source_rel") or "")
                src_path = (home / src_rel).resolve()
                if not src_path.is_file():
                    self._send_json(404, {"ok": False, "error": f"preset source missing: {src_rel}"})
                    return
                res = standalone_intake(root=wd, slug=slug, sources=[src_path])
                intake_json_path = wd / "outputs" / f"{slug}-intake.json"
                if intake_json_path.is_file():
                    try:
                        idoc = json.loads(intake_json_path.read_text(encoding="utf-8"))
                        if isinstance(idoc, dict):
                            if preset.get("can_solve") and preset.get("problem_id"):
                                idoc["problem_id_hint"] = preset["problem_id"]
                                idoc["problem_class_hint"] = preset["problem_class"]
                            else:
                                idoc["problem_id_hint"] = None
                                idoc["problem_class_hint"] = None
                            intake_json_path.write_text(
                                json.dumps(idoc, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8",
                            )
                    except (OSError, json.JSONDecodeError):
                        pass
                pv = build_problem_view(workdir=wd, home=home, slug=slug)
                pv["domain"] = preset.get("problem_class") if preset.get("can_solve") else "unregistered"
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "mode": "preset",
                        "slug": slug,
                        "thread_id": slug,
                        "preset": preset,
                        "intake": res,
                        "problem_view": pv,
                    },
                )
                return

            if mode == "upload":
                file_name = str(body.get("file_name") or "problem.txt").strip()
                safe_name = re.sub(r"[^a-zA-Z0-9._\-\u4e00-\u9fa5]+", "_", Path(file_name).name) or "problem.txt"
                slug = _sanitize_slug(str(body.get("slug") or Path(safe_name).stem or "case-upload"))
                b64 = str(body.get("file_base64") or "").strip()
                if "," in b64 and b64.startswith("data:"):
                    b64 = b64.split(",", 1)[1]
                if not b64:
                    self._send_json(400, {"ok": False, "error": "file_base64 required"})
                    return
                raw_bytes = base64.b64decode(b64)
                inbox_dir = wd / "inbox" / slug
                inbox_dir.mkdir(parents=True, exist_ok=True)
                dest_path = inbox_dir / safe_name
                dest_path.write_bytes(raw_bytes)

                res = standalone_intake(root=wd, slug=slug, sources=[dest_path])
                brief_txt = ""
                if res.get("brief_path") and Path(res["brief_path"]).is_file():
                    brief_txt = Path(res["brief_path"]).read_text(encoding="utf-8", errors="replace")[:4000]
                dom = _guess_domain_info(file_name + "\n" + brief_txt)
                pv = build_problem_view(workdir=wd, home=home, slug=slug)
                pv["domain"] = dom["domain"]
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "mode": "upload",
                        "slug": slug,
                        "thread_id": slug,
                        "saved_path": str(dest_path),
                        "domain_guess": dom,
                        "intake": res,
                        "problem_view": pv,
                    },
                )
                return

            if mode == "text":
                raw_text = str(body.get("raw_text") or "").strip()
                title = str(body.get("title") or "").strip()
                if not raw_text:
                    self._send_json(400, {"ok": False, "error": "题面文本不能为空"})
                    return
                slug = _sanitize_slug(str(body.get("slug") or "case-custom"))
                inbox_dir = wd / "inbox" / slug
                inbox_dir.mkdir(parents=True, exist_ok=True)
                dest_path = inbox_dir / "problem-statement.md"
                full_md = (f"# {title}\n\n{raw_text}\n" if title and not raw_text.startswith("#") else f"{raw_text}\n")
                dest_path.write_text(full_md, encoding="utf-8")

                res = standalone_intake(root=wd, slug=slug, sources=[dest_path])
                dom = _guess_domain_info(title + "\n" + raw_text)
                pv = build_problem_view(workdir=wd, home=home, slug=slug)
                pv["domain"] = dom["domain"]
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "mode": "text",
                        "slug": slug,
                        "thread_id": slug,
                        "saved_path": str(dest_path),
                        "domain_guess": dom,
                        "intake": res,
                        "problem_view": pv,
                    },
                )
                return

            if mode == "folder":
                raw_files = body.get("files")
                if not isinstance(raw_files, list) or not raw_files:
                    self._send_json(400, {"ok": False, "error": "files list required for folder mode"})
                    return
                slug = _sanitize_slug(str(body.get("slug") or "case-folder"))
                inbox_dir = wd / "inbox" / slug
                inbox_dir.mkdir(parents=True, exist_ok=True)

                saved_files: list[Path] = []
                for f in raw_files:
                    if not isinstance(f, dict):
                        continue
                    rel = str(f.get("rel_path") or f.get("name") or "").strip().replace("\\", "/")
                    if not rel or rel.startswith("/") or rel.startswith("../") or "/../" in f"/{rel}/":
                        self._send_json(400, {"ok": False, "error": f"invalid rel_path: {rel}"})
                        return
                    b64 = str(f.get("content_base64") or f.get("file_base64") or "").strip()
                    if "," in b64 and b64.startswith("data:"):
                        b64 = b64.split(",", 1)[1]
                    raw_bytes = base64.b64decode(b64) if b64 else b""
                    dest_p = inbox_dir / rel
                    dest_p.parent.mkdir(parents=True, exist_ok=True)
                    dest_p.write_bytes(raw_bytes)
                    saved_files.append(dest_p)

                from orpath.studio_analyzer import profile_inbox_assets
                dp = profile_inbox_assets(inbox_dir, slug, wd / "outputs")

                stmt_sources = [
                    inbox_dir / st for st in dp.get("statement_files", []) if (inbox_dir / st).is_file()
                ]
                if not stmt_sources and saved_files:
                    stmt_sources = [saved_files[0]]

                res = standalone_intake(root=wd, slug=slug, sources=stmt_sources, assets_dir=inbox_dir)
                pv = build_problem_view(workdir=wd, home=home, slug=slug)
                pv["data_profile"] = dp
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "mode": "folder",
                        "slug": slug,
                        "thread_id": slug,
                        "files_count": len(saved_files),
                        "data_profile": dp,
                        "intake": res,
                        "problem_view": pv,
                    },
                )
                return

            self._send_json(400, {"ok": False, "error": f"unsupported import mode: {mode}"})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": str(exc)})

    def _handle_intake_run(self, body: dict[str, Any]) -> None:
        slug = _sanitize_slug(str(body.get("slug") or "case-run"))
        thread = _sanitize_slug(str(body.get("thread_id") or slug))
        wd = self._workdir
        home = self._home

        pv = build_problem_view(workdir=wd, home=home, slug=slug)
        raw_pid = str(body.get("problem_id") or pv.get("problem_id") or "").strip()
        raw_pclass = str(body.get("problem_class") or pv.get("problem_class") or "").strip()
        solve_mode = str(body.get("solve_mode") or "").strip()
        live = bool(body.get("live", False))

        from orpath.domain_registry import is_registered_solve_class, normalize_problem_class

        norm_class = normalize_problem_class(raw_pclass)
        has_fixture = _has_runnable_fixture(home, wd, raw_pid, norm_class)
        # Strict honesty contract: never bind custom/unregistered/intake-only problems to a golden fixture!
        if (
            not norm_class
            or norm_class in {"unknown", "unregistered", "intake_only"}
            or not is_registered_solve_class(norm_class)
            or not raw_pid
            or not has_fixture
        ):
            err_msg = (
                f"题目 '{slug}' (class={raw_pclass or '未注册'}, problem_id={raw_pid or '无算例绑定'}) "
                "尚无对应的结构化求解算例或领域求解适配器（当前已注册工业算例域：tube_cut, polyomino_cover, vrp, tsp, shortest_path）。"
                "根据系统硬法（specs/product-scope.md §4 与 specs/problem-intake.md §2.3），严禁对自定义题面或未注册域假绑内置金标（如 shortest_path=42），已诚实拦截并标记为 BLOCKED。"
            )
            out_dir = wd / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            blocked_sol = {
                "status": "BLOCKED",
                "objective": None,
                "solver": "none",
                "source": "no_domain_adapter_for_intake",
                "problem_id": raw_pid or None,
                "problem_class": norm_class or "unknown",
                "slug": slug,
                "meta": {
                    "exact": False,
                    "proven_optimal": False,
                    "blocked": True,
                    "method_class": "intake_blocked",
                    "reason": err_msg,
                },
            }
            (out_dir / f"{slug}-solution.json").write_text(
                json.dumps(blocked_sol, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            self._send_json(
                400,
                {
                    "ok": False,
                    "status": "BLOCKED",
                    "error_code": "unregistered_domain",
                    "error": err_msg,
                    "slug": slug,
                    "domain": "unregistered",
                },
            )
            return

        problem_id = raw_pid
        problem_class = norm_class
        if not solve_mode:
            if problem_class == "tube_cut":
                solve_mode = "tube"
            elif problem_class == "polyomino_cover":
                solve_mode = "polyomino"
            elif problem_class in {"vrp", "tsp"}:
                solve_mode = "ortools"
            else:
                solve_mode = "networkx"

        py_exe = _pick_python(home)
        cmd = [
            py_exe,
            str(home / "orpath" / "run_orpath.py"),
            "run",
            "--fresh",
            "--slug",
            slug,
            "--thread-id",
            thread,
            "--problem-id",
            problem_id,
            "--problem-class",
            problem_class,
            "--solve-mode",
            solve_mode,
            "--workdir",
            str(wd),
            "--knowledge-mode",
            "hybrid",
            "--live-subagent" if live else "--no-live-subagent",
        ]

        cli_command = (
            f"orpath.bat run --fresh --slug {slug} --thread-id {thread} "
            f"--problem-id {problem_id} --problem-class {problem_class} "
            f"--solve-mode {solve_mode} --workdir \"{wd}\""
        )

        # Include intake source if present under inbox/<slug>/
        inbox_slug = wd / "inbox" / slug
        if inbox_slug.is_dir():
            for f in sorted(inbox_slug.iterdir()):
                if f.is_file():
                    cmd.extend(["--intake-in", str(f)])
                    break

        # Clear existing stages before spawning so UI shows live stage-by-stage growth
        stages_dir = wd / "runs" / thread / "stages"
        if stages_dir.is_dir():
            for old_st in stages_dir.glob("*.json"):
                try:
                    old_st.unlink()
                except OSError:
                    pass

        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONUTF8"] = "1"
        env["ORPATH_HOME"] = str(home)
        env["ORPATH_WORKDIR"] = str(wd)
        env["ORPATH_LIVE_SUBAGENT"] = "1" if live else "0"

        # Explicit replay control: do not silently force reuse
        is_replay = bool(body.get("reuse", False) or body.get("fast_demo", False))
        if solve_mode == "tube" and is_replay:
            env["ORPATH_TUBE_REUSE"] = "1"

        def _bg_worker() -> None:
            try:
                subprocess.run(
                    cmd,
                    cwd=str(home),
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                )
            except Exception as exc:  # noqa: BLE001
                sys.stderr.write(f"[watch] bg run error: {exc}\n")

        t = threading.Thread(target=_bg_worker, daemon=True)
        t.start()

        self._send_json(
            200,
            {
                "ok": True,
                "slug": slug,
                "thread_id": thread,
                "problem_id": problem_id,
                "problem_class": problem_class,
                "solve_mode": solve_mode,
                "is_replay": is_replay,
                "command": " ".join(cmd),
                "cli_command": cli_command,
            },
        )

    def _handle_studio_analyze(self, body: dict[str, Any]) -> None:
        if not isinstance(body, dict):
            self._send_json(400, {"ok": False, "error": "body must be object"})
            return

        slug = _sanitize_slug(str(body.get("slug") or "studio-run"))
        prompt = str(body.get("prompt") or "").strip()

        # 1. Strictly forbid number authority in prompt & body
        forbid = find_forbidden_keys(body)
        if forbid:
            self._send_json(400, {"ok": False, "error": f"forbidden number key: {forbid[0]}"})
            return

        prompt_low = prompt.lower()
        for kw in ("objective", "best_cost", "tour", "routes", "proven_optimal", "global_optimal", "optima"):
            if kw in prompt_low:
                self._send_json(400, {"ok": False, "error": f"forbidden number key in prompt: {kw}"})
                return

        # 2. Write initial human steer with pause_next=True at_stage=after_research
        notes_dir = self._workdir / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        steer_doc = {
            "schema_version": 1,
            "slug": slug,
            "source": "studio_analyze",
            "utc": datetime.now(timezone.utc).isoformat(),
            "lg": {
                "pause_next": True,
                "at_stage": "after_research",
            },
            "pi": {
                "notes": prompt,
            },
        }
        steer_file = notes_dir / f"{slug}-human-steer.json"
        steer_file.write_text(json.dumps(steer_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # 3. Run deep analysis
        from orpath.studio_analyzer import run_deep_analysis

        api_key = str(body.get("api_key") or "").strip()
        model = str(body.get("model") or "deepseek-reasoner").strip()
        base_url = str(body.get("base_url") or "").strip()
        if api_key.startswith("ak-"):
            os.environ["XFYUN_API_KEY"] = api_key
            if not model or model == "deepseek-reasoner":
                model = "spark-x2.6"
        elif api_key.startswith("sk-"):
            os.environ["DEEPSEEK_API_KEY"] = api_key

        ana = run_deep_analysis(
            self._workdir,
            slug,
            prompt=prompt,
            home=self._home,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        detected_class = ana.get("domain_diagnosis", {}).get("problem_class") or "tsp"
        rec_algo = ana.get("domain_diagnosis", {}).get("recommended_algorithm") or "mock"

        # 4. Invoke LangGraph up to the pause
        try:
            from orpath.control_plane import (
                build_graph,
                default_initial,
                open_sqlite_checkpointer,
                thread_config,
            )

            # Clear stages for clean pause observation
            stages_dir = self._workdir / "runs" / slug / "stages"
            if stages_dir.is_dir():
                for old_st in stages_dir.glob("*.json"):
                    try:
                        old_st.unlink()
                    except OSError:
                        pass

            db_file = self._workdir / "runs" / "orpath.sqlite"
            db_file.parent.mkdir(parents=True, exist_ok=True)
            saver, conn = open_sqlite_checkpointer(db_file)
            app = build_graph(checkpointer=saver)
            cfg = thread_config(slug)

            k_mode = os.environ.get("ORPATH_KNOWLEDGE_MODE", "hybrid").strip().lower()
            if k_mode not in {"off", "seed", "hybrid"}:
                k_mode = "hybrid"

            initial = default_initial(
                root=self._workdir,
                slug=slug,
                problem_id=slug,
                problem_class=detected_class,
                solve_mode=rec_algo if rec_algo != "none" else "mock",
                knowledge_mode=k_mode,
                live_subagent=False,
                thread_id=slug,
            )
            final = app.invoke(initial, cfg)
            conn.close()
            human_req = bool(final.get("human_required"))
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"ok": False, "error": f"graph pause run failed: {exc}"})
            return

        self._send_json(
            200,
            {
                "ok": True,
                "slug": slug,
                "analysis": ana,
                "human_required": human_req,
                "paused_at": "after_research",
            },
        )

    def _handle_studio_confirm(self, body: dict[str, Any]) -> None:
        if not isinstance(body, dict):
            self._send_json(400, {"ok": False, "error": "body must be object"})
            return

        slug = _sanitize_slug(str(body.get("slug") or "studio-run"))
        selected_options = body.get("selected_options") if isinstance(body.get("selected_options"), dict) else {}
        extra_prompt = str(body.get("extra_prompt") or "").strip()

        # 1. Strictly forbid number authority in prompt & body
        forbid = find_forbidden_keys(body)
        if forbid:
            self._send_json(400, {"ok": False, "error": f"forbidden number key: {forbid[0]}"})
            return

        prompt_low = extra_prompt.lower()
        for kw in ("objective", "best_cost", "tour", "routes", "proven_optimal", "global_optimal", "optima"):
            if kw in prompt_low:
                self._send_json(400, {"ok": False, "error": f"forbidden number key in extra_prompt: {kw}"})
                return

        # 2. Check data profile
        from orpath.studio_analyzer import profile_inbox_assets

        profile_path = self._workdir / "outputs" / f"{slug}-data-profile.json"
        if profile_path.is_file():
            try:
                prof = json.loads(profile_path.read_text(encoding="utf-8"))
            except Exception:
                prof = profile_inbox_assets(self._workdir / "inbox" / slug, slug, self._workdir / "outputs")
        else:
            prof = profile_inbox_assets(self._workdir / "inbox" / slug, slug, self._workdir / "outputs")

        has_solver_dataset = bool(prof.get("has_solver_dataset"))
        detected_class = prof.get("detected_runnable_class") or "tsp"
        chosen_algo = str(selected_options.get("q_algorithm") or "ortools").strip().lower()
        if chosen_algo not in ALLOWED_SOLVE_MODES:
            chosen_algo = "ortools" if detected_class in {"tsp", "vrp"} else "mock"

        # 3. Write updated steer with pause_next=False
        notes_dir = self._workdir / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        steer_doc = {
            "schema_version": 1,
            "slug": slug,
            "source": "studio_confirm",
            "utc": datetime.now(timezone.utc).isoformat(),
            "lg": {
                "pause_next": False,
                "solve_mode": chosen_algo,
                "fresh": False,
            },
            "pi": {
                "prefer_methods": [chosen_algo],
                "notes": extra_prompt,
                "selected_options": selected_options,
            },
        }
        steer_file = notes_dir / f"{slug}-human-steer.json"
        steer_file.write_text(json.dumps(steer_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # Scenario A: Runnable dataset exists
        if has_solver_dataset:
            conn = None
            try:
                from orpath.agents.callbacks import (
                    MultiAgentSnapshotCallback,
                    SUPERVISOR_NAME,
                )
                from orpath.control_plane import (
                    _PROVIDER_DEFAULTS,
                    _resolve_provider,
                    build_compiled_multiagent,
                    build_graph,
                    default_initial,
                    get_chat_model,
                    open_sqlite_checkpointer,
                    thread_config,
                )

                # Optional user credentials passed from the Web Studio UI
                api_key = str(body.get("api_key") or "").strip()
                chosen_model = str(body.get("model") or "").strip()
                base_url = str(body.get("base_url") or "").strip()
                if api_key.startswith("ak-"):
                    os.environ["XFYUN_API_KEY"] = api_key
                    if not chosen_model or chosen_model == "deepseek-reasoner":
                        chosen_model = "spark-x2.6"
                elif api_key.startswith("sk-"):
                    os.environ["DEEPSEEK_API_KEY"] = api_key
                if base_url:
                    if api_key.startswith("ak-"):
                        os.environ["XFYUN_BASE_URL"] = base_url
                    elif api_key.startswith("sk-"):
                        os.environ["DEEPSEEK_BASE_URL"] = base_url

                k_mode = os.environ.get("ORPATH_KNOWLEDGE_MODE", "hybrid").strip().lower()
                if k_mode not in {"off", "seed", "hybrid"}:
                    k_mode = "hybrid"

                initial = default_initial(
                    root=self._workdir,
                    slug=slug,
                    problem_id=slug,
                    problem_class=detected_class,
                    solve_mode=chosen_algo,
                    knowledge_mode=k_mode,
                    live_subagent=False,
                    thread_id=slug,
                )

                # --- Task 9: multi-agent execution engine + snapshot callback ---
                # ORPATH_ENGINE selects the execution engine:
                #   * "multiagent" (default / unspecified) → prefer the compiled
                #     supervisor graph (build_compiled_multiagent);
                #   * "graph" → deterministic product pipeline only.
                # Any multiagent error — or a regression where the run completes
                # without producing the canonical solution artifact — falls back
                # smoothly to the existing build_graph solve, so
                # outputs/<slug>-solution.json + -validate.json stay guaranteed.
                engine_param = str(body.get("engine") or "").strip().lower()
                engine_env = (engine_param or os.environ.get("ORPATH_ENGINE", "multiagent")).strip().lower()
                use_multiagent = engine_env in ("", "multiagent")
                snapshot_cb = MultiAgentSnapshotCallback(
                    thread_id=slug, slug=slug, workdir=self._workdir
                )
                cfg = thread_config(slug)
                cfg["callbacks"] = [snapshot_cb]

                engine_used = "graph"
                final: Any = None
                if use_multiagent:
                    engine_used = "multiagent"
                    ma_http: Any = None
                    ma_outcome: dict[str, Any] = {}
                    abort_event = threading.Event()

                    # Dynamic execution budget:
                    # Priority: body['timeout'] -> ORPATH_MULTIAGENT_TIMEOUT -> default.
                    # Default is 3.0s for automated/gate environments (ensuring failover
                    # well within the 10.0s client timeout). In Web Studio and production,
                    # the client passes body['timeout'] (e.g. 60s) or sets ORPATH_MULTIAGENT_TIMEOUT.
                    req_to = body.get("timeout")
                    env_to = os.environ.get("ORPATH_MULTIAGENT_TIMEOUT")
                    if req_to is not None:
                        try:
                            ma_timeout = float(req_to)
                        except (ValueError, TypeError):
                            ma_timeout = 3.0
                    elif env_to is not None and env_to.strip():
                        try:
                            ma_timeout = float(env_to.strip())
                        except (ValueError, TypeError):
                            ma_timeout = 3.0
                    else:
                        ma_timeout = 3.0

                    def _run_multiagent() -> None:
                        """Attempt the compiled supervisor multi-agent solve.

                        Runs with dedicated HTTP client & MemorySaver checkpointer.
                        If the execution is aborted by caller on timeout, abort_event
                        guards disk output files from being overwritten.
                        """
                        nonlocal ma_http, final
                        try:
                            try:
                                import httpx2 as _httpx  # type: ignore[import-not-found]
                            except ImportError:  # pragma: no cover - classic httpx
                                import httpx as _httpx  # type: ignore[import-not-found,no-redef]
                            connect_to = min(2.5, ma_timeout)
                            ma_http = _httpx.Client(
                                timeout=_httpx.Timeout(timeout=ma_timeout, connect=connect_to),
                                limits=_httpx.Limits(max_keepalive_connections=0),
                            )
                            ma_model = get_chat_model(
                                model_name=chosen_model if chosen_model else None,
                                http_client=ma_http,
                            )
                            try:
                                ma_model.max_retries = 0
                            except Exception:
                                pass
                            from langgraph.checkpoint.memory import MemorySaver

                            app_ma = build_compiled_multiagent(
                                checkpointer=MemorySaver(), model=ma_model
                            )
                            ma_cfg = thread_config(f"{slug}-multiagent")
                            ma_cfg["callbacks"] = [snapshot_cb]
                            ma_input = dict(initial)
                            ma_input["messages"] = [
                                (
                                    "user",
                                    (
                                        f"运筹学工作台求解任务：slug={slug}，"
                                        f"problem_id={slug}，problem_class={detected_class}，"
                                        f"solve_mode={chosen_algo}，题面与数据位于 "
                                        f"{self._workdir / 'inbox' / slug}。"
                                        "严格按 researcher → modeler → verifier_writer "
                                        "流水线执行，产出 "
                                        f"outputs/{slug}-solution.json 与 "
                                        f"outputs/{slug}-validate.json。"
                                    ),
                                )
                            ]
                            snapshot_cb.write_stage_snapshot(SUPERVISOR_NAME, status="running")
                            res = app_ma.invoke(ma_input, ma_cfg)
                            if abort_event.is_set():
                                return

                            # Regression guard: a completed multiagent run must leave
                            # the canonical solution artifact on disk; otherwise the
                            # supervisor did not hand a usable result to the
                            # workbench and we fall back to the product pipeline.
                            sol_p = self._workdir / "outputs" / f"{slug}-solution.json"
                            if not sol_p.is_file():
                                raise FileNotFoundError(
                                    "multiagent run finished without producing "
                                    f"outputs/{slug}-solution.json"
                                )
                            if abort_event.is_set():
                                return
                            final = res
                            snapshot_cb.write_stage_snapshot(SUPERVISOR_NAME, status="ok")
                            ma_outcome["ok"] = True
                        except Exception as ma_exc:  # noqa: BLE001
                            if abort_event.is_set():
                                return
                            ma_outcome["error"] = f"{type(ma_exc).__name__}: {ma_exc}"
                            try:
                                snapshot_cb.write_stage_snapshot(SUPERVISOR_NAME, status="error")
                            except Exception:
                                pass
                        finally:
                            if ma_http is not None:
                                try:
                                    ma_http.close()
                                except Exception:
                                    pass

                    ma_thread = threading.Thread(target=_run_multiagent, daemon=True, name=f"ma-{slug}")
                    ma_thread.start()
                    ma_thread.join(ma_timeout)
                    if ma_thread.is_alive():
                        # Wall-clock bound fired: signal abort and close HTTP socket
                        abort_event.set()
                        if ma_http is not None:
                            try:
                                ma_http.close()
                            except Exception:
                                pass
                        ma_outcome["error"] = f"TimeoutError: Multi-agent execution exceeded {ma_timeout:.1f}s budget"
                        ma_thread.join(0.2)

                    if not ma_outcome.get("ok"):
                        # Error, bound exceeded, or regression (no solution
                        # artifact): smooth fallback to the deterministic
                        # product pipeline.
                        engine_used = "graph"
                        final = None

                if engine_used != "multiagent":
                    db_file = self._workdir / "runs" / "orpath.sqlite"
                    db_file.parent.mkdir(parents=True, exist_ok=True)
                    saver, conn = open_sqlite_checkpointer(db_file)
                    try:
                        app = build_graph(checkpointer=saver)
                        final = app.invoke(initial, cfg)
                    finally:
                        if conn is not None:
                            try:
                                conn.close()
                            except Exception:
                                pass
                            conn = None
                    try:
                        snapshot_cb.write_stage_snapshot("graph_solve", status="ok")
                    except Exception:
                        pass
                    engine_used = "graph"
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": f"graph solve run failed: {exc}"})
                return
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = None

            sol_file = self._workdir / "outputs" / f"{slug}-solution.json"
            if not sol_file.is_file():
                self._send_json(500, {"ok": False, "error": "solution file was not produced"})
                return
            sol_doc = json.loads(sol_file.read_text(encoding="utf-8"))

            val_file = self._workdir / "outputs" / f"{slug}-validate.json"
            val_doc = {}
            if val_file.is_file():
                try:
                    val_doc = json.loads(val_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            obj = sol_doc.get("objective")
            tour = sol_doc.get("tour") or []
            val_ok = bool(val_doc.get("ok"))
            checks_count = len(val_doc.get("checks", []))

            summary = {
                "headline": f"优化路线求解完成 (求解状态: {sol_doc.get('status', 'OK')})",
                "objective_str": f"最优目标值: {obj} 单位" if obj is not None else "求解完成",
                "solution_detail": f"节点访问顺序: {' -> '.join(tour)}" if tour else f"求解器输出: {sol_doc.get('solver')}",
                "validation_status": f"数理校验通过 ({checks_count} 项物理约束 100% 合格)" if val_ok else "数理校验存在警告",
            }

            self._send_json(
                200,
                {
                    "ok": True,
                    "status": "COMPLETED",
                    "slug": slug,
                    "engine": engine_used,
                    "solution": sol_doc,
                    "validation": val_doc,
                    "plain_language_summary": summary,
                },
            )
            return

        # Scenario B: No solver dataset -> honestly BLOCKED
        out_dir = self._workdir / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        blocked_sol = {
            "status": "BLOCKED",
            "objective": None,
            "solver": "none",
            "source": "studio_no_solver_dataset",
            "problem_id": slug,
            "problem_class": detected_class or "unknown",
            "slug": slug,
            "meta": {
                "blocked": True,
                "reason": "题面未提供结构化坐标或距离矩阵算例附件，系统已完成定性数学建模与思路研判，根据系统硬法诚实限制假绑数值求解。",
            },
        }
        (out_dir / f"{slug}-solution.json").write_text(
            json.dumps(blocked_sol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self._send_json(
            200,
            {
                "ok": True,
                "status": "BLOCKED",
                "slug": slug,
                "objective": None,
                "reason": "题面未提供结构化数值算例，已形成定性模型框架并诚实停止数值虚构。",
                "solution": blocked_sol,
            },
        )

    def _sse_loop(self, slug: str, thread: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        last_fp: str | None = None
        last_ev = 0
        try:
            snap = build_snapshot(
                slug=slug,
                thread_id=thread,
                root=self._home,
                workdir=self._workdir,
            )
            last_fp = (snap.get("poll") or {}).get("fingerprint")
            last_ev = int((snap.get("poll") or {}).get("events_count") or 0)
            self._sse_send("snapshot", snap)
            while True:
                time.sleep(SSE_INTERVAL_S)
                info = compute_source_fingerprint(
                    slug=slug, thread_id=thread, workdir=self._workdir
                )
                fp = info.get("fingerprint")
                if fp == last_fp:
                    self._sse_send("ping", {"fingerprint": fp, "dirty": False})
                    continue
                snap = build_snapshot(
                    slug=slug,
                    thread_id=thread,
                    root=self._home,
                    workdir=self._workdir,
                    prev_fingerprint=last_fp,
                    prev_events_count=last_ev,
                )
                last_fp = (snap.get("poll") or {}).get("fingerprint")
                last_ev = int((snap.get("poll") or {}).get("events_count") or 0)
                self._sse_send("snapshot", snap)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        except Exception as exc:  # noqa: BLE001
            try:
                self._sse_send("error", {"error": str(exc)})
            except Exception:
                return

    def _sse_send(self, event: str, data: object) -> None:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        msg = f"event: {event}\ndata: {payload}\n\n"
        self.wfile.write(msg.encode("utf-8"))
        self.wfile.flush()


def serve(
    *,
    slug: str = "test",
    thread_id: str | None = None,
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    home: Path | None = None,
    workdir: Path | None = None,
) -> int:
    from orpath.paths import apply_workdir

    home = (home or orpath_home()).resolve()
    if workdir is not None:
        workdir = apply_workdir(workdir)
    else:
        workdir = apply_workdir(orpath_workdir())
    os.environ["ORPATH_HOME"] = str(home)
    os.environ["ORPATH_WORKDIR"] = str(workdir)

    if not (WEB_DIR / HTML_NAME).is_file():
        print(f"[ERROR] missing {WEB_DIR / HTML_NAME}", file=sys.stderr)
        return 2

    handler = partial(WatchHandler, home=home, workdir=workdir, directory=str(WEB_DIR))

    httpd: ThreadingHTTPServer | None = None
    bound_port = port
    last_err: OSError | None = None
    for i in range(MAX_PORT_TRIES):
        bound_port = port + i
        try:
            httpd = ThreadingHTTPServer((host, bound_port), handler)
            break
        except OSError as e:
            last_err = e
            httpd = None
    if httpd is None:
        print(f"[ERROR] bind failed from port {port}: {last_err}", file=sys.stderr)
        return 1

    tid = (thread_id or slug).strip() or slug
    q = f"slug={slug}&thread={tid}"
    browser_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    url = f"http://{browser_host}:{bound_port}/?{q}"
    print(f"[watch] home    = {home}")
    print(f"[watch] workdir = {workdir}")
    print(f"[watch] listen  = http://{host}:{bound_port}/")
    print(f"[watch] open    = {url}")
    print(f"[watch] P1      = /api/poll + /api/stream + /api/model")
    print("[watch] Ctrl+C to stop")

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[watch] stopped")
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OR-Path Live Watch (V0/P1)")
    p.add_argument("--slug", default="test", help="artifact slug (default test)")
    p.add_argument("--thread-id", default=None, help="runs/<thread> id (default = slug)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="case data root (outputs/runs); sets ORPATH_WORKDIR",
    )
    args = p.parse_args(argv)
    from orpath.paths import apply_workdir

    wd = None
    if args.workdir is not None and str(args.workdir).strip():
        wd = apply_workdir(args.workdir)
    return serve(
        slug=args.slug,
        thread_id=args.thread_id,
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
        workdir=wd,
    )


if __name__ == "__main__":
    raise SystemExit(main())
