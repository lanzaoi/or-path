"""pi_launch_law: bare pi -p must not claim multi-agent."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orpath.pi_launch_law import (
    LaunchMode,
    banner,
    build_multi_agent_lead_cmd,
    build_single_lead_cmd,
    is_harness_shaped_cmd,
    validate_launch,
)
from orpath.subagent_harness import LEAD_TOOLS_NO_WRITE


def test_single_lead_cmd_not_harness_shaped():
    cmd = build_single_lead_cmd(ROOT, prompt="hello single lead")
    assert not is_harness_shaped_cmd(cmd)
    v = validate_launch(cmd, claim_multi_agent=False)
    assert v.ok
    assert v.mode is LaunchMode.SINGLE_LEAD


def test_claim_multi_on_bare_cmd_fails():
    cmd = build_single_lead_cmd(ROOT, prompt="pretend multi")
    v = validate_launch(cmd, claim_multi_agent=True, label="test")
    assert not v.ok
    assert "ILLEGAL" in v.reason or "harness" in v.reason.lower()


def test_multi_agent_cmd_is_harness_shaped():
    cmd = build_multi_agent_lead_cmd(ROOT, prompt="must call subagent")
    assert is_harness_shaped_cmd(cmd)
    assert LEAD_TOOLS_NO_WRITE.split(",")[0] in " ".join(cmd) or "--tools" in cmd
    tools_idx = cmd.index("--tools")
    tools = cmd[tools_idx + 1]
    assert "subagent" in tools
    assert "write" not in tools.split(",")
    assert "edit" not in tools.split(",")
    assert "--mode" in cmd and "json" in cmd
    v = validate_launch(cmd, claim_multi_agent=True)
    assert v.ok
    assert v.mode is LaunchMode.MULTI_AGENT_HARNESS


def test_banner_mentions_mode():
    b1 = banner(LaunchMode.SINGLE_LEAD, job="x")
    assert "SINGLE_LEAD" in b1
    assert "NOT multi-agent" in b1
    b2 = banner(LaunchMode.MULTI_AGENT_HARNESS, job="y")
    assert "MULTI_AGENT" in b2


def test_resolve_launcher_imports():
    # syntax / import path used by tube launcher
    import importlib.util

    p = ROOT / "outputs/b-tube-cut/logs/launch_pi_resolve.py"
    spec = importlib.util.spec_from_file_location("launch_pi_resolve", p)
    assert spec and spec.loader
    # only check file declares SINGLE_LEAD
    text = p.read_text(encoding="utf-8")
    assert "SINGLE_LEAD" in text
    assert "claim_multi_agent=False" in text


def test_paper_launcher_uses_harness_imports():
    text = (ROOT / "outputs/b-tube-cut/logs/launch_pi_paper_loop.py").read_text(
        encoding="utf-8"
    )
    assert "run_cite_subagent_lead" in text
    assert "run_review_subagent_lead" in text
    assert "MULTI_AGENT_HARNESS" in text
    assert "claim_multi_agent=False" in text  # draft only
