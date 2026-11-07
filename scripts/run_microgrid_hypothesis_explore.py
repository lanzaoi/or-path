#!/usr/bin/env python3
"""Multi-agent hypothesis-space exploration: find modeling assumptions that
could explain a >=20% lower cost vs the current solution.

The teacher's standard answer claims all costs can be compressed by >=20%.
The previous audit proved the current LP is optimal *under its assumptions*.
This task asks the microgrid team to systematically explore alternative
modeling assumptions and find which ones produce >=20% lower costs.

Hypotheses to test (each via execute_python_sandbox):
  H1: Q1 without SOC end closure (SOC(24) free, not forced = SOC(0))
  H2: Efficiency applied one-way instead of round-trip (charge eta=0.9,
      discharge eta=0.9 on grid side, not battery side)
  H3: Battery can charge and discharge simultaneously (no mutual exclusion)
  H4: No battery at all (pure grid + PV, no storage)
  H5: Emergency purchase price = normal price (not 5x)
  H6: Q2 day-ahead plan uses actual PV instead of forecast (perfect info)
  H7: Battery capacity = 12000 (not SOC-limited to [1200,10800])
  H8: Price data from 附件4 (dynamic) instead of 附件1 (static) for Q1
  H9: Load/PV interpolation: step-hold vs linear
  H10: Time granularity: hourly (24) instead of 10-min (144)

For each hypothesis, compute Q1 cost and compare to current 35,126.95.
Identify which assumptions produce >=20% lower cost.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage

from orpath.agents.callbacks import MultiAgentSnapshotCallback
from orpath.agents.domains.microgrid import (
    MICROGRID_ALL_AGENT_NAMES,
    build_compiled_microgrid_supervisor,
)
from orpath.control_plane import get_chat_model, thread_config

SLUG = "cumcm2026_c"


def main() -> int:
    model = get_chat_model(temperature=0.1, timeout=300.0)
    print(f"Model: {model.model} @ {model.openai_api_base}")

    checkpointer = MemorySaver()
    app = build_compiled_microgrid_supervisor(
        checkpointer=checkpointer,
        model=model,
        enable_guard=True,
        enable_trim=False,
    )

    cb = MultiAgentSnapshotCallback(thread_id=f"{SLUG}-explore", slug=SLUG, workdir=ROOT)
    cfg = thread_config(f"{SLUG}-explore")
    cfg["callbacks"] = [cb]
    cfg["recursion_limit"] = 100

    user_prompt = (
        "你是园区能源微网格调度协同主控。现有一条教师标准答案声称：CUMCM 2026 C 题的所有费用"
        "（Q1~Q4）都可以压缩至少 20%。当前求解结果（outputs/cumcm2026_c-solution.json，"
        "独立校验 ok=true）已证明在其建模假设下是全局最优（GLOP proven_optimal）。\n\n"
        "因此，教师答案的更低费用一定来自**不同的建模假设**。请严格按五阶段流水线"
        "系统性地探索假设空间，找到能产生 >=20% 更低费用的建模路径：\n\n"
        "阶段 1：指派 or_microgrid_auditor，只调用 profile_microgrid_data(case_dir='inbox/cumcm2026_c') "
        "确认数据结构，用一段话给出数据审计结论后停止。\n\n"
        "阶段 2：指派 or_microgrid_exact_bound，用 execute_python_sandbox 系统测试以下假设"
        "（每个假设写独立脚本，输出 Q1 单日费用，与当前 35,126.95 元对比）：\n"
        "  H1: Q1 不要求 SOC 日终闭合（SOC(24) 自由，不强制 = SOC(0)=6000）\n"
        "  H2: 效率单向应用（充电 eta=0.9 作用在电网侧，放电 eta=0.9 作用在电网侧，即 SOC 变化 = ch*eta - dis*eta）\n"
        "  H3: 电池可同时充放电（无互斥约束，LP 松弛）\n"
        "  H4: 无电池（纯电网+光伏，无储能）\n"
        "  H5: 紧急购电价格 = 正常电价（非 5 倍）\n"
        "  H6: Q2 计划用实际 PV（而非预报，完美信息）\n"
        "  H7: 电池可用容量 = 12000（SOC 不限制在 [1200,10800]，而是 [0,12000]）\n"
        "  H8: Q1 用附件4 动态电价（而非附件1 静态电价）\n"
        "  H9: 负荷/光伏插值用阶梯保持（而非线性）\n"
        "  H10: 时间粒度用整点 24 段（而非 10 分钟 144 段）\n"
        "每个假设都要真实求解（调用 tools/solve_microgrid.py 或直接用 scipy.optimize.linprog "
        "在 sandbox 中建模），输出 Q1 费用并与基准对比，用一段话给出哪些假设产生 >=20% 更低费用后停止。\n\n"
        "阶段 3：指派 or_microgrid_heuristic，调用 validate_solution_tool(problem_id='microgrid_cumcm2026_c', "
        "solution_path='outputs/cumcm2026_c-solution.json', output_path='outputs/cumcm2026_c-validation-explore.json') "
        "独立重算确认当前解 ok=true 后停止。\n\n"
        "阶段 4：指派 or_microgrid_realities，基于阶段 2 的假设空间探索结果撰写报告"
        "（中文，含：假设矩阵表（假设/Q1费用/降幅/是否>=20%）、哪些假设合法哪些不合法、"
        "教师答案最可能的建模路径推断），用 export_paper_markdown 导出至 papers/cumcm2026_c-explore.md 后停止。\n\n"
        "阶段 5：指派 or_microgrid_redteam，用 execute_python_sandbox 对阶段 2 中产生 >=20% 降幅的假设"
        "做合法性审查（是否违反题面物理约束），并调用 run_microgrid_redteam_gate(solution_path='outputs/cumcm2026_c-solution.json', "
        "out_path='outputs/cumcm2026_c-redteam-explore.json') 确认当前解无法被篡改，给出红队裁决后停止。\n\n"
        "全部完成后，主控用一段话总结：哪些假设能产生 >=20% 更低费用、这些假设是否合法、"
        "教师答案最可能的建模路径是什么。"
    )

    inputs = {"messages": [HumanMessage(content=user_prompt)]}

    print("\n--- Starting 6-Agent Hypothesis-Space Exploration ---")
    start = time.time()
    step = 0
    try:
        for output in app.stream(inputs, cfg, stream_mode="updates"):
            step += 1
            elapsed = time.time() - start
            for node_name, update in output.items():
                for msg in (update or {}).get("messages", []):
                    name = getattr(msg, "name", None) or type(msg).__name__
                    content = (msg.content or "")
                    snip = content.replace("\n", " ")[:200]
                    print(f"[{elapsed:7.1f}s] step{step:02d} {node_name}: {snip}")
                    if getattr(msg, "tool_calls", None):
                        for tc in msg.tool_calls:
                            argstr = json.dumps(tc.get("args", {}), ensure_ascii=False)[:150]
                            print(f"        -> TOOL {tc.get('name')}({argstr})")
    except Exception as exc:
        print(f"\nExecution exception: {exc}")
        import traceback
        traceback.print_exc()

    total = time.time() - start
    print(f"\n=== Exploration finished in {total:.1f}s across {step} super-steps ===")

    trace_payload = {
        "slug": SLUG,
        "task": "hypothesis_space_exploration",
        "model": model.model,
        "total_sec": total,
        "super_steps": step,
        "agent_names": list(MICROGRID_ALL_AGENT_NAMES),
        "events": cb.events,
    }
    trace_path = ROOT / "outputs" / ".agents" / SLUG / "agent_trace_explore.json"
    trace_path.write_text(json.dumps(trace_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Trace persisted: {trace_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
