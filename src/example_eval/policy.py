from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .errors import ExampleEvalError

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


def _require_mapping(value: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExampleEvalError(f"Policy field {path} must be a mapping.")
    return value


def _require_number(value: Any, *, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExampleEvalError(f"Policy field {path} must be a number.")
    as_float = float(value)
    if as_float != as_float:  # NaN
        raise ExampleEvalError(f"Policy field {path} must not be NaN.")
    return as_float


def _validate_weight_mapping(policy: dict[str, Any], *, path: str) -> None:
    mapping = _require_mapping(policy.get(path, {}), path=path)
    weights = []
    for key, value in mapping.items():
        weight = _require_number(value, path=f"{path}.{key}")
        if weight < 0:
            raise ExampleEvalError(f"Policy field {path}.{key} must be non-negative.")
        weights.append(weight)
    if weights and sum(weights) <= 0:
        raise ExampleEvalError(f"Policy field {path} must have a positive total weight.")


def _validate_policy(policy: dict[str, Any]) -> None:
    _validate_weight_mapping(policy, path="weights")
    _validate_weight_mapping(policy, path="critical_structure_components")
    _validate_weight_mapping(policy, path="text_block_kind_weights")
    _validate_weight_mapping(policy, path="code_block_text_weights")

    golden = _require_mapping(policy.get("golden_adjudication", {}), path="golden_adjudication")
    strength = _require_number(golden.get("strength", 0.25), path="golden_adjudication.strength")
    if strength < 0:
        raise ExampleEvalError("Policy field golden_adjudication.strength must be non-negative.")
    deadband = _require_number(golden.get("deadband", 0.02), path="golden_adjudication.deadband")
    if deadband < 0:
        raise ExampleEvalError("Policy field golden_adjudication.deadband must be non-negative.")

    rule_adj = _require_mapping(policy.get("rule_adjudication", {}), path="rule_adjudication")
    strength = _require_number(rule_adj.get("strength", 0.05), path="rule_adjudication.strength")
    if strength < 0:
        raise ExampleEvalError("Policy field rule_adjudication.strength must be non-negative.")

    json_policy = _require_mapping(policy.get("json_structure", {}), path="json_structure")
    bbox_tolerance = json_policy.get("bbox_tolerance", 15)
    if isinstance(bbox_tolerance, bool):
        raise ExampleEvalError("Policy field json_structure.bbox_tolerance must be an integer.")
    try:
        parsed = int(bbox_tolerance)
    except (TypeError, ValueError) as exc:
        raise ExampleEvalError("Policy field json_structure.bbox_tolerance must be an integer.") from exc
    if parsed < 0:
        raise ExampleEvalError("Policy field json_structure.bbox_tolerance must be non-negative.")

    json_weights = json_policy.get("weights", {})
    if json_weights is not None:
        _validate_weight_mapping(json_policy, path="weights")


def load_policy(path: Path | None) -> dict[str, Any]:
    if path is None:
        return deepcopy(DEFAULT_POLICY)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExampleEvalError(f"Failed to read policy file: {path}") from exc
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ExampleEvalError(f"Failed to parse policy YAML: {path}") from exc
    if not isinstance(data, dict):
        raise ExampleEvalError(f"Policy must be a mapping: {path}")
    merged = _deep_merge(DEFAULT_POLICY, data)
    _validate_policy(merged)
    return merged
