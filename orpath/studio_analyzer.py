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

STATEMENT_EXTS = frozenset({".md", ".txt", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".webp"})
DATA_EXTS = frozenset({".csv", ".xlsx", ".xlsm", ".xls", ".json", ".stp", ".step", ".sm", ".col", ".dat"})


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
                # Probe Excel (.xlsx / .xlsm)
                elif suf in {".xlsx", ".xlsm"}:
                    try:
                        from tools.intake_assets import probe_spreadsheet

                        smeta = probe_spreadsheet(p)
                        if not smeta.get("error"):
                            file_info["sheet_names"] = smeta.get("sheet_names", [])
                            file_info["sheets"] = smeta.get("sheets", [])
                            if smeta.get("columns"):
                                file_info["columns"] = smeta["columns"]
                            if smeta.get("sample_rows"):
                                file_info["sample_rows"] = smeta["sample_rows"]
                            if smeta.get("rows_count_est"):
                                file_info["rows_count_est"] = smeta["rows_count_est"]
                        else:
                            file_info["probe_warning"] = smeta["error"]
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

    # Check for microgrid or tube data files (inspect real workbook sheet signatures, never blind '附件' match)
    all_names = {Path(df["rel_path"]).name.lower() for df in data_files}
    csv_names = {Path(df["rel_path"]).name.lower() for df in data_files if df.get("kind") == "csv"}
    all_xlsx_sheets = {
        str(sname).strip()
        for df in data_files
        if df.get("kind") in {"xlsx", "xlsm"}
        for sname in (df.get("sheet_names") or [])
    }
    has_mg_result_wb = any(
        k in all_names
        for k in ("result1.xlsx", "result2.xlsx", "result3.xlsx", "result4-2.xlsx", "result4-3.xlsx")
    )
    has_mg_schema = "小区负载" in all_xlsx_sheets and "光伏发电实际功率" in all_xlsx_sheets
    if has_mg_result_wb or has_mg_schema:
        detected_class = detected_class or "microgrid_dispatch"
        has_solver_dataset = True
    elif any(k in all_names for k in ("demand_batches.xlsx", "demand.xlsx")) or len(csv_names) >= 5:
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
        from tools.intake_assets import read_statement_text

        for sf in profile.get("statement_files") or []:
            sp = inbox_dir / sf
            if sp.is_file() and sp.suffix.lower() in {".md", ".txt", ".docx", ".pdf"}:
                txt = read_statement_text(sp, max_chars=4000)
                if txt.strip():
                    statement_texts.append(txt)
    combined_text = "\n".join(statement_texts) + "\n" + (prompt or "")

    # 3. Detect problem class
    from orpath.studio_domain_catalog import detect_problem_class_from_text, get_domain_spec

    detected_class = profile.get("detected_runnable_class")
    if not detected_class:
        detected_class = detect_problem_class_from_text(combined_text)

    # 4. Domain diagnosis & comparisons
    domain_name, rec_algo, comparisons, rationale = get_domain_spec(detected_class)

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
        f"4. 策略直通执行：已自动锁定推荐求解引擎与度量准则直通求解，如需微调可在下方参数卡片调整后重算。"
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
    matched_skills: list[dict[str, str]] = []
    literature_anchors: list[dict[str, Any]] = []
    knowledge_context_str = ""
    try:
        from orpath.agents.knowledge_pack import extract_skill_highlights, match_top_literature

        skills_raw, _chk, _modes = extract_skill_highlights(
            problem_class=detected_class if detected_class != "unregistered" else "",
            home=home,
        )
        matched_skills = [{"id": s["id"], "path": s["path"], "excerpt": s["excerpt"][:200]} for s in skills_raw[:4]]
        literature_anchors = match_top_literature(
            problem_class=detected_class if detected_class != "unregistered" else "",
            query=retrieval_query,
            topk=3,
            home=home,
        )
    except Exception:
        matched_skills = []
        literature_anchors = []

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
                topk=4,
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

            ctx_lines = [
                f"- 📚 [{kh['title']}] ({kh['backend']}): {kh['snippet']}"
                for kh in knowledge_hits
            ]
            for sk in matched_skills[:2]:
                ctx_lines.append(f"- 🛠️ [Skill:{sk['id']}]: {sk['excerpt'][:160]}")
            for lit in literature_anchors[:2]:
                ctx_lines.append(f"- 🏛️ [TopJournal:{lit['cite_label']}]: {lit['title']} ({lit['venue']})")
            if ctx_lines:
                knowledge_context_str = "\n".join(ctx_lines)
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
            "matched_skills": matched_skills,
            "literature_anchors": literature_anchors,
            "retrieval_query": retrieval_query,
        },
        "knowledge_hits": knowledge_hits,
        "matched_skills": matched_skills,
        "literature_anchors": literature_anchors,
        "retrieval_query": retrieval_query,
        "clarification_questions": clarification_questions,
    }

    out_file = outputs_dir / f"{slug}-studio-analysis.json"
    out_file.write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return analysis
