from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .errors import ExampleEvalError
from .json_metrics import score_json_structure
from .markdown_ir import parse_markdown_document
from .policy import load_policy
from .report import write_reports
from .rules import evaluate_rules, load_rules
from .text_metrics import (
    score_block_shape,
    score_block_text_fidelity,
    score_decorative_style,
    score_table_blocks,
    weighted_mean,
)
from .types import ExampleEvaluation, ExamplePaths, PairScore


def _tool_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_policy_path() -> Path:
    return _tool_root() / "config" / "policy.yaml"


def default_rules_root() -> Path:
    return _tool_root() / "config" / "rules"


def discover_examples(repo_root: Path) -> list[ExamplePaths]:
    source_root = repo_root / "examples" / "source"
    result_root = repo_root / "examples" / "result"
    reference_root = repo_root / "examples" / "reference_result"
    golden_root = repo_root / "examples" / "golden_result"
    rules_root = default_rules_root()

    if not source_root.is_dir():
        raise ExampleEvalError(f"Missing examples/source directory under repo root: {source_root}")

    supported = {".png", ".jpg", ".jpeg", ".pdf"}
    examples: list[ExamplePaths] = []
    for source_path in sorted(source_root.iterdir()):
        if not source_path.is_file() or source_path.suffix.lower() not in supported:
            continue
        name = source_path.stem
        rules_path = rules_root / f"{name}.yaml"
        examples.append(
            ExamplePaths(
                name=name,
                source_path=source_path,
                result_dir=result_root / name,
                reference_dir=reference_root / name,
                golden_dir=golden_root / name,
                rules_path=rules_path if rules_path.is_file() else None,
            )
        )
    return examples


def _read_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _read_text_with_reason(path: Path) -> tuple[str | None, str | None]:
    if not path.is_file():
        return None, "missing"
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError as exc:
        return None, f"utf-8 decode error: {exc}"
    except OSError as exc:
        return None, f"read error: {exc}"


def _rule_pass_rate(rule_results: list[Any]) -> float | None:
    if not rule_results:
        return None
    passed = sum(1 for result in rule_results if result.status == "pass")
    return passed / len(rule_results)


def _page_texts_from_json(path: Path) -> list[str] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, list):
        return None
    page_texts: list[str] = []
    for page in payload:
        if not isinstance(page, list):
            page_texts.append("")
            continue
        parts: list[str] = []
        for block in page:
            if not isinstance(block, dict):
                continue
            content = str(block.get("content", "")).strip()
            if content:
                parts.append(content)
        page_texts.append("\n".join(parts))
    return page_texts


def _score_pair(actual_dir: Path, expected_dir: Path, example_name: str, policy: dict[str, Any]) -> PairScore:
    actual_md_path = actual_dir / f"{example_name}.md"
    expected_md_path = expected_dir / f"{example_name}.md"
    actual_md, actual_error = _read_text_with_reason(actual_md_path)
    expected_md, expected_error = _read_text_with_reason(expected_md_path)

    if actual_md is None or expected_md is None:
        missing_parts = []
        if actual_md is None:
            missing_parts.append(f"{actual_md_path} ({actual_error})")
        if expected_md is None:
            missing_parts.append(f"{expected_md_path} ({expected_error})")
        return PairScore(
            available=False,
            overall=None,
            dimensions={"text_fidelity": None, "critical_structure": None, "decorative_style": None},
            details={},
            missing_reason="missing markdown: " + ", ".join(missing_parts),
        )

    try:
        actual_doc = parse_markdown_document(actual_md)
        expected_doc = parse_markdown_document(expected_md)
    except Exception as exc:
        return PairScore(
            available=False,
            overall=None,
            dimensions={"text_fidelity": None, "critical_structure": None, "decorative_style": None},
            details={},
            missing_reason=f"failed to parse markdown: {exc}",
        )

    text_fidelity, text_details = score_block_text_fidelity(
        actual_doc.non_table_blocks, expected_doc.non_table_blocks, policy
    )
    table_score, table_details = score_table_blocks(actual_doc.table_blocks, expected_doc.table_blocks)
    block_shape = score_block_shape(actual_doc.blocks, expected_doc.blocks)
    decorative_style, style_details = score_decorative_style(actual_doc.blocks, expected_doc.blocks)

    json_score, json_details = score_json_structure(
        actual_dir / f"{example_name}.json",
        expected_dir / f"{example_name}.json",
        policy,
    )

    critical_weights = policy.get("critical_structure_components", {})
    include_block_shape = table_score is not None or json_score is not None
    critical_structure = weighted_mean(
        [
            (table_score, float(critical_weights.get("table", 0.50))),
            (json_score, float(critical_weights.get("json_structure", 0.35))),
            (block_shape if include_block_shape else None, float(critical_weights.get("block_shape", 0.15))),
        ]
    )

    overall_weights = policy.get("weights", {})
    dimensions = {
        "text_fidelity": text_fidelity,
        "critical_structure": critical_structure,
        "decorative_style": decorative_style,
    }
    overall = weighted_mean(
        [
            (dimensions["text_fidelity"], float(overall_weights.get("text_fidelity", 0.60))),
            (dimensions["critical_structure"], float(overall_weights.get("critical_structure", 0.35))),
            (dimensions["decorative_style"], float(overall_weights.get("decorative_style", 0.05))),
        ]
    )

    return PairScore(
        available=True,
        overall=overall,
        dimensions=dimensions,
        details={
            "text": text_details,
            "tables": table_details,
            "json": json_details,
            "style": style_details,
            "block_shape": block_shape,
        },
    )


def _finalize_dimensions(
    parity: PairScore, result_to_golden: PairScore, reference_to_golden: PairScore, policy: dict[str, Any]
) -> tuple[dict[str, float | None], float | None]:
    strength = float(policy.get("golden_adjudication", {}).get("strength", 0.25))
    deadband = float(policy.get("golden_adjudication", {}).get("deadband", 0.02))

    final_dimensions: dict[str, float | None] = {}
    for name in ["text_fidelity", "critical_structure", "decorative_style"]:
        parity_value = parity.dimensions.get(name)
        result_value = result_to_golden.dimensions.get(name)
        reference_value = reference_to_golden.dimensions.get(name)
        if parity_value is None:
            final_dimensions[name] = None
            continue
        if result_value is None or reference_value is None:
            final_dimensions[name] = parity_value
            continue
        delta = result_value - reference_value
        if abs(delta) < deadband:
            delta = 0.0
        final_dimensions[name] = max(0.0, min(1.0, parity_value + strength * delta))

    overall_weights = policy.get("weights", {})
    final_overall = weighted_mean(
        [
            (final_dimensions.get("text_fidelity"), float(overall_weights.get("text_fidelity", 0.60))),
            (final_dimensions.get("critical_structure"), float(overall_weights.get("critical_structure", 0.35))),
            (final_dimensions.get("decorative_style"), float(overall_weights.get("decorative_style", 0.05))),
        ]
    )
    return final_dimensions, final_overall


def evaluate_repo(
    repo_root: Path,
    *,
    policy_path: Path | None = None,
    out_dir: Path | None = None,
    examples: list[str] | None = None,
    fail_under: float | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    if not repo_root.is_dir():
        raise ExampleEvalError(f"--repo-root must be a directory: {repo_root}")
    if fail_under is not None and not (0.0 <= fail_under <= 1.0):
        raise ExampleEvalError("--fail-under must be within [0, 1].")
    policy = load_policy(policy_path or default_policy_path())
    discovered = discover_examples(repo_root)
    if not discovered:
        raise ExampleEvalError(f"No examples discovered under: {repo_root / 'examples' / 'source'}")

    requested = set(examples or [])
    if requested:
        discovered_names = {example.name for example in discovered}
        unknown = sorted(requested - discovered_names)
        if unknown:
            known = ", ".join(sorted(discovered_names)[:10])
            suffix = "" if len(discovered_names) <= 10 else f" (and {len(discovered_names) - 10} more)"
            raise ExampleEvalError(f"Unknown example(s): {', '.join(unknown)}. Known examples include: {known}{suffix}")
        selected = [example for example in discovered if example.name in requested]
    else:
        selected = discovered

    evaluations: list[ExampleEvaluation] = []
    for example in selected:
        parity = _score_pair(example.result_dir, example.reference_dir, example.name, policy)
        result_to_golden = _score_pair(example.result_dir, example.golden_dir, example.name, policy)
        reference_to_golden = _score_pair(example.reference_dir, example.golden_dir, example.name, policy)

        result_md = _read_text(example.result_dir / f"{example.name}.md") or ""
        result_page_texts = _page_texts_from_json(example.result_dir / f"{example.name}.json")
        reference_md = _read_text(example.reference_dir / f"{example.name}.md") or ""
        reference_page_texts = _page_texts_from_json(example.reference_dir / f"{example.name}.json")
        rules = load_rules(example.rules_path)
        rule_results = evaluate_rules(result_md, rules, page_texts=result_page_texts)
        reference_rule_results = evaluate_rules(reference_md, rules, page_texts=reference_page_texts) if rules else []

        final_dimensions, final_overall = _finalize_dimensions(parity, result_to_golden, reference_to_golden, policy)
        result_rule_rate = _rule_pass_rate(rule_results)
        reference_rule_rate = _rule_pass_rate(reference_rule_results)
        if final_overall is not None and result_rule_rate is not None and reference_rule_rate is not None:
            rule_strength = float(policy.get("rule_adjudication", {}).get("strength", 0.05))
            final_overall = max(0.0, min(1.0, final_overall + rule_strength * (result_rule_rate - reference_rule_rate)))
        evaluations.append(
            ExampleEvaluation(
                name=example.name,
                parity=parity,
                result_to_golden=result_to_golden,
                reference_to_golden=reference_to_golden,
                final_dimensions=final_dimensions,
                final_overall=final_overall,
                rule_results=rule_results,
                paths=example,
            )
        )

    effective_fail_under = fail_under
    if effective_fail_under is None:
        configured = policy.get("report", {}).get("fail_under")
        effective_fail_under = float(configured) if configured is not None else None

    output_root = out_dir or (repo_root / ".build" / "example_eval")
    write_reports(output_root, evaluations, fail_under=effective_fail_under)

    should_fail = False
    if effective_fail_under is not None:
        for evaluation in evaluations:
            if evaluation.final_overall is not None and evaluation.final_overall < effective_fail_under:
                should_fail = True
                break
    if any(
        result.status == "fail" and result.severity == "error"
        for evaluation in evaluations
        for result in evaluation.rule_results
    ):
        should_fail = True

    return {
        "repo_root": str(repo_root),
        "out_dir": str(output_root),
        "policy": policy,
        "examples": evaluations,
        "should_fail": should_fail,
    }
