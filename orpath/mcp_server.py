#!/usr/bin/env python3
"""OR-Path MCP server (stdio JSON-RPC minimal) — whitelist tools only.

Exposes:
  - orpath_list_solvers
  - orpath_list_tools
  - orpath_memory_search
  - orpath_memory_record
  - orpath_validate_check (run validate_solution.py)

Does NOT expose raw solve as proven oracle without validate.
Optional: install official `mcp` package later; this file works with stdlib only
so product CI does not require MCP deps.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orpath.process_memory import record_from_run, retrieve_lessons  # noqa: E402
from orpath.tool_catalog import list_tools, solver_claim_table  # noqa: E402


PROTOCOL = "2024-11-05"
SERVER_NAME = "orpath"
SERVER_VERSION = "0.1.0"


def _tools_list() -> list[dict[str, Any]]:
    return [
        {
            "name": "orpath_list_solvers",
            "description": "List OR-Path problem_class → default solve_mode and claim ladder",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "orpath_list_tools",
            "description": "List OR-Path product tools (solve/validate/memory/…)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mcp_only": {
                        "type": "boolean",
                        "description": "If true, only MCP-whitelisted tools",
                        "default": False,
                    }
                },
            },
        },
        {
            "name": "orpath_memory_search",
            "description": (
                "Search process memory lessons (how past runs were solved / pitfalls). "
                "Never treat results as authoritative optima."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "problem_class": {"type": "string"},
                    "topk": {"type": "integer", "default": 5},
                },
            },
        },
        {
            "name": "orpath_memory_record",
            "description": "Record a process lesson (no objective authority fields)",
            "inputSchema": {
                "type": "object",
                "required": ["problem_class", "summary"],
                "properties": {
                    "problem_class": {"type": "string"},
                    "summary": {"type": "string"},
                    "slug": {"type": "string"},
                    "key_decisions": {"type": "array", "items": {"type": "string"}},
                    "pitfalls": {"type": "array", "items": {"type": "string"}},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        {
            "name": "orpath_validate_check",
            "description": "Run tools/validate_solution.py on a solution JSON path",
            "inputSchema": {
                "type": "object",
                "required": ["problem_id", "solution_path"],
                "properties": {
                    "problem_id": {"type": "string"},
                    "solution_path": {"type": "string"},
                },
            },
        },
    ]


def _call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    args = arguments or {}
    if name == "orpath_list_solvers":
        return {"solvers": solver_claim_table()}
    if name == "orpath_list_tools":
        return {"tools": list_tools(mcp_only=bool(args.get("mcp_only")))}
    if name == "orpath_memory_search":
        hits = retrieve_lessons(
            str(args.get("query") or ""),
            root=ROOT,
            problem_class=str(args.get("problem_class") or "") or None,
            topk=int(args.get("topk") or 5),
        )
        return {"hits": hits, "authority": "process_only_not_optima"}
    if name == "orpath_memory_record":
        path = record_from_run(
            ROOT,
            slug=str(args.get("slug") or ""),
            problem_class=str(args.get("problem_class") or ""),
            summary=str(args.get("summary") or ""),
            key_decisions=list(args.get("key_decisions") or []),
            pitfalls=list(args.get("pitfalls") or []),
            tags=list(args.get("tags") or []),
            local=True,
        )
        return {"path": str(path)}
    if name == "orpath_validate_check":
        pid = str(args.get("problem_id") or "")
        sol = str(args.get("solution_path") or "")
        script = ROOT / "tools" / "validate_solution.py"
        cmd = [sys.executable, str(script), "--problem-id", pid, "--solution", sol]
        r = subprocess.run(
            cmd, cwd=str(ROOT), text=True, encoding="utf-8", errors="replace", capture_output=True
        )
        return {
            "exit_code": r.returncode,
            "stdout": (r.stdout or "")[-4000:],
            "stderr": (r.stderr or "")[-2000:],
        }
    raise ValueError(f"unknown tool: {name}")


def _result_content(payload: Any) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _error_content(msg: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": msg}], "isError": True}


def handle(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one JSON-RPC message; notifications return None."""
    mid = msg.get("id", None)
    method = msg.get("method")
    params = msg.get("params") or {}

    def reply(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def fail(code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}

    if method == "initialize":
        return reply(
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        )
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return reply({})
    if method == "tools/list":
        return reply({"tools": _tools_list()})
    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") or {}
        try:
            payload = _call_tool(name, arguments if isinstance(arguments, dict) else {})
            return reply(_result_content(payload))
        except Exception as exc:  # noqa: BLE001
            return reply(_error_content(str(exc)))
    if mid is None:
        return None
    return fail(-32601, f"method not found: {method}")


def main() -> int:
    """Stdio loop: one JSON object per line (MCP-style newline JSON)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            err = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "parse error"},
            }
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()
            continue
        if not isinstance(msg, dict):
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
