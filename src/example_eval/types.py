from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class ExamplePaths:
    name: str
    source_path: Path
    result_dir: Path
    reference_dir: Path
    golden_dir: Path
    rules_path: Path | None


@dataclass(slots=True)
class TableIR:
    rows: list[list[str]]
    source: str


@dataclass(slots=True)
class Block:
    kind: str
    raw_text: str
    canonical_text: str
    table: TableIR | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DocumentIR:
    blocks: list[Block]

    @property
    def non_table_blocks(self) -> list[Block]:
        return [block for block in self.blocks if block.kind != "table"]

    @property
    def table_blocks(self) -> list[Block]:
        return [block for block in self.blocks if block.kind == "table"]


@dataclass(slots=True)
class PairScore:
    available: bool
    overall: float | None
    dimensions: dict[str, float | None]
    details: dict[str, Any] = field(default_factory=dict)
    missing_reason: str | None = None


@dataclass(slots=True)
class RuleCheckResult:
    check_id: str
    check_type: str
    status: str
    severity: str
    message: str


@dataclass(slots=True)
class ExampleEvaluation:
    name: str
    parity: PairScore
    result_to_golden: PairScore
    reference_to_golden: PairScore
    final_dimensions: dict[str, float | None]
    final_overall: float | None
    rule_results: list[RuleCheckResult]
    paths: ExamplePaths
