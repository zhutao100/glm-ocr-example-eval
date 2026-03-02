from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import ExampleEvalError
from .markdown_ir import normalize_text
from .types import RuleCheckResult


def load_rules(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExampleEvalError(f"Failed to read rule file: {path}") from exc
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ExampleEvalError(f"Failed to parse rule YAML: {path}") from exc
    checks = data.get("checks", [])
    if not isinstance(checks, list):
        raise ExampleEvalError(f"Rule file checks must be a list: {path}")
    return [check for check in checks if isinstance(check, dict)]


def page_segments_from_markdown(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\f" in text:
        pages = text.split("\f")
    else:
        pages = text.split("\n---\n")
    return [normalize_text(page) for page in pages]


def _contains_any(text: str, phrases: list[str]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(phrase) in normalized for phrase in phrases if phrase)


def _as_positive_int(value: Any, *, default: int | None = None) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _normalized_alternatives(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def evaluate_rules(
    markdown_text: str,
    checks: list[dict[str, Any]],
    *,
    page_texts: list[str] | None = None,
) -> list[RuleCheckResult]:
    pages = [normalize_text(page) for page in page_texts] if page_texts else page_segments_from_markdown(markdown_text)
    whole = normalize_text("\n".join(pages) if pages else markdown_text)
    results: list[RuleCheckResult] = []

    for check in checks:
        check_id = str(check.get("id", "unnamed"))
        check_type = str(check.get("type", "unknown"))
        severity = str(check.get("severity", "warn")).lower()
        if severity not in {"warn", "error"}:
            severity = "warn"
        status = "pass"
        message = ""

        if check_type == "contains":
            phrases = [str(check.get("must_contain", ""))] + _normalized_alternatives(check.get("alternatives"))
            if _contains_any(whole, phrases):
                message = f"Found required phrase for {check_id}."
            else:
                status = "fail"
                message = f"Missing required phrase: {phrases[0]!r}."

        elif check_type == "page_start":
            page_number = _as_positive_int(check.get("page"), default=1)
            if page_number is None:
                status = "fail"
                message = "Invalid rule: page must be a positive integer."
            else:
                page_text = pages[page_number - 1] if 0 < page_number <= len(pages) else ""
                phrases = [str(check.get("must_contain", ""))] + _normalized_alternatives(check.get("alternatives"))
                if _contains_any(page_text[: max(400, len(page_text) // 3)], phrases):
                    message = f"Page {page_number} start matched expected content."
                else:
                    status = "fail"
                    message = f"Page {page_number} start did not contain the expected phrase."

        elif check_type == "page_end":
            page_number = _as_positive_int(check.get("page"), default=1)
            if page_number is None:
                status = "fail"
                message = "Invalid rule: page must be a positive integer."
            else:
                page_text = pages[page_number - 1] if 0 < page_number <= len(pages) else ""
                phrases = [str(check.get("must_contain", ""))] + _normalized_alternatives(check.get("alternatives"))
                tail = page_text[-max(400, len(page_text) // 3) :]
                if _contains_any(tail, phrases):
                    message = f"Page {page_number} end matched expected content."
                else:
                    status = "fail"
                    message = f"Page {page_number} end did not contain the expected phrase."

        elif check_type == "continuation":
            left_page = _as_positive_int(check.get("left_page"), default=1)
            right_page = _as_positive_int(
                check.get("right_page"), default=(left_page + 1) if left_page is not None else None
            )
            if left_page is None or right_page is None:
                status = "fail"
                message = "Invalid rule: left_page and right_page must be positive integers."
            else:
                left_text = pages[left_page - 1] if 0 < left_page <= len(pages) else ""
                right_text = pages[right_page - 1] if 0 < right_page <= len(pages) else ""
                left_phrase = str(check.get("left_must_contain", ""))
                right_phrase = str(check.get("right_must_contain", ""))
                if _contains_any(left_text, [left_phrase]) and _contains_any(right_text, [right_phrase]):
                    message = f"Continuation across pages {left_page} -> {right_page} matched."
                else:
                    status = "fail"
                    message = f"Continuation across pages {left_page} -> {right_page} did not match."

        else:
            status = "warn"
            message = f"Unknown check type {check_type!r}; skipped."

        results.append(
            RuleCheckResult(
                check_id=check_id,
                check_type=check_type,
                status=status,
                severity=severity,
                message=message,
            )
        )

    return results
