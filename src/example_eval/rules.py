from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .markdown_ir import normalize_text
from .types import RuleCheckResult


def load_rules(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    checks = data.get("checks", [])
    if not isinstance(checks, list):
        raise ValueError(f"Rule file checks must be a list: {path}")
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
        severity = str(check.get("severity", "warn"))
        status = "pass"
        message = ""

        if check_type == "contains":
            phrases = [str(check.get("must_contain", ""))] + [str(item) for item in check.get("alternatives", [])]
            if _contains_any(whole, phrases):
                message = f"Found required phrase for {check_id}."
            else:
                status = "fail"
                message = f"Missing required phrase: {phrases[0]!r}."

        elif check_type == "page_start":
            page_number = int(check.get("page", 1))
            page_text = pages[page_number - 1] if 0 < page_number <= len(pages) else ""
            phrases = [str(check.get("must_contain", ""))] + [str(item) for item in check.get("alternatives", [])]
            if _contains_any(page_text[: max(400, len(page_text) // 3)], phrases):
                message = f"Page {page_number} start matched expected content."
            else:
                status = "fail"
                message = f"Page {page_number} start did not contain the expected phrase."

        elif check_type == "page_end":
            page_number = int(check.get("page", 1))
            page_text = pages[page_number - 1] if 0 < page_number <= len(pages) else ""
            phrases = [str(check.get("must_contain", ""))] + [str(item) for item in check.get("alternatives", [])]
            tail = page_text[-max(400, len(page_text) // 3) :]
            if _contains_any(tail, phrases):
                message = f"Page {page_number} end matched expected content."
            else:
                status = "fail"
                message = f"Page {page_number} end did not contain the expected phrase."

        elif check_type == "continuation":
            left_page = int(check.get("left_page", 1))
            right_page = int(check.get("right_page", left_page + 1))
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
