from __future__ import annotations

import json
from itertools import zip_longest
from pathlib import Path
from typing import Any

from .markdown_ir import normalize_text
from .text_metrics import char_ngram_fscore, weighted_mean


def _load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"failed to read json: {exc}"
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, f"failed to parse json: {exc}"


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def score_json_structure(
    actual_path: Path, expected_path: Path, policy: dict[str, object]
) -> tuple[float | None, dict[str, object]]:
    if not actual_path.is_file() or not expected_path.is_file():
        missing: list[str] = []
        if not actual_path.is_file():
            missing.append(str(actual_path))
        if not expected_path.is_file():
            missing.append(str(expected_path))
        return None, {"available": False, "reason": "missing json baseline or result: " + ", ".join(missing)}

    actual, actual_error = _load_json(actual_path)
    if actual_error is not None:
        return None, {"available": False, "reason": actual_error, "path": str(actual_path)}
    expected, expected_error = _load_json(expected_path)
    if expected_error is not None:
        return None, {"available": False, "reason": expected_error, "path": str(expected_path)}
    if not isinstance(actual, list) or not isinstance(expected, list):
        return None, {"available": False, "reason": "json roots are not page lists"}

    bbox_tolerance = int(policy.get("json_structure", {}).get("bbox_tolerance", 15))
    component_weights = policy.get("json_structure", {}).get("weights", {})

    page_count_score = 1.0 - (abs(len(actual) - len(expected)) / max(len(actual), len(expected), 1))

    block_count_parts: list[tuple[float | None, float]] = []
    label_parts: list[tuple[float | None, float]] = []
    bbox_parts: list[tuple[float | None, float]] = []
    content_parts: list[tuple[float | None, float]] = []

    page_details: list[dict[str, object]] = []

    for page_index, (actual_page, expected_page) in enumerate(zip_longest(actual, expected, fillvalue=[])):
        if not isinstance(actual_page, list) or not isinstance(expected_page, list):
            block_count_parts.append((0.0, 1.0))
            label_parts.append((0.0, 1.0))
            bbox_parts.append((0.0, 1.0))
            content_parts.append((0.0, 1.0))
            page_details.append({"page": page_index + 1, "status": "invalid_page"})
            continue

        block_count = 1.0 - (abs(len(actual_page) - len(expected_page)) / max(len(actual_page), len(expected_page), 1))
        block_count_parts.append((block_count, 1.0))

        label_scores: list[float] = []
        bbox_scores: list[float] = []
        content_scores: list[float] = []

        for actual_block, expected_block in zip_longest(actual_page, expected_page, fillvalue={}):
            if not isinstance(actual_block, dict) or not isinstance(expected_block, dict):
                label_scores.append(0.0)
                bbox_scores.append(0.0)
                content_scores.append(0.0)
                continue

            label_scores.append(1.0 if actual_block.get("label") == expected_block.get("label") else 0.0)

            actual_bbox = actual_block.get("bbox_2d")
            expected_bbox = expected_block.get("bbox_2d")
            if (
                isinstance(actual_bbox, list)
                and isinstance(expected_bbox, list)
                and len(actual_bbox) == 4
                and len(expected_bbox) == 4
            ):
                coord_scores: list[float] = []
                for actual_coord, expected_coord in zip(actual_bbox, expected_bbox):
                    actual_int = _as_int(actual_coord)
                    expected_int = _as_int(expected_coord)
                    if actual_int is None or expected_int is None:
                        coord_scores.append(0.0)
                    else:
                        delta = abs(actual_int - expected_int)
                        coord_scores.append(max(0.0, 1.0 - (delta / max(bbox_tolerance, 1))))
                bbox_scores.append(sum(coord_scores) / len(coord_scores))
            else:
                bbox_scores.append(0.0)

            actual_text = normalize_text(str(actual_block.get("content", "")))
            expected_text = normalize_text(str(expected_block.get("content", "")))
            content_scores.append(char_ngram_fscore(actual_text, expected_text))

        label_parts.append((sum(label_scores) / len(label_scores) if label_scores else 1.0, 1.0))
        bbox_parts.append((sum(bbox_scores) / len(bbox_scores) if bbox_scores else 1.0, 1.0))
        content_parts.append((sum(content_scores) / len(content_scores) if content_scores else 1.0, 1.0))

        page_details.append(
            {
                "page": page_index + 1,
                "block_count": round(block_count, 4),
                "labels": round(label_parts[-1][0], 4),
                "bbox": round(bbox_parts[-1][0], 4),
                "content": round(content_parts[-1][0], 4),
            }
        )

    components = {
        "page_count": page_count_score,
        "block_count": weighted_mean(block_count_parts),
        "labels": weighted_mean(label_parts),
        "bbox": weighted_mean(bbox_parts),
        "content": weighted_mean(content_parts),
    }
    overall = weighted_mean((components[name], float(component_weights.get(name, 0.0))) for name in components)
    return overall, {"available": True, "components": components, "pages": page_details}
