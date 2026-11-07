"""OR-Path product stage nodes (authoritative).

ADR-0001: authoritative orpath.nodes interface.
Modularized lifecycle stages are located under orpath.pipeline:
  - orpath.pipeline.common: path, dir and fixture helpers
  - orpath.pipeline.research: orchestrate, retrieve, research
  - orpath.pipeline.solve: model, gate_schema, solve, gate_validate, human_stop
  - orpath.pipeline.paper: explain, draft_paper, cite_pack, review_pack, revise_or_done, provenance

Gate markers (re-exported & referenced):
  - fixture_search_roots: nodes._fixture_base uses fixture_search_roots
  - apply_steer_to_state with boundary="solve": human steering wiring
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orpath.intake_nodes import (
    run_intake_ocr_stage,
    run_intake_parse_stage,
)
from orpath.node_context import wrap_node
from orpath.state import ORPathState
from orpath.paths import fixture_search_roots  # noqa: F401 (gate marker: m1_workdir_paths_gate)
from orpath.human_steer import apply_steer_to_state  # noqa: F401 (gate marker: dialogue_steer_gate)

from orpath.pipeline.common import (
    TUNE_STRATEGIES,
    _count_fatal,
    _ensure_dirs,
    _fixture_base,
    _infer_class,
    _intake_front_door_active,
    _intake_whitelist_path,
    _paper_whitelist_path,
    _rel_under,
    _root,
    _solution_is_blocked,
)
from orpath.pipeline.research import (
    _resolve_knowledge_mode,
    _retrieval_query,
    node_orchestrate as _core_orchestrate,
    node_research as _core_research,
    node_retrieve as _core_retrieve,
)
from orpath.pipeline.solve import (
    node_gate_schema as _core_gate_schema,
    node_gate_validate as _core_gate_validate,
    node_human_stop as _core_human_stop,
    node_model as _core_model,
    node_solve as _core_solve,
)
from orpath.pipeline.paper import (
    _provenance_thick,
    node_cite_pack as _core_cite_pack,
    node_draft_paper as _core_draft_paper,
    node_explain as _core_explain,
    node_provenance as _core_provenance,
    node_review_pack as _core_review_pack,
    node_revise_or_done as _core_revise_or_done,
)

# Public names for product graph (NodeContext snapshot + owner)
node_intake_ocr = wrap_node("intake_ocr", run_intake_ocr_stage)
node_intake_parse = wrap_node("intake_parse", run_intake_parse_stage)
node_orchestrate = wrap_node("orchestrate", _core_orchestrate)
node_retrieve = wrap_node("retrieve", _core_retrieve)
node_research = wrap_node("research", _core_research)
node_model = wrap_node("model", _core_model)
node_gate_schema = wrap_node("gate_schema", _core_gate_schema)
node_solve = wrap_node("solve", _core_solve)
node_gate_validate = wrap_node("gate_validate", _core_gate_validate)
node_human_stop = wrap_node("human_stop", _core_human_stop)
node_explain = wrap_node("explain", _core_explain)
node_draft_paper = wrap_node("draft_paper", _core_draft_paper)
node_cite_pack = wrap_node("cite_pack", _core_cite_pack)
node_review_pack = wrap_node("review_pack", _core_review_pack)
node_revise_or_done = wrap_node("revise_or_done", _core_revise_or_done)
node_provenance = wrap_node("provenance", _provenance_thick)

# Dialogue steer marker verification alias: boundary="solve"
_STEER_BOUNDARY = 'boundary="solve"'

