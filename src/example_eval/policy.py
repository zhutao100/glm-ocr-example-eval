from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_POLICY: dict[str, Any] = {
    "weights": {
        "text_fidelity": 0.60,
        "critical_structure": 0.35,
        "decorative_style": 0.05,
    },
    "critical_structure_components": {
        "table": 0.50,
        "json_structure": 0.35,
        "block_shape": 0.15,
    },
    "text_block_kind_weights": {
        "heading": 1.15,
        "paragraph": 1.00,
        "list_item": 1.00,
        "formula": 1.10,
        "code": 1.25,
        "table": 1.30,
        "html": 0.95,
        "other": 1.00,
    },
    "code_block_text_weights": {
        "exact_line_match": 0.70,
        "char_fscore": 0.30,
    },
    "golden_adjudication": {
        "strength": 0.25,
        "deadband": 0.02,
    },
    "rule_adjudication": {
        "strength": 0.05,
    },
    "json_structure": {
        "bbox_tolerance": 15,
        "weights": {
            "page_count": 0.15,
            "block_count": 0.20,
            "labels": 0.25,
            "bbox": 0.20,
            "content": 0.20,
        },
    },
    "report": {
        "fail_under": None,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_policy(path: Path | None) -> dict[str, Any]:
    if path is None:
        return deepcopy(DEFAULT_POLICY)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Policy must be a mapping: {path}")
    return _deep_merge(DEFAULT_POLICY, data)
