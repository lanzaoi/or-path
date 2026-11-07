#!/usr/bin/env python3
"""Multi-agent audit task: investigate whether all microgrid costs can be
compressed by 20% (teacher's standard answer claims >=20% headroom exists).

The microgrid domain team (lead + auditor + exact_bound + heuristic +
realities + redteam) must independently investigate:
  1. Model formulation: efficiency direction, power balance form, SOC dynamics
  2. Data interpolation: hourly->10min interpolation method
  3. Solver variants: alternative parameters / formulations
  4. Verdict: is there genuine 20% headroom, or is the current solution optimal?

Numbers Truth: agents must use their domain tools and report real evidence.
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
from orpath.control_plane import get_chat_model, is_real_llm_configured, thread_config

SLUG = "cumcm2026_c"


def main() -> int:
    ap_model = get_chat_model(temperature=0.1, timeout=300.0)
    print(f"Model: {ap_model.model} @ {ap_model.openai_api_base}")

    checkpointer = MemorySaver()
    app = build_compiled_microgrid_supervisor(
        checkpointer=checkpointer,
        model=ap_model,
        enable_guard=True,
        enable_trim=False,
    )

    cb = MultiAgentSnapshotCallback(thread_id=f"{SLUG}-audit", slug=SLUG, workdir=ROOT)
    cfg = thread_config(f"{SLUG}-audit")
    cfg["callbacks"] = [cb]
    cfg["recursion_limit"] = 80

    user_prompt = (
        "你是园区能源微网格调度协同主控。现有一条外部质疑：某教师标准答案声称"
        "本赛题（CUMCM 2026 C 题，微网与外部电网电力调控策略）的所有费用"
        "（Q1~Q4 各子问题总购电费用）都可以在当前求解结果基础上再压缩至少 20%。\n\n"
        "当前已求解结果（outputs/cumcm2026_c-solution.json，独立校验 ok=true，27/27 通过）：\n"
        "- Q1 单日计划购电费用：35,126.95 元\n"
        "- Q2 全年计划+紧急购电总费用：21,703,007.69 元\n"
        "- Q3 全年滚动预报调整总费用：16,216,958.20 元\n"
        "- Q4-2 波动电价总费用：22,464,605.06 元\n"
        "- Q4-3 波动电价滚动调整总费用：16,742,879.52 元\n\n"
        "案例数据目录：inbox/cumcm2026_c/（含 problem.txt、附件1~附件4.xlsx、附件5 结果模板）。\n\n"
        "请严格按五阶段流水线调查这条 20% 质疑是否成立：\n\n"
        "阶段 1：指派 or_microgrid_auditor，只调用 profile_microgrid_data(case_dir='inbox/cumcm2026_c') "
        "检查输入数据结构与完整性（电价范围、负荷/光伏量级、储能参数），用一段话给出数据审计结论后停止。\n\n"
        "阶段 2：指派 or_microgrid_exact_bound，先用 inspect_microgrid_solution(solution_path='outputs/cumcm2026_c-solution.json') "
        "读回当前解的 envelope 分解与目标值，然后调用 execute_or_solver(problem_id='microgrid_cumcm2026_c', "
        "mode='microgrid', extra_args='--case-dir inbox/cumcm2026_c', slug='cumcm2026_c-audit') 重新求解，"
        "对比两次目标值是否一致；并用 execute_python_sandbox 做敏感性实验：例如修改效率方向约定"
        "（充电 eta=0.9 放电 1/eta vs 双向 eta=0.9）、修改功率平衡形式、修改插值方式，"
        "看目标值变化幅度是否能达到 20%。用一段话给出精确下界/敏感性结论后停止。\n\n"
        "阶段 3：指派 or_microgrid_heuristic，调用 validate_solution_tool(problem_id='microgrid_cumcm2026_c', "
        "solution_path='outputs/cumcm2026_c-solution.json', output_path='outputs/cumcm2026_c-validation-audit.json') "
        "独立重算核验当前解的物理与经济约束，确认 ok=true 后停止。\n\n"
        "阶段 4：指派 or_microgrid_realities，基于阶段 2 的敏感性实验数据，撰写一份调查报告"
        "（中文，含：建模假设核查、效率方向/插值方式敏感性结果、20% 质疑的成立与否、若成立则指出"
        "具体可改进方向，若不成立则给出当前解已是最优的证据），用 export_paper_markdown "
        "导出至 papers/cumcm2026_c-audit.md 后停止。\n\n"
        "阶段 5：指派 or_microgrid_redteam，调用 run_microgrid_redteam_gate(solution_path='outputs/cumcm2026_c-solution.json', "
        "out_path='outputs/cumcm2026_c-redteam-audit.json') 执行 5 组 DIMO 篡改攻击测试，"
        "确认当前解无法被篡改通过，并针对 20% 质疑给出红队裁决后停止。\n\n"
        "全部五阶段完成后，主控用一段话总结：20% 质疑是否成立、关键证据、当前解是否最优。"
    )

    inputs = {"messages": [HumanMessage(content=user_prompt)]}

    print("\n--- Starting 6-Agent Audit Pipeline ---")
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
                    snip = content.replace("\n", " ")[:160]
                    print(f"[{elapsed:7.1f}s] step{step:02d} {node_name}: {snip}")
                    if getattr(msg, "tool_calls", None):
                        for tc in msg.tool_calls:
                            argstr = json.dumps(tc.get("args", {}), ensure_ascii=False)[:140]
                            print(f"        -> TOOL {tc.get('name')}({argstr})")
    except Exception as exc:
        print(f"\nExecution exception: {exc}")
        import traceback
        traceback.print_exc()

    total = time.time() - start
    print(f"\n=== Audit Pipeline finished in {total:.1f}s across {step} super-steps ===")
    print(f"Agent trace: outputs/.agents/{SLUG}/agent_trace.json")

    # Persist trace
    trace_payload = {
        "slug": SLUG,
        "audit_task": "20pct_headroom_investigation",
        "model": ap_model.model,
        "total_sec": total,
        "super_steps": step,
        "agent_names": list(MICROGRID_ALL_AGENT_NAMES),
        "events": cb.events,
    }
    trace_path = ROOT / "outputs" / ".agents" / SLUG / "agent_trace_audit.json"
    trace_path.write_text(json.dumps(trace_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Trace persisted: {trace_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
