#!/usr/bin/env python3
"""Comprehensive test suite for Multi-Domain Watch Snapshot Aggregator (Task 6.1).

Covers:
  - DOMAIN_SWARM_ROLES coverage (10 domains × 6 roles = 60 roles)
  - _STAGE_ROLE mapping completeness
  - _SUBAGENT_DETECT_PATTERNS detection across all 10 domain swarms
  - _infer_stage_role_from_name parsing across all 10 domain swarms
  - build_snapshot output including active domain and 6-role cards metadata
"""
from __future__ import annotations

import re
from pathlib import Path
import pytest

from orpath.watch_snapshot import (
    DOMAIN_SWARM_ROLES,
    _STAGE_ROLE,
    _infer_stage_role_from_name,
    build_snapshot,
    detect_subagent_calls,
)

DOMAINS: list[str] = [
    "tube",
    "routing",
    "scheduling",
    "project",
    "inventory",
    "facility",
    "rostering",
    "microgrid",
    "pricing",
    "finance",
]


def test_domain_swarm_roles_complete():
    assert len(DOMAIN_SWARM_ROLES) == 10
    total_roles = 0
    for dom in DOMAINS:
        assert dom in DOMAIN_SWARM_ROLES, f"Missing domain {dom}"
        roles = DOMAIN_SWARM_ROLES[dom]
        assert len(roles) == 6, f"Domain {dom} must have exactly 6 roles"
        total_roles += len(roles)
    assert total_roles == 60


def test_stage_role_mapping_includes_all_60_roles():
    for dom, roles in DOMAIN_SWARM_ROLES.items():
        for agent_key, role_label in roles.items():
            assert agent_key in _STAGE_ROLE, f"Missing {agent_key} in _STAGE_ROLE"
            assert _STAGE_ROLE[agent_key] == role_label


@pytest.mark.parametrize("domain", DOMAINS)
def test_detect_subagent_calls_all_domains(domain: str):
    roles = DOMAIN_SWARM_ROLES[domain]
    for agent_key, role_label in roles.items():
        sample_log = f'2026-11-02 12:00:00 [subagent] tool call subagent name="{role_label}" executing'
        detected, evidence = detect_subagent_calls(sample_log)
        assert detected is True, f"Failed to detect subagent call for {agent_key} ({role_label})"
        assert len(evidence) >= 1


@pytest.mark.parametrize("domain", DOMAINS)
def test_infer_stage_role_from_name_all_domains(domain: str):
    roles = DOMAIN_SWARM_ROLES[domain]
    for agent_key, role_label in roles.items():
        log_name = f"{agent_key}-lead.log"
        stage, role = _infer_stage_role_from_name(log_name)
        assert role == role_label, f"Mismatch for {log_name}: got role {role}, expected {role_label}"


def test_build_snapshot_surfaces_domain_and_roles(tmp_path: Path):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    (workdir / "runs").mkdir()
    (workdir / "runs" / "routing_test").mkdir()

    snap = build_snapshot(
        slug="routing_test",
        thread_id="test_thread",
        workdir=workdir,
    )
    assert snap["domain"] == "routing"
    assert "domain_roles" in snap
    roles = snap["domain_roles"]
    assert len(roles) == 6
    assert any(r["role"] == "or-vrp-lead" and r["is_lead"] for r in roles)
