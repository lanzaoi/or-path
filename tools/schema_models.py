"""Pydantic contracts for OR-Path T2 (exportable to contracts/)."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ProblemClass(str, Enum):
    shortest_path = "shortest_path"
    tsp = "tsp"
    vrp = "vrp"
    tube_cut = "tube_cut"
    polyomino_cover = "polyomino_cover"


class SolutionStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    ERROR = "ERROR"


FORBIDDEN_SCHEMA_KEYS = frozenset(
    {
        "objective",
        "optimal",
        "objective_value",
        "optima",
        "optimal_value",
        "optimal_cost",
        "tour",
        "routes",
        "path",
    }
)

# 1.1 intake.json — same spirit + a few extra solution-ish keys (specs/problem-intake.md)
FORBIDDEN_INTAKE_KEYS = frozenset(
    {
        *FORBIDDEN_SCHEMA_KEYS,
        "proven_optimal",
        "best_cost",
        "best_objective",
    }
)

INTAKE_SCHEMA_VERSION = "1.1.0"
INTAKE_STATUSES = frozenset({"ok", "needs_human", "error"})
INTAKE_ASSET_KINDS = frozenset({"csv", "xlsx", "stp", "pdf", "image", "other"})


class Edge(BaseModel):
    u: str
    v: str
    w: float


class ProblemSchema(BaseModel):
    problem_id: str
    problem_class: ProblemClass
    slug: str | None = None
    # SP
    nodes: list[str] | None = None
    edges: list[Edge] | None = None
    edges_ref: str | None = None
    source: str | None = None
    target: str | None = None
    weight_key: str | None = "w"
    # TSP
    distance_matrix: list[list[float]] | None = None
    coords: list[dict[str, Any]] | None = None
    # VRP
    depot: str | int | None = None
    locations: list[dict[str, Any]] | None = None
    demands: dict[str, float] | list[float] | None = None
    vehicle_count: int | None = None
    capacities: list[float] | None = None
    # polyomino_cover (M2) — structural only; no placements/objective in schema
    board: dict[str, Any] | None = None
    board_ref: str | None = None
    rows: int | None = None
    cols: int | None = None
    pieces: list[Any] | None = None
    piece_types: list[Any] | None = None
    removed: list[Any] | None = None
    max_counts: dict[str, Any] | None = None
    constraints: list[Any] = Field(default_factory=list)
    notes: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _class_fields(self) -> ProblemSchema:
        pc = self.problem_class
        if pc == ProblemClass.shortest_path:
            if not self.nodes and not self.edges_ref:
                raise ValueError("shortest_path requires nodes or edges_ref")
        elif pc == ProblemClass.tsp:
            if self.distance_matrix is None and self.coords is None:
                raise ValueError("tsp requires distance_matrix or coords")
        elif pc == ProblemClass.vrp:
            if self.vehicle_count is None or self.vehicle_count < 2:
                raise ValueError("vrp T2 requires vehicle_count >= 2")
            if self.capacities is None:
                raise ValueError("vrp requires capacities")
            if self.demands is None:
                raise ValueError("vrp requires demands")
        elif pc == ProblemClass.polyomino_cover:
            has_board = bool(self.board or self.board_ref)
            has_rc = self.rows is not None and self.cols is not None
            has_pieces = bool(self.pieces or self.piece_types)
            if not (has_board or has_rc or has_pieces):
                raise ValueError(
                    "polyomino_cover requires board|board_ref or rows+cols or pieces|piece_types"
                )
        return self


class Solution(BaseModel):
    problem_id: str
    problem_class: ProblemClass | str = "shortest_path"
    status: SolutionStatus | str
    objective: float | int
    solver: str
    source: str
    path: list[str] | None = None
    tour: list[str] | None = None
    routes: list[list[str]] | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _shape(self) -> Solution:
        pc = (
            self.problem_class.value
            if isinstance(self.problem_class, ProblemClass)
            else str(self.problem_class)
        )
        if pc == "shortest_path" and not self.path:
            raise ValueError("shortest_path solution requires path")
        if pc == "tsp" and not self.tour:
            raise ValueError("tsp solution requires tour")
        if pc == "vrp" and not self.routes:
            raise ValueError("vrp solution requires routes")
        # polyomino_cover: placements live in meta or free fields — envelope not strict here
        return self


class CheckResult(BaseModel):
    name: str
    ok: bool
    expected: Any | None = None
    got: Any | None = None
    detail: str | None = None


class ValidateReport(BaseModel):
    ok: bool
    problem_id: str
    problem_class: str
    checks: list[CheckResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    source_path: str
    page: int | None = None
    mineru_job_id: str | None = None
    title: str | None = None


class RetrievalHit(BaseModel):
    chunk_id: str
    score: float
    backend: Literal["lightrag", "bm25", "fts", "seed", "rrf"]
    snippet: str
    source_path: str | None = None


class RetrievalArtifact(BaseModel):
    query: str
    knowledge_mode: Literal["off", "seed", "hybrid"]
    hits: list[RetrievalHit] = Field(default_factory=list)
    seed_facts: list[dict[str, Any]] = Field(default_factory=list)


class IntakeSource(BaseModel):
    path: str
    sha256: str | None = None
    kind: str | None = None
    pages: int | None = None


class IntakeSubproblem(BaseModel):
    id: str
    title: str
    must_deliver: list[str] = Field(default_factory=list)
    data_refs: list[str] = Field(default_factory=list)
    notes: str | None = None


class IntakeDataAsset(BaseModel):
    path: str
    kind: Literal["csv", "xlsx", "stp", "pdf", "image", "other"] = "other"
    role: str = "unknown"
    notes: str | None = None


class IntakeArtifact(BaseModel):
    """Structured problem intake (1.1). Not a Solution and not a ProblemSchema."""

    slug: str
    schema_version: str = INTAKE_SCHEMA_VERSION
    status: Literal["ok", "needs_human", "error"]
    sources: list[IntakeSource] = Field(default_factory=list)
    subproblems: list[IntakeSubproblem]
    data_assets: list[IntakeDataAsset] = Field(default_factory=list)
    constraints_text: str = ""
    objectives_text: str = ""
    deliverables: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    brief_path: str
    ocr_raw_path: str
    ocr_meta_path: str
    ocr_backend: str
    problem_class_hint: str | None = None
    problem_id_hint: str | None = None


def walk_forbidden_keys(
    obj: Any,
    found: set[str] | None = None,
    *,
    forbidden: frozenset[str] | None = None,
) -> set[str]:
    """Collect forbidden key names under obj.

    Special case: key ``path`` is only forbidden when the value looks like a
    *solution tour* (list of nodes). A string filesystem/URI path is allowed
    (common in intake/schema data_refs).
    """
    keys = forbidden if forbidden is not None else FORBIDDEN_SCHEMA_KEYS
    if found is None:
        found = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in keys:
                if lk == "path" and isinstance(v, str):
                    # e.g. "path": "notes/foo.md" — not a graph solution path
                    pass
                else:
                    found.add(lk)
            walk_forbidden_keys(v, found, forbidden=keys)
    elif isinstance(obj, list):
        for item in obj:
            walk_forbidden_keys(item, found, forbidden=keys)
    return found


def export_json_schemas(out_dir: Any) -> None:
    from pathlib import Path

    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    mapping = {
        "problem_schema.json": ProblemSchema,
        "solution.json": Solution,
        "validate_report.json": ValidateReport,
        "chunk.json": Chunk,
        "retrieval_hit.json": RetrievalHit,
        "intake.json": IntakeArtifact,
    }
    for name, model in mapping.items():
        (d / name).write_text(
            model.model_json_schema().__str__()
            if False
            else __import__("json").dumps(model.model_json_schema(), indent=2) + "\n",
            encoding="utf-8",
        )
