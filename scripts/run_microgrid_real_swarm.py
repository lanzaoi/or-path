#!/usr/bin/env python3
"""REAL LLM multi-agent run for CUMCM 2026 Problem C (Microgrid dispatch).

This is the "break the paper-mask" run: it wires the genuine Spark X2.6 chat
model (``orpath.control_plane.get_chat_model``) into the native LangGraph
microgrid supervisor team and drives the full

    Lead -> Auditor -> ExactBound -> Heuristic -> Realities -> Redteam

pipeline on the *complete* 7394-char problem statement (no 1600-char trim hook).
Every agent start/end and tool start/end event is captured by
``MultiAgentSnapshotCallback`` into ``outputs/.agents/cumcm2026_c/`` so the
thinking/tool-call trace is a real on-disk artifact.

Usage:
    python scripts/run_microgrid_real_swarm.py [--max-steps N] [--out-trace PATH]
"""
from __future__ import annotations

import argparse
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


def _read_problem(inbox_dir: Path) -> str:
    pf = inbox_dir / "problem.txt"
    return pf.read_text(encoding="utf-8")


def _build_user_prompt(problem_text: str) -> str:
    return (
        "你是园区能源微网格调度协同主控。请严格按 microgrid 团队五阶段流水线执行，"
        "全程遵守 Numbers Truth 铁律（数值权威唯一归属求解脚本与独立校验器）。\n\n"
        "=== 完整题面（CUMCM 2026 C 题，未截断）===\n"
        f"{problem_text}\n"
        "=== 题面结束 ===\n\n"
        "案例数据目录：inbox/cumcm2026_c/（含 problem.txt、附件1~附件4.xlsx、附件5 结果模板）。\n\n"
        "【效率纪律】每位专家只调用我指定的那一个核心工具，拿到结果后立即用一段话总结并停止，"
        "严禁调用其他工具、严禁重复求解、严禁做额外探索。主控也不要重复指派同一阶段。\n\n"
        "必须依次完成以下阶段，严禁跳步：\n"
        "1. 指派 or_microgrid_auditor：只调用 profile_microgrid_data(case_dir='inbox/cumcm2026_c') "
        "生成数据画像，用一段话给出审计结论（电价/负荷/光伏一致性、储能铭牌参数）后立即停止。\n"
        "2. 指派 or_microgrid_exact_bound：只调用 execute_or_solver(problem_id='microgrid_cumcm2026_c', "
        "mode='microgrid', extra_args='--case-dir inbox/cumcm2026_c', slug='cumcm2026_c') 求解全局最优，"
        "再用 inspect_microgrid_solution 读回 objective，报告 proven_optimal 与目标值后停止。\n"
        "3. 指派 or_microgrid_heuristic：只调用 validate_solution_tool(problem_id='microgrid_cumcm2026_c', "
        "solution_path='outputs/cumcm2026_c-solution.json', output_path='outputs/cumcm2026_c-validation.json') "
        "独立核验物理约束，确认 ok=true 后停止。\n"
        "4. 指派 or_microgrid_realities：综合 outputs/cumcm2026_c-solution.json 的真实数值撰写一篇高规格数模学术论文"
        "（中文，含摘要、建模假设、符号说明、四问建模与求解结果、结论，公式与数值务必来自 solution.json），"
        "用 export_paper_markdown(output_path='papers/cumcm2026_c.md', content=...) 导出后停止。\n"
        "5. 指派 or_microgrid_redteam：只调用 run_microgrid_redteam_gate(solution_path='outputs/cumcm2026_c-solution.json', "
        "out_path='outputs/cumcm2026_c-redteam.json') 执行 5 组 DIMO 篡改攻击测试，给出红队裁决后停止。\n\n"
        "全部五阶段完成后，主控用一段话总结：目标函数值、各子问题结果、校验与篡改测试结论、论文与结果表落盘路径。"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-steps", type=int, default=120)
    ap.add_argument("--out-trace", default=str(ROOT / "outputs" / ".agents" / SLUG / "agent_trace.json"))
    args = ap.parse_args()

    inbox_dir = ROOT / "inbox" / SLUG
    problem_text = _read_problem(inbox_dir)
    print(f"=== [REAL SWARM] slug={SLUG} ===")
    print(f"Problem chars: {len(problem_text)}")
    print(f"Real LLM configured: {is_real_llm_configured()}")

    model = get_chat_model(temperature=0.1, timeout=300.0)
    print(f"Model: {model.model} @ {model.openai_api_base}")

    # Fresh trace directory for this run.
    trace_dir = Path(args.out_trace).parent
    trace_dir.mkdir(parents=True, exist_ok=True)
    # Clear the previous run log so this run's trace is unambiguous.
    log_file = trace_dir / f"{SLUG}.log"
    if log_file.exists():
        log_file.unlink()

    checkpointer = MemorySaver()
    app = build_compiled_microgrid_supervisor(
        checkpointer=checkpointer,
        model=model,
        enable_guard=True,
        enable_trim=False,  # 1600-char trim hook is hard-disabled
    )
    print("Supervisor graph compiled (guard=on, trim=off).")

    cb = MultiAgentSnapshotCallback(thread_id=SLUG, slug=SLUG, workdir=ROOT)
    cfg = thread_config(f"{SLUG}-real-swarm")
    cfg["callbacks"] = [cb]
    cfg["recursion_limit"] = args.max_steps

    user_prompt = _build_user_prompt(problem_text)
    inputs = {"messages": [HumanMessage(content=user_prompt)]}

    start = time.time()
    step = 0
    final_state: dict | None = None
    try:
        for output in app.stream(inputs, cfg, stream_mode="updates"):
            step += 1
            elapsed = time.time() - start
            for node_name, update in output.items():
                role = getattr(update, "get", lambda *_: None)
                for msg in (update or {}).get("messages", []):
                    name = getattr(msg, "name", None) or type(msg).__name__
                    content = (msg.content or "")
                    snip = content.replace("\n", " ")[:160]
                    print(f"[{elapsed:7.1f}s] step{step:02d} {node_name}: {snip}")
                    if getattr(msg, "tool_calls", None):
                        for tc in msg.tool_calls:
                            argstr = json.dumps(tc.get("args", {}), ensure_ascii=False)[:140]
                            print(f"        -> TOOL {tc.get('name')}({argstr})")
            # capture final state
            try:
                final_state = app.get_state(cfg)
            except Exception:
                pass
    except Exception as exc:  # noqa: BLE001
        print(f"\n[REAL SWARM] Execution exception: {exc}")
        import traceback

        traceback.print_exc()
        final_state = None

    total = time.time() - start
    print(f"\n=== REAL SWARM finished in {total:.1f}s across {step} super-steps ===")

    # Persist the full agent trace (events + captured messages).
    trace_payload = {
        "slug": SLUG,
        "model": model.model,
        "base_url": model.openai_api_base,
        "real_llm": is_real_llm_configured(),
        "problem_chars": len(problem_text),
        "total_sec": total,
        "super_steps": step,
        "recursion_limit": args.max_steps,
        "trim_hook_enabled": False,
        "guard_enabled": True,
        "agent_names": list(MICROGRID_ALL_AGENT_NAMES),
        "events": cb.events,
        "final_messages": None,
    }
    if final_state is not None:
        try:
            msgs = list(final_state.values or [])
            trace_payload["final_messages"] = [
                {
                    "role": getattr(m, "type", None),
                    "name": getattr(m, "name", None),
                    "content": (getattr(m, "content", "") or "")[:2000],
                    "tool_calls": [
                        {"name": tc.get("name"), "args": tc.get("args")}
                        for tc in (getattr(m, "tool_calls", None) or [])
                    ],
                }
                for m in msgs
            ]
        except Exception:
            pass
    trace_path = Path(args.out_trace)
    trace_path.write_text(json.dumps(trace_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Agent trace persisted: {trace_path} ({trace_path.stat().st_size} bytes)")

    # ---- artifact verification ----
    print("\n=== ARTIFACT CHECK ===")
    checks = {
        "solution": ROOT / "outputs" / f"{SLUG}-solution.json",
        "validation": ROOT / "outputs" / f"{SLUG}-validation.json",
        "paper": ROOT / "papers" / f"{SLUG}.md",
        "result1": ROOT / "outputs" / SLUG / "result1.xlsx",
    }
    for label, path in checks.items():
        exists = path.is_file()
        size = path.stat().st_size if exists else 0
        print(f"  {label:10s} {path.relative_to(ROOT)}  exists={exists}  bytes={size}")

    # event summary
    kinds: dict[str, int] = {}
    for ev in cb.events:
        kinds[ev.get("kind", "?")] = kinds.get(ev.get("kind", "?"), 0) + 1
    print(f"\nEvent kinds: {kinds}")
    agents_hit = sorted({ev.get("agent") for ev in cb.events if ev.get("agent")})
    print(f"Agents seen: {agents_hit}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
