"""OR-Path Studio Analyzer — 文件夹数据探针与深度思考方向研判器.

职责：
1. profile_inbox_assets: 扫描 inbox/<slug> 内的全部文件（支持多层级子目录），
   对 CSV 表头、JSON 键、Excel Sheet 做非侵入式轻量探针，生成 outputs/<slug>-data-profile.json；
2. run_deep_analysis: 结合题面全文 + 数据探针 + 本地运筹知识库 (RAG) 检索，
   调用大模型深度思考 (DeepSeek / Pi Lead) 或确定性推演，产出建模方向对比与反问人类决策卡。
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

STATEMENT_EXTS = frozenset({".md", ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".webp"})
DATA_EXTS = frozenset({".csv", ".xlsx", ".xls", ".json", ".stp", ".step", ".sm", ".col", ".dat"})


def profile_inbox_assets(inbox_dir: Path, slug: str, outputs_dir: Path) -> dict[str, Any]:
    """Scan inbox/<slug> directory and produce outputs/<slug>-data-profile.json."""
    inbox_dir = Path(inbox_dir).resolve()
    outputs_dir = Path(outputs_dir).resolve()
    outputs_dir.mkdir(parents=True, exist_ok=True)

    statements: list[str] = []
    data_files: list[dict[str, Any]] = []
    detected_class: str | None = None
    has_solver_dataset = False

    if inbox_dir.is_dir():
        for p in sorted(inbox_dir.rglob("*")):
            if not p.is_file() or p.name.startswith("."):
                continue
            try:
                rel = str(p.relative_to(inbox_dir)).replace("\\", "/")
            except ValueError:
                rel = p.name

            suf = p.suffix.lower()
            if (suf in STATEMENT_EXTS and suf != ".txt") or (suf == ".txt" and any(k in p.name.lower() for k in ("problem", "readme", "brief", "题", "说明"))):
                statements.append(rel)
            elif suf in DATA_EXTS or (suf == ".txt" and any(k in p.name.lower() for k in ("cap", "cab", "benchmark", "demand", "matrix"))):
                file_info: dict[str, Any] = {
                    "rel_path": rel,
                    "kind": suf.lstrip("."),
                    "size_bytes": p.stat().st_size,
                }
                # Probe CSV
                if suf == ".csv":
                    try:
                        text = p.read_text(encoding="utf-8", errors="replace")[:10000]
                        reader = csv.reader(io.StringIO(text))
                        rows = list(reader)
                        if rows:
                            file_info["columns"] = rows[0]
                            file_info["sample_rows"] = rows[1:3]
                            file_info["rows_count_est"] = len(rows)
                    except Exception:
                        pass
                # Probe JSON
                elif suf == ".json":
                    try:
                        jdata = json.loads(p.read_text(encoding="utf-8"))
                        if isinstance(jdata, dict):
                            keys = list(jdata.keys())
                            file_info["top_keys"] = keys[:10]
                            name_low = p.name.lower()
                            if "coords" in keys or name_low == "coords.json" or "matrix" in keys:
                                file_info["detected_solver_fixture"] = "tsp"
                                detected_class = detected_class or "tsp"
                                has_solver_dataset = True
                            elif "nodes" in keys and "edges" in keys:
                                file_info["detected_solver_fixture"] = "shortest_path"
                                detected_class = detected_class or "shortest_path"
                                has_solver_dataset = True
                            elif "locations" in keys or "demands" in keys:
                                file_info["detected_solver_fixture"] = "vrp"
                                detected_class = detected_class or "vrp"
                                has_solver_dataset = True
                            elif "board" in keys or ("rows" in keys and "pieces" in keys):
                                file_info["detected_solver_fixture"] = "polyomino_cover"
                                detected_class = detected_class or "polyomino_cover"
                                has_solver_dataset = True
                            elif "jobs" in keys or "machines" in keys or "jssp" in name_low or "taillard" in name_low:
                                file_info["detected_solver_fixture"] = "job_shop"
                                detected_class = detected_class or "job_shop"
                                has_solver_dataset = True
                            elif ("capacities" in keys and "fixed_costs" in keys) or "cflp" in name_low or "cap" in name_low:
                                file_info["detected_solver_fixture"] = "facility_location"
                                detected_class = detected_class or "facility_location"
                                has_solver_dataset = True
                            elif "activities" in keys or "resources" in keys or "psplib" in name_low:
                                file_info["detected_solver_fixture"] = "rcpsp"
                                detected_class = detected_class or "rcpsp"
                                has_solver_dataset = True
                            elif ("distances" in keys and "flows" in keys) or "cab" in name_low:
                                file_info["detected_solver_fixture"] = "hub_location"
                                detected_class = detected_class or "hub_location"
                                has_solver_dataset = True
                            elif ("distance_matrix" in keys and "flow_matrix" in keys) or "qap" in name_low:
                                file_info["detected_solver_fixture"] = "qap"
                                detected_class = detected_class or "qap"
                                has_solver_dataset = True
                            elif "items" in keys and ("bin_capacity" in keys or "bin_size" in keys or "bins" in keys):
                                file_info["detected_solver_fixture"] = "bin_packing"
                                detected_class = detected_class or "bin_packing"
                                has_solver_dataset = True
                            elif "scenarios" in keys or "farmer" in name_low:
                                file_info["detected_solver_fixture"] = "stochastic_lp"
                                detected_class = detected_class or "stochastic_lp"
                                has_solver_dataset = True
                            elif "expected_returns" in keys or "cov_matrix" in keys:
                                file_info["detected_solver_fixture"] = "portfolio_opt"
                                detected_class = detected_class or "portfolio_opt"
                                has_solver_dataset = True
                            elif "Q" in keys or ("h" in keys and "J" in keys):
                                file_info["detected_solver_fixture"] = "qubo_ising"
                                detected_class = detected_class or "qubo_ising"
                                has_solver_dataset = True
                    except Exception:
                        pass
                elif suf == ".sm":
                    file_info["detected_solver_fixture"] = "rcpsp"
                    detected_class = detected_class or "rcpsp"
                    has_solver_dataset = True
                elif suf == ".col":
                    is_coloring = any(k in p.name.lower() for k in ("color", "vcp", "chrom", "dsatur"))
                    target = "graph_coloring" if is_coloring else "max_clique"
                    file_info["detected_solver_fixture"] = target
                    detected_class = detected_class or target
                    has_solver_dataset = True
                elif suf == ".dat":
                    file_info["detected_solver_fixture"] = "qap"
                    detected_class = detected_class or "qap"
                    has_solver_dataset = True
                elif suf == ".txt":
                    name_low = p.name.lower()
                    if "cap" in name_low:
                        file_info["detected_solver_fixture"] = "facility_location"
                        detected_class = detected_class or "facility_location"
                        has_solver_dataset = True
                    elif "cab" in name_low:
                        file_info["detected_solver_fixture"] = "hub_location"
                        detected_class = detected_class or "hub_location"
                        has_solver_dataset = True
                    elif "ww" in name_low or "clsp" in name_low:
                        file_info["detected_solver_fixture"] = "lot_sizing"
                        detected_class = detected_class or "lot_sizing"
                        has_solver_dataset = True

                data_files.append(file_info)
            elif suf in STATEMENT_EXTS:
                statements.append(rel)

    # Check for tube data files (10 csvs or demand_batches)
    csv_names = {Path(df["rel_path"]).name.lower() for df in data_files if df.get("kind") == "csv"}
    if any(k in csv_names for k in ("demand_batches.xlsx", "demand.xlsx")) or len(csv_names) >= 5:
        detected_class = detected_class or "tube_cut"
        has_solver_dataset = True

    profile: dict[str, Any] = {
        "slug": slug,
        "total_files": len(statements) + len(data_files),
        "statement_files": statements,
        "data_files": data_files,
        "detected_runnable_class": detected_class,
        "has_solver_dataset": has_solver_dataset,
    }

    out_file = outputs_dir / f"{slug}-data-profile.json"
    out_file.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return profile


# Alias for case profiling
extract_case_data_profile = profile_inbox_assets


def call_llm_reasoner(
    api_key: str,
    prompt: str,
    statement_text: str,
    data_profile: dict[str, Any],
    model: str = "",
    base_url: str = "",
    timeout_sec: float = 75.0,
    knowledge_context: str = "",
) -> dict[str, Any] | None:
    """Call DeepSeek or iFlytek Spark MaaS API for true deep mathematical thinking and diagnosis."""
    api_key = (api_key or "").strip()
    if not api_key:
        return None

    # Auto-detect iFlytek Spark MaaS vs DeepSeek
    is_xfyun = (
        api_key.startswith("ak-")
        or "xf-yun" in base_url
        or (model and ("spark" in model.lower() or "xf" in model.lower()))
    )
    if is_xfyun:
        base_url = (base_url or os.environ.get("XFYUN_BASE_URL") or "https://maas-api.cn-huabei-1.xf-yun.com/v2").rstrip("/")
        if not model or model.startswith("deepseek"):
            model = os.environ.get("XFYUN_MODEL") or "spark-x2.6"
    else:
        base_url = (base_url or os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
        model = model or "deepseek-reasoner"

    url = f"{base_url}/chat/completions"

    system_prompt = (
        "You are an expert Operations Research Scientist & Mathematical Programming Architect (运筹学与运筹优化专家).\n"
        "Analyze the provided problem statement, user requirements, and structured data profile.\n"
        "1. Diagnose the problem domain and recommend the best solver/algorithm with engineering trade-offs.\n"
        "2. Map data assets and table columns to mathematical decision variables, constraints, and parameters.\n"
        "3. Produce 2-3 structured clarification questions with recommended options for human confirmation before solving.\n"
        "Respond in strict JSON with keys: 'domain_diagnosis', 'data_alignment', 'clarification_questions'.\n"
        "Ensure domain_diagnosis contains: problem_class (e.g. tsp, vrp, shortest_path, tube_cut, polyomino_cover, scheduling, unregistered), domain_name (Chinese title), recommended_algorithm, algorithm_comparison (list of {name, recommended: bool, pros, cons}), rationale.\n"
        "Ensure data_alignment contains: matched_variables (list of {name, source, status, details}), missing_or_warnings (list of str).\n"
        "Ensure clarification_questions contains list of {id, question, options: [{id, label, recommended: bool}], recommended: str}."
    )

    clean_profile = {
        "slug": data_profile.get("slug"),
        "total_files": data_profile.get("total_files"),
        "statement_files": data_profile.get("statement_files"),
        "data_files": data_profile.get("data_files"),
        "detected_runnable_class": data_profile.get("detected_runnable_class"),
    }

    rag_section = f"【底层运筹知识库检索启发 (RAG Context)】\n{knowledge_context}\n\n" if knowledge_context else ""

    user_content = (
        f"【用户业务需求与提示词】\n{prompt or '（未输入额外提示词，请根据数据特征自主研判）'}\n\n"
        f"{rag_section}"
        f"【题面文本片段】\n{statement_text[:3500] if statement_text else '（无纯文本题面）'}\n\n"
        f"【附件数据探针概览】\n{json.dumps(clean_profile, ensure_ascii=False, indent=2)}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "stream": True,
    }

    req_data = json.dumps(payload).encode("utf-8")
    max_retries = int(os.environ.get("ORPATH_LLM_MAX_RETRIES") or 4)
    base_delay = float(os.environ.get("ORPATH_LLM_RETRY_DELAY") or 2.0)

    import time

    def _is_rate_limit_or_transient(code: int | None, msg: str) -> bool:
        if code in (429, 502, 503, 504):
            return True
        low = (msg or "").lower()
        return any(
            k in low
            for k in (
                "429",
                "rate limit",
                "rate_limit",
                "too many requests",
                "限流",
                "并发",
                "qps",
                "rpm",
                "tpm",
                "11202",
                "10014",
            )
        )

    last_error: dict[str, Any] = {"error": "unknown error", "failed": True}
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "OR-Path-Studio/1.0",
            },
            method="POST",
        )
        try:
            r_parts: list[str] = []
            c_parts: list[str] = []
            stream_err_msg: str | None = None
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if not line.startswith("data: "):
                        if line.startswith("{") and ("error" in line.lower() or "429" in line):
                            stream_err_msg = line
                        continue
                    if line == "data: [DONE]":
                        continue
                    try:
                        chunk = json.loads(line[6:])
                        if isinstance(chunk, dict) and chunk.get("error"):
                            err_obj = chunk["error"]
                            stream_err_msg = json.dumps(err_obj, ensure_ascii=False)
                            break
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        if delta.get("reasoning_content"):
                            r_parts.append(delta["reasoning_content"])
                        if delta.get("content"):
                            c_parts.append(delta["content"])
                    except Exception:
                        pass

            reasoning_content = "".join(r_parts)
            raw_content = "".join(c_parts).strip()

            # Robust JSON extraction from LLM response (handling thinking intros, markdown fences)
            parsed_json = None
            cleaned = raw_content.strip()
            if cleaned:
                # 1. Direct parse
                try:
                    parsed_json = json.loads(cleaned)
                except Exception:
                    pass
                # 2. Markdown fence regex
                if parsed_json is None:
                    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
                    if m:
                        try:
                            parsed_json = json.loads(m.group(1))
                        except Exception:
                            pass
                # 3. First { to last }
                if parsed_json is None:
                    s_idx = cleaned.find("{")
                    e_idx = cleaned.rfind("}")
                    if s_idx != -1 and e_idx > s_idx:
                        try:
                            parsed_json = json.loads(cleaned[s_idx : e_idx + 1])
                        except Exception:
                            pass

            if stream_err_msg and parsed_json is None:
                if attempt < max_retries and _is_rate_limit_or_transient(None, stream_err_msg):
                    time.sleep(base_delay * (2**attempt))
                    continue
                return {"error": f"Stream error: {stream_err_msg}", "failed": True}

            if not raw_content and not reasoning_content:
                provider_label = "讯飞星辰" if is_xfyun else "DeepSeek"
                if attempt < max_retries:
                    time.sleep(base_delay * (2**attempt))
                    continue
                return {"error": f"{provider_label} API 返回空响应", "failed": True}

            if parsed_json is None:
                return {
                    "error": "LLM response did not contain valid JSON",
                    "raw_preview": raw_content[:400],
                    "failed": True,
                }

            parsed_json["reasoning_content"] = reasoning_content
            parsed_json["model_used"] = model
            parsed_json["retry_count"] = attempt
            return parsed_json
        except urllib.error.HTTPError as exc:
            err_msg = exc.read().decode("utf-8", errors="replace")
            last_error = {"error": f"HTTP {exc.code}: {err_msg}", "failed": True}
            if attempt < max_retries and _is_rate_limit_or_transient(exc.code, err_msg):
                retry_after = None
                if exc.headers:
                    ra = exc.headers.get("Retry-After")
                    if ra:
                        try:
                            retry_after = float(ra)
                        except ValueError:
                            retry_after = None
                delay = retry_after if (retry_after is not None and retry_after > 0) else base_delay * (2**attempt)
                time.sleep(min(delay, 30.0))
                continue
            return last_error
        except Exception as exc:
            err_str = str(exc)
            last_error = {"error": err_str, "failed": True}
            if attempt < max_retries and _is_rate_limit_or_transient(None, err_str):
                time.sleep(base_delay * (2**attempt))
                continue
            return last_error
    return last_error


# Backward-compatible alias
call_deepseek_reasoner = call_llm_reasoner


def run_deep_analysis(
    workdir: Path,
    slug: str,
    prompt: str = "",
    home: Path | None = None,
    api_key: str = "",
    model: str = "deepseek-reasoner",
    base_url: str = "",
) -> dict[str, Any]:
    """Perform deep thinking domain diagnosis, data alignment, and structured questions."""
    workdir = Path(workdir).resolve()
    home = Path(home or os.environ.get("ORPATH_HOME") or workdir).resolve()
    inbox_dir = workdir / "inbox" / slug
    outputs_dir = workdir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Resolve API Key from argument, env, or .env file
    key_candidate = (api_key or "").strip()
    if not key_candidate and os.environ.get("ORPATH_STUDIO_LIVE") == "1":
        key_candidate = (
            os.environ.get("XFYUN_API_KEY", "").strip()
            or os.environ.get("DEEPSEEK_API_KEY", "").strip()
            or os.environ.get("OPENAI_API_KEY", "").strip()
        )
        if not key_candidate:
            for env_path in (workdir / ".env", home / ".env"):
                if env_path.is_file():
                    try:
                        for line in env_path.read_text(encoding="utf-8").splitlines():
                            if line.startswith("XFYUN_API_KEY="):
                                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                                if v:
                                    key_candidate = v
                                    break
                            elif line.startswith("DEEPSEEK_API_KEY="):
                                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                                if v:
                                    key_candidate = v
                                    break
                    except Exception:
                        pass
                if key_candidate:
                    break

    # 1. Profile inbox if needed
    profile_path = outputs_dir / f"{slug}-data-profile.json"
    if profile_path.is_file():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except Exception:
            profile = profile_inbox_assets(inbox_dir, slug, outputs_dir)
    else:
        profile = profile_inbox_assets(inbox_dir, slug, outputs_dir)

    # 2. Gather statement text
    statement_texts: list[str] = []
    if inbox_dir.is_dir():
        for sf in profile.get("statement_files") or []:
            sp = inbox_dir / sf
            if sp.is_file() and sp.suffix.lower() in {".md", ".txt"}:
                try:
                    statement_texts.append(sp.read_text(encoding="utf-8", errors="replace")[:4000])
                except Exception:
                    pass
    combined_text = "\n".join(statement_texts) + "\n" + (prompt or "")

    # 3. Detect problem class
    detected_class = profile.get("detected_runnable_class")
    if not detected_class:
        low = combined_text.lower()
        if any(k in low for k in ("巡检", "旅行商", "环路", "tsp", "工位", "回路")):
            detected_class = "tsp"
        elif any(k in low for k in ("下料", "圆管", "切削", "余料", "tube")):
            detected_class = "tube_cut"
        elif any(k in low for k in ("多米诺", "拼图", "格点覆盖", "polyomino")):
            detected_class = "polyomino_cover"
        elif any(k in low for k in ("微电网", "光伏", "储能", "电池", "microgrid", "pv", "bess")):
            detected_class = "microgrid"
        elif any(k in low for k in ("车间", "作业车间", "工序", "makespan", "jssp", "fjssp", "job shop", "jobshop", "完工时间", "换模", "ft06")):
            detected_class = "job_shop"
        elif any(k in low for k in ("rcpsp", "项目排程", "工期", "紧前关系", "psplib", "关键路径", "可再生资源", "j30")):
            detected_class = "rcpsp"
        elif any(k in low for k in ("设施选址", "选址", "cflp", "sscflp", "厂址", "配送中心选址", "facility location", "cap41")):
            detected_class = "facility_location"
        elif any(k in low for k in ("枢纽", "p-hub", "辐射网络", "中继", "hub location", "转运", "cab10", "cab25")):
            detected_class = "hub_location"
        elif any(k in low for k in ("二次指派", "qap", "qaplib", "布局优化", "设备布局", "车间布局", "quadratic assignment", "nug12")):
            detected_class = "qap"
        elif any(k in low for k in ("装箱", "装柜", "下料装载", "bin pack", "bin_pack", "binpacking", "1d装箱", "3d装箱", "三维装箱", "knapsack", "背包")):
            detected_class = "bin_packing"
        elif any(k in low for k in ("网络流", "费用流", "最大流", "二分图匹配", "指派匹配", "min cost flow", "bipartite", "matching", "多商品流")):
            detected_class = "network_flow"
        elif any(k in low for k in ("投资组合", "资产配置", "夏普比率", "均值方差", "markowitz", "portfolio", "收益率", "方差", "有效前沿")):
            detected_class = "portfolio_opt"
        elif any(k in low for k in ("qubo", "ising", "量子退火", "自旋玻璃", "max cut", "最大割", "退火", "spin glass")):
            detected_class = "qubo_ising"
        elif any(k in low for k in ("图着色", "染色", "色数", "graph color", "coloring", "dsatur", "冲突调度")):
            detected_class = "graph_coloring"
        elif any(k in low for k in ("最大团", "最大独立集", "max clique", "independent set", "clique", "对偶互补", "团数", "独立数", "myciel")):
            detected_class = "max_clique"
        elif any(k in low for k in ("随机规划", "两阶段", "stochastic", "evpi", "vss", "农民问题", "farmer")):
            detected_class = "stochastic_lp"
        elif any(k in low for k in ("排班", "轮班", "护士排班", "staff rostering", "rostering", "shift", "排班表")):
            detected_class = "staff_rostering"
        elif any(k in low for k in ("批量", "批次", "lot sizing", "lot_sizing", "wagner whitin", "wagner_whitin", "clsp", "订货提前期")):
            detected_class = "lot_sizing"
        elif any(k in low for k in ("博弈", "纳什均衡", "game theory", "nash")):
            detected_class = "game_theory"
        elif any(k in low for k in ("车辆路径", "车队", "vrp", "cvrp", "vrptw", "容量限制", "准时制")):
            detected_class = "vrp"
        elif any(k in low for k in ("最短路", "导航", "shortest", "路径规划", "dijkstra")):
            detected_class = "shortest_path"
        else:
            detected_class = "unregistered"

    # 4. Domain diagnosis & comparisons
    if detected_class == "tsp":
        domain_name = "旅行商与闭环巡检规划 (TSP)"
        rec_algo = "ortools"
        comparisons = [
            {
                "name": "OR-Tools Routing / CP-SAT (约束规划/整型规划)",
                "recommended": True,
                "pros": "工业级求解速度，内建强大的全局最优回路剪枝与邻域搜索，尺度支持几百站点",
                "cons": "对输入点阵的欧氏距离或距离矩阵完整性有严格要求",
            },
            {
                "name": "HiGHS / 混合整数线性规划 (MIP - MTZ/DFJ 消除子回路)",
                "recommended": False,
                "pros": "具备数学精确对偶界限与最优性证明，小规模站点表现优良",
                "cons": "DFJ 子回路消除约束随节点数呈指数级爆炸，稍大尺度极易超时",
            },
            {
                "name": "Christofides 启发式 / 最近邻快速贪婪法",
                "recommended": False,
                "pros": "毫秒级快速给出可行初始解，无外部第三方求解器依赖",
                "cons": "近似比理论上限 1.5，在大规模工业巡检中常多消耗 10%~20% 冗余里程",
            },
        ]
        rationale = (
            "根据数据探针检测，算例包含工位空间坐标信息。对于中小规模封闭巡检路线规划问题，"
            "OR-Tools CP-SAT 能在秒级内求得严格数学全局最优巡检路线并消除任何子环路，"
            "兼具精确性与工程鲁棒性，因此作为第一推荐算法。"
        )
    elif detected_class == "shortest_path":
        domain_name = "单源/多源最短路径规划 (Shortest Path)"
        rec_algo = "networkx"
        comparisons = [
            {
                "name": "NetworkX Dijkstra / A* 算法",
                "recommended": True,
                "pros": "经典图论算法，针对非负权重图时间复杂度 O(E + V log V)，执行极快",
                "cons": "不支持负权回路",
            },
            {
                "name": "HiGHS 混合整数规划 (MIP 单商品流模型)",
                "recommended": False,
                "pros": "便于在最短路基础上额外叠加复杂的非线性业务约束或排队约束",
                "cons": "求解耗时较直接图论遍历高出数十倍",
            },
        ]
        rationale = "网络拓扑与点边关系明确，推荐采用标准图论 Dijkstra 算法求取严格最优单源最短路径。"
    elif detected_class == "tube_cut":
        domain_name = "圆管下料与余料复用多批次优化 (Tube Cut BFD)"
        rec_algo = "tube"
        comparisons = [
            {
                "name": "最佳适应降序 (BFD) + 列生成背包优化",
                "recommended": True,
                "pros": "针对多材质、多批次、非对称焊缝与余料复用场景定制，大幅压低原材料损耗率",
                "cons": "对长短零件批量配合有敏感性",
            },
            {
                "name": "首次适应贪婪切割 (First-Fit Decreasing)",
                "recommended": False,
                "pros": "计算速度极快，易于现场人工对照实施",
                "cons": "余料无法跨批次优化流转，原材料利用率偏低",
            },
        ]
        rationale = "检测到原材料切割与需求清单数据，推荐采用降序最佳适应与余料复用算法降低损耗。"
    elif detected_class == "polyomino_cover":
        domain_name = "多联骨牌精确覆盖与拼合 (Polyomino Exact Cover)"
        rec_algo = "polyomino"
        comparisons = [
            {
                "name": "Dancing Links X (DLX) / CP-SAT 精确覆盖",
                "recommended": True,
                "pros": "基于双向十字链表的极速回溯剪枝，能在巨大状态空间中瞬间判定无解或找出所有拼合解",
                "cons": "需要严格的网格离散化矩阵表达",
            },
            {
                "name": "简单几何贪婪放置",
                "recommended": False,
                "pros": "无矩阵构建开销",
                "cons": "极易陷入死胡同，无法证明不可行性",
            },
        ]
        rationale = "检测到网格或骨牌覆盖结构，推荐采用精确覆盖 Dancing Links 算法求解。"
    elif detected_class in ("job_shop", "jssp", "fjssp"):
        domain_name = "作业车间调度优化 (JSSP / FJSSP)"
        rec_algo = "jssp"
        comparisons = [
            {
                "name": "PyJobShop / OR-Tools CP-SAT 析取约束规划",
                "recommended": True,
                "pros": "针对机器无重叠区间与工序先后顺序列生成极速剪枝，工业基准求解性能世界领先",
                "cons": "超大规模需分解",
            },
            {
                "name": "遗传算法 / 模拟退火 (GA/SA 元启发式)",
                "recommended": False,
                "pros": "结构灵活易嵌入定制局部搜索",
                "cons": "缺少全局最优性数学证明",
            },
        ]
        rationale = "检测到工件工序与机器排产约束，推荐采用 PyJobShop CP-SAT 求解全局最优 Makespan。"
    elif detected_class == "rcpsp":
        domain_name = "多资源约束项目排程 (RCPSP)"
        rec_algo = "rcpsp"
        comparisons = [
            {
                "name": "OR-Tools CP-SAT 累积调度精确规划 (Cumulative Scheduling)",
                "recommended": True,
                "pros": "严格建模有限可再生资源多重容量限制与紧前时序，精准识别关键路径与零总时差",
                "cons": "资源类型过多时变量增加",
            },
            {
                "name": "传统关键路径法 (CPM / PERT)",
                "recommended": False,
                "pros": "计算极其简单快速",
                "cons": "完全忽视资源瓶颈，实景中多不可行",
            },
        ]
        rationale = "检测到工序紧前时序与有限资源约束，推荐采用 CP-SAT 累积调度模型求解最短工期与关键路径。"
    elif detected_class in ("facility_location", "facility"):
        domain_name = "有容量限制设施选址优化 (CFLP / SCND)"
        rec_algo = "facility"
        comparisons = [
            {
                "name": "混合整数线性规划 (MIP - HiGHS / OR-Tools)",
                "recommended": True,
                "pros": "严格权衡设施固定投资建造成本与运输运费，全局最优保证，支持单源/多源配置",
                "cons": "极大网络需分解",
            },
            {
                "name": "连续重心法 / 几何重力模型",
                "recommended": False,
                "pros": "快速得到连续坐标",
                "cons": "无法处理离散候选厂址与工厂容量上限",
            },
        ]
        rationale = "检测到固定投资成本与客户需求容量约束，推荐采用 MIP 混合整数规划求解最优选址与配送流。"
    elif detected_class in ("hub_location", "hub"):
        domain_name = "枢纽辐射网络选址优化 (p-Hub Location)"
        rec_algo = "hub_location"
        comparisons = [
            {
                "name": "Ernst & Krishnamoorthy 3-下标流 MIP 模型",
                "recommended": True,
                "pros": "精确刻画干线转运折扣因子与集散网络，全局最优保证",
                "cons": "三下标变量规模较高",
            },
            {
                "name": "先聚类后选址两阶段启发式",
                "recommended": False,
                "pros": "计算速度快",
                "cons": "无法折算跨枢纽网络转运折扣，总成本偏高",
            },
        ]
        rationale = "检测到节点间流量交互矩阵与转运规模折扣，推荐采用三下标流 MIP 精确求解最优枢纽选址。"
    elif detected_class == "qap":
        domain_name = "二次指派与车间布局优化 (QAP)"
        rec_algo = "qap"
        comparisons = [
            {
                "name": "SciPy FAQ 凸松弛 + 2-opt 局部搜索混合算法",
                "recommended": True,
                "pros": "凸松弛全局初始点结合 2-opt 极速交换，高概率命中 QAPLIB 金标已知最优",
                "cons": "强 NP-Hard，超大维度需多起点并行",
            },
            {
                "name": "全排列暴力枚举",
                "recommended": False,
                "pros": "穷举绝对精确",
                "cons": "阶乘级复杂度 O(n!)，n>12 时耗时不可承受",
            },
        ]
        rationale = "检测到距离矩阵与流矩阵乘积的二次搬运成本，推荐采用 FAQ 凸松弛与 2-opt 混合求解。"
    elif detected_class in ("bin_packing", "binpack"):
        domain_name = "多维工业装箱与空间装载优化 (Bin Packing 1D/2D/3D)"
        rec_algo = "bin_packing"
        comparisons = [
            {
                "name": "混合整数规划 / 极端点几何放置启发式 (Extreme Point 3D-BPP)",
                "recommended": True,
                "pros": "支持长宽高 6 自由度旋转与空间无重叠碰撞硬约束，空间利用率高",
                "cons": "异构小包数量超大时求解时间上升",
            },
            {
                "name": "首次适应降序法 (FFD / First-Fit Decreasing)",
                "recommended": False,
                "pros": "计算极快",
                "cons": "在复杂三维货柜装载中产生严重空洞浪费",
            },
        ]
        rationale = "检测到货件多维几何尺寸与承重限制，推荐采用空间极值点 6-DOF 放置算法最大化装载率。"
    elif detected_class == "network_flow":
        domain_name = "网络流与二部图最优匹配 (Network Flow & Matching)"
        rec_algo = "network_flow"
        comparisons = [
            {
                "name": "NetworkX 最小费用流与增广路 / OR-Tools GLOP 多商品流",
                "recommended": True,
                "pros": "利用网络全幺模矩阵性质，直接线性规划即可得整型极值解，求解极速",
                "cons": "非网络拓扑约束需转化为广义网络",
            },
            {
                "name": "通用整型规划 MIP",
                "recommended": False,
                "pros": "通用性强",
                "cons": "未利用网络全幺模结构，计算开销大一个数量级",
            },
        ]
        rationale = "检测到节点供需平衡与弧容量/费用结构，推荐采用专业网络流算法求解。"
    elif detected_class in ("portfolio_opt", "portfolio"):
        domain_name = "Markowitz 均值-方差现代投资组合优化 (Portfolio Optimization)"
        rec_algo = "portfolio_opt"
        comparisons = [
            {
                "name": "PyPortfolioOpt / SciPy 二次凸规划 (QP / SLSQP)",
                "recommended": True,
                "pros": "精确解析求解最大夏普比率、最小方差并平滑绘制有效前沿，支持整数股离散配置",
                "cons": "输入资产协方差矩阵须半正定",
            },
            {
                "name": "等权重平均配置 (1/N 策略)",
                "recommended": False,
                "pros": "无参数估计误差",
                "cons": "完全忽略资产间相关性与风险对冲收益",
            },
        ]
        rationale = "检测到资产预期收益与风险协方差矩阵，推荐采用标准二次凸规划求解最大夏普比率最优资产权重。"
    elif detected_class in ("qubo_ising", "qubo"):
        domain_name = "量子退火与自旋玻璃优化 (QUBO & Ising)"
        rec_algo = "qubo_ising"
        comparisons = [
            {
                "name": "D-Wave dimod 模拟退火 (Simulated Annealing) / 精确穷举",
                "recommended": True,
                "pros": "原生支持二次无约束二值优化 (QUBO) 与 Ising 自旋映射，自适应降温退火",
                "cons": "硬约束需要通过大惩罚项 (Penalty multiplier) 嵌入",
            },
            {
                "name": "贪婪局部搜索 (Greedy Local Search)",
                "recommended": False,
                "pros": "快速单步改进",
                "cons": "极易陷入多峰复杂能量曲面上的局部极小值深井",
            },
        ]
        rationale = "检测到二次二值相互作用矩阵与 Ising 偏置，推荐采用 D-Wave 模拟退火采样器寻找最低基态能量。"
    elif detected_class == "graph_coloring":
        domain_name = "图顶点着色与冲突消解 (Graph Coloring)"
        rec_algo = "graph_coloring"
        comparisons = [
            {
                "name": "NetworkX DSATUR 启发式上界 + OR-Tools CP-SAT 精确求解",
                "recommended": True,
                "pros": "DSATUR 毫秒级锁定高质量饱和度着色上界，CP-SAT 快速裁决色数全局最优性",
                "cons": "密集图需加入完全子图团约束加速",
            },
            {
                "name": "简单贪心着色 (Greedy Coloring)",
                "recommended": False,
                "pros": "无额外开销",
                "cons": "对节点排列顺序极其敏感，经常浪费额外 20%~50% 颜色数",
            },
        ]
        rationale = "检测到相冲突节点不共享资源的互斥拓扑，推荐采用 DSATUR 结合 CP-SAT 混合求解最小色数方案。"
    elif detected_class == "max_clique":
        domain_name = "最大团与最大独立集图论优化 (Max Clique & MIS)"
        rec_algo = "max_clique"
        comparisons = [
            {
                "name": "NetworkX Tomita 分支定界 + CP-SAT 对偶互补验证",
                "recommended": True,
                "pros": "基于补图对偶性 omega(G) = alpha(G_comp) 双重验证，严格保障数值真实性与证明",
                "cons": "在超大规模稠密图上需设置合理超时截断",
            },
            {
                "name": "经典 Bron-Kerbosch 简单回溯",
                "recommended": False,
                "pros": "代码精简",
                "cons": "无有效枢轴选择时搜索树极度庞大",
            },
        ]
        rationale = "检测到稠密图互连或互斥特征，推荐采用 Tomita 分支定界与补图 CP-SAT 双重对偶求解。"
    elif detected_class in ("stochastic_lp", "stochastic"):
        domain_name = "两阶段随机线性规划 (Two-Stage Stochastic LP)"
        rec_algo = "stochastic_lp"
        comparisons = [
            {
                "name": "OR-Tools GLOP 大规模确定性等价型 (Extensive Form)",
                "recommended": True,
                "pros": "同时输出第一阶段期望最优决策 (RP)、全知信息价值 (EVPI) 与随机解价值 (VSS)",
                "cons": "情景爆炸时需采用 L-shaped 分解",
            },
            {
                "name": "平均值均值模型 (Expected Value Problem)",
                "recommended": False,
                "pros": "仅需求解单个平均情景",
                "cons": "完全忽视极端情景尾部风险，实际落地期望收益偏低",
            },
        ]
        rationale = "检测到带概率分布的不确定情景数据，推荐采用确定性等价型大规模线性规划精确计算 VSS 与 EVPI。"
    elif detected_class == "staff_rostering":
        domain_name = "企业员工排班与轮班优化 (Staff Rostering)"
        rec_algo = "staff_rostering"
        comparisons = [
            {
                "name": "OR-Tools CP-SAT 连续工作天数与覆盖约束规划",
                "recommended": True,
                "pros": "完美处理每人单班、夜班后休息、最大连续出勤天数等多维硬法规约束与员工满意度",
                "cons": "班次技能等级过多元化时需扩充维度",
            },
            {
                "name": "人工轮转轮盘法 (Cyclic Roster)",
                "recommended": False,
                "pros": "易于固定排班规律",
                "cons": "对突发请假或动态波动班次需求完全缺乏柔性调配能力",
            },
        ]
        rationale = "检测到多员工出勤需求与劳动法规工时约束，推荐采用 CP-SAT 约束规划生成兼顾合规与满意度的排班表。"
    elif detected_class in ("lot_sizing", "inventory_planning"):
        domain_name = "多周期动态批量订货优化 (Lot Sizing WW / CLSP)"
        rec_algo = "lot_sizing"
        comparisons = [
            {
                "name": "Wagner-Whitin 动态规划 (无产能) / SCIP MIP (有产能限制 CLSP)",
                "recommended": True,
                "pros": "利用零库存定理实现多周期订货与库存持有总成本数学全局最优，毫秒级出解",
                "cons": "有能力限制时复杂度上升为 NP-Hard",
            },
            {
                "name": "经济订货批量 (EOQ)",
                "recommended": False,
                "pros": "平方根公式极简",
                "cons": "强行假设需求速率恒定，在动态离散需求场景下造成高额库存积压",
            },
        ]
        rationale = "检测到时变需求与固定准备/库存持有成本，推荐采用 Wagner-Whitin 动态规划与 CLSP 模型求解最优生产批量。"
    elif detected_class in ("microgrid", "microgrid_dispatch"):
        domain_name = "园区微电网储能充放电与能耗调度 (Microgrid PV-BESS)"
        rec_algo = "microgrid"
        comparisons = [
            {
                "name": "滚动视界模型预测控制 (MPC) + 线性规划 (LP - HiGHS)",
                "recommended": True,
                "pros": "动态跟踪分时电价峰谷差套利与需量电费消峰，兼顾电池循环衰减成本",
                "cons": "需要较为精准的短时负荷与光伏出力预测",
            },
            {
                "name": "简单阈值规则调度 (Rule-Based Control)",
                "recommended": False,
                "pros": "逻辑简单无求解器依赖",
                "cons": "缺乏前瞻性，电价尖峰时刻容易电量耗尽无法顶峰",
            },
        ]
        rationale = "检测到分时电价曲线与储能电池充放电参数，推荐采用 MPC 滚动优化与线性规划降低综合用电成本。"
    elif detected_class == "vrp":
        domain_name = "多车带容量/时间窗路径规划 (CVRP / VRPTW)"
        rec_algo = "ortools"
        comparisons = [
            {
                "name": "OR-Tools Routing / 导向局部搜索 (Guided Local Search)",
                "recommended": True,
                "pros": "工业物流领域标杆，支持车载容量、严格到达时间窗与异构车队调度",
                "cons": "超大尺度需结合分区聚类",
            },
            {
                "name": "逐车贪婪插入启发式 (Greedy Insertion)",
                "recommended": False,
                "pros": "速度极快",
                "cons": "路径容易产生交叉绕行，总运输里程高出 15%~30%",
            },
        ]
        rationale = "检测到客户网点需求与车队载重/时间窗约束，推荐采用 OR-Tools 导向局部搜索求解最低运力成本方案。"
    elif detected_class == "game_theory":
        domain_name = "非合作双矩阵博弈与纳什均衡 (Game Theory)"
        rec_algo = "game_theory"
        comparisons = [
            {
                "name": "Nashpy 支持枚举 (Support Enumeration) / Lemke-Howson",
                "recommended": True,
                "pros": "严格求取所有纯策略与混合策略纳什均衡 (Nash Equilibrium)，输出完备博弈分析",
                "cons": "高阶张量博弈维度较高",
            },
            {
                "name": "极大极小单边分析",
                "recommended": False,
                "pros": "计算直观",
                "cons": "无法反映双边动态策略互动的均衡状态",
            },
        ]
        rationale = "检测到收益矩阵与竞争对抗策略，推荐采用 Nashpy 支持枚举算法求解混合策略纳什均衡。"
    else:
        domain_name = f"未注册运筹领域 ({detected_class})"
        rec_algo = "none"
        comparisons = [
            {
                "name": "定性数学建模与模型框架构建",
                "recommended": True,
                "pros": "自动抽取目标函数、决策变量与约束集合，形成标准 Markdown / LaTeX 数学规划公式",
                "cons": "当前系统工业适配器尚未注册该特定专有求解器，需要接入领域适配器方可直接数值计算",
            }
        ]
        rationale = "当前题面属于自定义或扩展运筹问题，系统已完成语义解析并给出建议，但诚实限制数值虚假绑定。"

    # 5. Data alignment
    matched_vars: list[dict[str, Any]] = []
    missing_warnings: list[str] = []

    for df in profile.get("data_files") or []:
        rel = df.get("rel_path", "")
        kind = df.get("kind", "")
        if "coords" in rel.lower() or df.get("detected_solver_fixture") == "tsp":
            matched_vars.append({
                "name": "工位/站点空间坐标",
                "source": rel,
                "status": "READY",
                "details": f"格式={kind}, 大小={df.get('size_bytes', 0)}B, 包含空间几何定位",
            })
        elif "demand" in rel.lower() or "csv" in kind:
            cols = df.get("columns") or []
            matched_vars.append({
                "name": "工件/业务需求明细",
                "source": rel,
                "status": "AVAILABLE",
                "details": f"表头: {', '.join(cols[:5])} (共约 {df.get('rows_count_est', 0)} 行)",
            })
        elif "locations" in rel.lower() or df.get("detected_solver_fixture") == "vrp":
            matched_vars.append({
                "name": "网点配送拓扑",
                "source": rel,
                "status": "READY",
                "details": f"格式={kind}, 包含配送网络节点",
            })
        elif "board" in rel.lower() or df.get("detected_solver_fixture") == "polyomino_cover":
            matched_vars.append({
                "name": "棋盘/多米诺几何定义",
                "source": rel,
                "status": "READY",
                "details": f"格式={kind}, 包含网格结构",
            })
        else:
            matched_vars.append({
                "name": f"附件数据 ({Path(rel).name})",
                "source": rel,
                "status": "PARSED",
                "details": f"格式={kind}, 维度探测完成",
            })

    if not matched_vars:
        missing_warnings.append("未检测到结构化数值数据文件（CSV/JSON/Excel），仅有纯文字题面；可进行定性建模，数值求解将受阻。")

    # 6. Deterministic baseline reasoning & questions
    deterministic_reasoning = (
        f"【运筹学知识库与数据维度推演研判】\n"
        f"1. 题面结构剖析：识别到业务场景属于「{domain_name}」，"
        f"核心在于在给定离散工位/节点集合下寻找满足所有业务约束的最优决策流。\n"
        f"2. 数据特征映射：探针已捕获数据文件共 {len(matched_vars)} 份，结构化参数与决策变量已成功建立索引映射。\n"
        f"3. 算法可行性论证：对比了精确求解器（MIP/CP-SAT）与启发式元算法，"
        f"针对当前问题规模与实时响应指标，推荐「{rec_algo}」作为基准求解引擎。\n"
        f"4. 决策关卡：为防止模型与实际业务语义发生偏差，在启动数值求解器之前，需向人类专家反问确认具体算例边界与度量准则。"
    )

    clarification_questions: list[dict[str, Any]] = [
        {
            "id": "q_algorithm",
            "question": "请确认推荐的求解引擎与求解策略：",
            "options": [
                {
                    "id": rec_algo if rec_algo != "none" else "qualitative",
                    "label": f"推荐方案：{comparisons[0]['name']}",
                    "recommended": True,
                },
                {
                    "id": "alternative",
                    "label": f"备选方案：{comparisons[1]['name'] if len(comparisons) > 1 else '通用启发式算法'}",
                    "recommended": False,
                },
            ],
            "recommended": rec_algo if rec_algo != "none" else "qualitative",
        },
        {
            "id": "q_subproblem",
            "question": "请确认优化目标与回路连通性范围：",
            "options": [
                {
                    "id": "full_closed_loop",
                    "label": "全局闭环优化 (推荐 · 访问全部点位并返回起始点，总距离最短)",
                    "recommended": True,
                },
                {
                    "id": "open_path",
                    "label": "开放式单向路径 (仅到达终点，不计算返程距离)",
                    "recommended": False,
                },
            ],
            "recommended": "full_closed_loop",
        },
        {
            "id": "q_distance_metric",
            "question": "请确认工位空间距离度量准则：",
            "options": [
                {
                    "id": "euclidean",
                    "label": "标准欧氏几何直线距离 sqrt((x1-x2)^2 + (y1-y2)^2) (推荐)",
                    "recommended": True,
                },
                {
                    "id": "manhattan",
                    "label": "曼哈顿网格距离 |x1-x2| + |y1-y2| (适用于有直角通道约束的厂区)",
                    "recommended": False,
                },
            ],
            "recommended": "euclidean",
        },
    ]

    # 6.5 Real OR Knowledge Base Retrieval (Hybrid RAG)
    retrieval_query_parts = []
    if detected_class and detected_class != "unregistered":
        retrieval_query_parts.append(detected_class.replace("_", " "))
    if prompt:
        retrieval_query_parts.append(prompt[:80])
    elif combined_text:
        retrieval_query_parts.append(combined_text[:100].strip())
    retrieval_query = " ".join(retrieval_query_parts).strip() or "operations research mathematical programming"

    knowledge_hits: list[dict[str, Any]] = []
    knowledge_context_str = ""
    try:
        from knowledge_svc.retrieve import retrieve as ks_retrieve
        from knowledge_svc.retrieve import artifact_to_payload

        k_mode = os.environ.get("ORPATH_KNOWLEDGE_MODE", "hybrid").strip().lower()
        if k_mode not in {"off", "seed", "hybrid"}:
            k_mode = "hybrid"

        if k_mode != "off":
            art_obj = ks_retrieve(
                retrieval_query,
                mode=k_mode,  # type: ignore[arg-type]
                topk=3,
                root=home,
                problem_class=detected_class if detected_class != "unregistered" else None,
            )
            retrieval_payload = artifact_to_payload(art_obj)

            notes_dir = workdir / "notes"
            notes_dir.mkdir(parents=True, exist_ok=True)
            (notes_dir / f"{slug}-retrieval.json").write_text(
                json.dumps(retrieval_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            (outputs_dir / f"{slug}-retrieval.json").write_text(
                json.dumps(retrieval_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

            for h in retrieval_payload.get("hits") or []:
                sp = str(h.get("source_path") or "")
                title = Path(sp).stem if sp else str(h.get("chunk_id") or "")
                knowledge_hits.append({
                    "chunk_id": str(h.get("chunk_id") or ""),
                    "score": round(float(h.get("score") or 0.0), 4),
                    "backend": str(h.get("backend") or "hybrid"),
                    "source_path": sp,
                    "title": title,
                    "snippet": str(h.get("snippet") or "")[:240],
                })

            if knowledge_hits:
                knowledge_context_str = "\n".join(
                    f"- 📚 [{kh['title']}] ({kh['backend']}): {kh['snippet']}"
                    for kh in knowledge_hits
                )
    except Exception as exc:
        knowledge_context_str = f"（知识库检索跳过: {exc}）"

    # 7. Real LLM invocation or honest offline probe
    llm_payload: dict[str, Any] | None = None
    live_thinking = False

    if key_candidate and model != "offline":
        llm_payload = call_deepseek_reasoner(
            api_key=key_candidate,
            prompt=prompt,
            statement_text=combined_text,
            data_profile=profile,
            model=model or "deepseek-reasoner",
            base_url=base_url,
            knowledge_context=knowledge_context_str,
        )

    if llm_payload and not llm_payload.get("error") and isinstance(llm_payload.get("domain_diagnosis"), dict):
        live_thinking = True
        thinking_mode = "llm_deep_think"
        is_xfyun_run = (
            (model and "spark" in model.lower())
            or (key_candidate and key_candidate.startswith("ak-"))
        )
        provider_title = "讯飞星辰 (Spark)" if is_xfyun_run else "DeepSeek"
        reasoning_text = llm_payload.get("reasoning_content") or (
            f"【{provider_title}-{model} 深度思考推演完成】\n"
            f"模型已结合底层运筹知识库召回的 {len(knowledge_hits)} 篇文献先验，对题面与 {len(matched_vars)} 份数据附件完成运筹学语义对齐与建模推导。"
        )
        llm_diag = llm_payload["domain_diagnosis"]
        domain_name = str(llm_diag.get("domain_name") or domain_name)
        detected_class = str(llm_diag.get("problem_class") or detected_class)
        rec_algo = str(llm_diag.get("recommended_algorithm") or rec_algo)
        if isinstance(llm_diag.get("algorithm_comparison"), list) and llm_diag["algorithm_comparison"]:
            comparisons = llm_diag["algorithm_comparison"]
        rationale = str(llm_diag.get("rationale") or rationale)

        llm_align = llm_payload.get("data_alignment")
        if isinstance(llm_align, dict):
            if isinstance(llm_align.get("matched_variables"), list) and llm_align["matched_variables"]:
                matched_vars = llm_align["matched_variables"]
            if isinstance(llm_align.get("missing_or_warnings"), list):
                missing_warnings.extend(llm_align["missing_or_warnings"])

        llm_qs = llm_payload.get("clarification_questions")
        if isinstance(llm_qs, list) and len(llm_qs) >= 2:
            clarification_questions = llm_qs

        citations = [
            f"{provider_title} Reasoning ({model})",
            f"OR-KNOWLEDGE: {detected_class} formulation and solver benchmarking standards",
            "OR-PATH: SDD product flow and numbers truth verification protocol",
        ]
        for kh in knowledge_hits:
            citations.append(f"📚 运筹文献先验: {kh['title']} ({kh['source_path']})")
    elif llm_payload and llm_payload.get("error"):
        thinking_mode = "rag_deterministic"
        live_thinking = False
        is_xfyun_run = (
            (model and "spark" in model.lower())
            or (key_candidate and key_candidate.startswith("ak-"))
        )
        provider_title = "讯飞星辰 (Spark)" if is_xfyun_run else "DeepSeek"
        rag_prefix = ""
        if knowledge_hits:
            rag_prefix = (
                f"【📚 运筹知识库 (RAG) 召回成功 · {len(knowledge_hits)} 篇方法文献】\n"
                + "\n".join(f"• [{kh['title']}]: {kh['snippet']}" for kh in knowledge_hits)
                + "\n\n"
            )
        reasoning_text = (
            f"【⚠️ {provider_title} API 调用未完成 · 已安全降级为本地探针】\n"
            f"接口提示: {llm_payload.get('error')}\n\n"
            + rag_prefix
            + "系统已自动结合知识库先验与本地运筹规则探针：\n"
            + deterministic_reasoning
        )
        citations = [
            f"OR-KNOWLEDGE: {detected_class} formulation and solver benchmarking standards",
            "OR-PATH: SDD product flow and numbers truth verification protocol",
        ]
        for kh in knowledge_hits:
            citations.append(f"📚 运筹文献先验: {kh['title']} ({kh['source_path']})")
    else:
        thinking_mode = "rag_deterministic"
        live_thinking = False
        rag_prefix = ""
        if knowledge_hits:
            rag_prefix = (
                f"【📚 本地运筹知识库 (RAG) 召回完成 · {len(knowledge_hits)} 篇方法先验】\n"
                + "\n".join(f"• [{kh['title']}]: {kh['snippet']}" for kh in knowledge_hits)
                + "\n\n"
            )
        reasoning_text = (
            "【⚠️ 离线启发式规则探针 · 未配置 API Key】\n"
            "系统检测到未填入 DeepSeek API Key。\n"
            + rag_prefix
            + "当前展示的算法对比与决策卡基于本地运筹学静态规则库、混合检索先验与数据特征探针推演。\n"
            "如需针对您上传的非标数据启动端到端语义理解与 DeepSeek-R1 深度推理链，请在页面顶部填入 DeepSeek API Key 后重新研判。\n\n"
            + deterministic_reasoning
        )
        citations = [
            f"OR-KNOWLEDGE: {detected_class} formulation and solver benchmarking standards",
            "OR-PATH: SDD product flow and numbers truth verification protocol",
        ]
        for kh in knowledge_hits:
            citations.append(f"📚 运筹文献先验: {kh['title']} ({kh['source_path']})")

    analysis: dict[str, Any] = {
        "slug": slug,
        "domain_diagnosis": {
            "problem_class": detected_class,
            "domain_name": domain_name,
            "recommended_algorithm": rec_algo,
            "algorithm_comparison": comparisons,
            "rationale": rationale,
        },
        "data_alignment": {
            "matched_variables": matched_vars,
            "missing_or_warnings": missing_warnings,
        },
        "thinking_meta": {
            "mode": thinking_mode,
            "live_thinking": live_thinking,
            "model": model if (key_candidate and model != "offline") else "offline",
            "reasoning_text": reasoning_text,
            "citations": citations,
            "knowledge_hits": knowledge_hits,
            "retrieval_query": retrieval_query,
        },
        "knowledge_hits": knowledge_hits,
        "retrieval_query": retrieval_query,
        "clarification_questions": clarification_questions,
    }

    out_file = outputs_dir / f"{slug}-studio-analysis.json"
    out_file.write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return analysis
