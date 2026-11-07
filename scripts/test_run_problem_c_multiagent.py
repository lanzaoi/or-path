#!/usr/bin/env python3
"""Execute and trace LangGraph Native Multi-Agent on CUMCM 2026 Problem C.

This script tests the full supervisor -> researcher -> modeler -> verifier_writer
chain, capturing detailed step transitions, tool invocations, execution times,
and generated artifacts for comparison against the legacy Pi multi-agent architecture.
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
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from orpath.agents.callbacks import MultiAgentSnapshotCallback
from orpath.agents.supervisor import (
    SUPERVISOR_NAME,
    build_compiled_supervisor,
)
from orpath.control_plane import get_chat_model, thread_config

def main():
    slug = "cumcm2026_c"
    workdir = ROOT
    inbox_dir = workdir / "inbox" / slug
    problem_file = inbox_dir / "problem.txt"
    
    print(f"=== [OR-Path Multi-Agent Trace] Target: {slug} ===")
    print(f"Inbox Problem File: {problem_file}")
    if not problem_file.is_file():
        print(f"ERROR: {problem_file} does not exist!")
        return 1
        
    # Read raw problem text
    problem_text = problem_file.read_text(encoding="utf-8")
    print(f"Problem Text Loaded: {len(problem_text)} characters")

    # Construct chat model with configured API
    model = get_chat_model(temperature=0.1)
    print(f"Chat Model: {model.model_name} (Base URL: {model.openai_api_base})")

    # Build compiled supervisor
    checkpointer = MemorySaver()
    app = build_compiled_supervisor(checkpointer=checkpointer, model=model)
    print("Compiled Supervisor Graph successfully constructed.")

    # Attach snapshot callback
    cb = MultiAgentSnapshotCallback(thread_id=slug, slug=slug, workdir=workdir)
    cfg = thread_config(f"{slug}-test-trace")
    cfg["callbacks"] = [cb]
    # Set recursion limit to allow full 4-stage multi-turn dialogue
    cfg["recursion_limit"] = 30

    # User message (clean prompt with ONLY problem description and data path)
    user_prompt = (
        f"运筹学竞赛任务：题面为全国大学生数学建模竞赛 C题（微网与外部电网电力调控策略）。\n"
        f"原始题面文件及相关附件已放置于：inbox/{slug}/problem.txt 以及 inbox/{slug}/ 目录下。\n"
        f"数据文件包括：附件1.xlsx, 附件2.xlsx, 附件3.xlsx, 附件4.xlsx。\n"
        f"请中心主控严格按 researcher → modeler → verifier_writer 流水线执行：\n"
        f"- 阶段 1：or_researcher 首先调用 read_problem_file 读取题面，精炼研判光伏、负荷、储能与调度目标特征（控制在 500 字以内，严禁编写代码或论文）；\n"
        f"- 阶段 2：or_modeler 探测系统内成熟算子（microgrid）并调用 execute_or_solver 求解，产出 outputs/{slug}-solution.json 与各项结果 Excel 表格；\n"
        f"- 阶段 3：or_verifier_writer 调用 validate_solution_tool 独立核验物理与经济约束（SOC、功率平衡、充放电互斥），确认无误后撰写学术论文并用 export_paper_markdown 导出至 papers/{slug}.md。\n"
        f"- 阶段 4：主控核查 ok: true 且论文成功导出后，总结汇报完结。"
    )

    inputs = {
        "messages": [HumanMessage(content=user_prompt)],
    }

    print("\n--- Starting Execution Pipeline ---")
    start_time = time.time()
    step_num = 0

    try:
        for output in app.stream(inputs, cfg, stream_mode="updates"):
            step_num += 1
            elapsed = time.time() - start_time
            for node_name, state_update in output.items():
                print(f"\n[Step {step_num}] [{elapsed:.2f}s] Active Node: {node_name}")
                if "messages" in state_update:
                    for msg in state_update["messages"]:
                        role = getattr(msg, "name", None) or type(msg).__name__
                        content_snip = (msg.content or "")[:200].replace("\n", " ")
                        print(f"  -> Message from [{role}]: {content_snip}...")
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                print(f"     * Tool Call: {tc['name']}({json.dumps(tc['args'], ensure_ascii=False)[:120]})")
    except Exception as e:
        print(f"\nExecution encountered exception: {e}")
        import traceback
        traceback.print_exc()

    total_time = time.time() - start_time
    print(f"\n=== Pipeline Completed in {total_time:.2f}s across {step_num} steps ===")

    # Inspect events logged by callback
    print(f"\nCallback Recorded Events: {len(cb.events)}")
    for ev in cb.events:
        ev_type = ev.get("type")
        agent = ev.get("agent") or ev.get("node")
        tool = ev.get("tool_name")
        if ev_type in ("agent_start", "agent_end"):
            print(f"  - Event: {ev_type} | Agent: {agent} | Timestamp: {ev.get('timestamp')}")
        elif ev_type in ("tool_start", "tool_end"):
            status = ev.get("status", "ok")
            print(f"  - Event: {ev_type} | Tool: {tool} (status={status}) | Agent: {agent}")

    # Inspect generated artifacts
    solution_path = ROOT / "outputs" / f"{slug}-solution.json"
    validate_path = ROOT / "outputs" / f"{slug}-validation.json"
    alt_validate_path = ROOT / "outputs" / f"{slug}-validate.json"
    paper_path = ROOT / "papers" / f"{slug}.md"

    print("\n=== Artifacts Check ===")
    print(f"Solution File ({solution_path}): exists={solution_path.is_file()}")
    if solution_path.is_file():
        print(f"  Size: {solution_path.stat().st_size} bytes")
    print(f"Validate File ({validate_path}): exists={validate_path.is_file()}")
    if validate_path.is_file():
        print(f"  Size: {validate_path.stat().st_size} bytes")
    print(f"Alt Validate File ({alt_validate_path}): exists={alt_validate_path.is_file()}")
    if alt_validate_path.is_file():
        print(f"  Size: {alt_validate_path.stat().st_size} bytes")
    print(f"Paper File ({paper_path}): exists={paper_path.is_file()}")
    if paper_path.is_file():
        print(f"  Size: {paper_path.stat().st_size} bytes")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
