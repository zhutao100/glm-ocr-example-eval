from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

from .types import ExampleEvaluation


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def _quality_overall(evaluation: ExampleEvaluation) -> float | None:
    if evaluation.result_to_golden.overall is not None:
        return evaluation.result_to_golden.overall
    return evaluation.parity.overall


def _final_minus_quality(evaluation: ExampleEvaluation) -> float | None:
    quality = _quality_overall(evaluation)
    if quality is None or evaluation.final_overall is None:
        return None
    return evaluation.final_overall - quality


def _inflation_warning(
    evaluation: ExampleEvaluation, *, inflation_warn_threshold: float | None
) -> dict[str, object] | None:
    if inflation_warn_threshold is None:
        return None
    delta = _final_minus_quality(evaluation)
    if delta is None or delta < inflation_warn_threshold:
        return None
    return {
        "type": "inflation",
        "metric": "final_minus_quality",
        "value": _round(delta),
        "threshold": inflation_warn_threshold,
        "message": "final_overall significantly exceeds quality_overall (parity-first inflation).",
    }


def _pair_payload(evaluation: ExampleEvaluation, pair_name: str) -> dict[str, object]:
    pair = getattr(evaluation, pair_name)
    return {
        "available": pair.available,
        "overall": _round(pair.overall),
        "dimensions": {key: _round(value) for key, value in pair.dimensions.items()},
        "details": pair.details,
        "missing_reason": pair.missing_reason,
    }


def _write_summary_json(
    out_dir: Path,
    evaluations: list[ExampleEvaluation],
    *,
    fail_under: float | None,
    inflation_warn_threshold: float | None,
) -> None:
    payload = {
        "fail_under": fail_under,
        "inflation_warn_threshold": inflation_warn_threshold,
        "examples": [
            {
                "name": evaluation.name,
                "parity": _pair_payload(evaluation, "parity"),
                "result_to_golden": _pair_payload(evaluation, "result_to_golden"),
                "reference_to_golden": _pair_payload(evaluation, "reference_to_golden"),
                "quality_overall": _round(_quality_overall(evaluation)),
                "final_dimensions": {key: _round(value) for key, value in evaluation.final_dimensions.items()},
                "final_overall": _round(evaluation.final_overall),
                "final_minus_quality": _round(_final_minus_quality(evaluation)),
                "warnings": [
                    warning
                    for warning in [_inflation_warning(evaluation, inflation_warn_threshold=inflation_warn_threshold)]
                    if warning is not None
                ],
                "rules": [
                    {
                        "check_id": rule.check_id,
                        "check_type": rule.check_type,
                        "status": rule.status,
                        "severity": rule.severity,
                        "message": rule.message,
                    }
                    for rule in evaluation.rule_results
                ],
            }
            for evaluation in evaluations
        ],
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_summary_md(
    out_dir: Path,
    evaluations: list[ExampleEvaluation],
    *,
    fail_under: float | None,
    inflation_warn_threshold: float | None,
) -> None:
    rows = [
        "# Example evaluation summary",
        "",
        f"- fail_under: {fail_under if fail_under is not None else 'disabled'}",
        f"- inflation_warn_threshold: {inflation_warn_threshold if inflation_warn_threshold is not None else 'disabled'}",
        "",
        "## How to interpret the scores",
        "",
        "- `parity_overall`: `result` vs `reference_result` (upstream parity/regression signal).",
        "- `quality_overall`: `result_to_golden.overall` when available; otherwise `parity_overall` (absolute usefulness proxy).",
        "- `final_overall`: parity-first score with a small golden correction (see `config/policy.yaml`).",
        "- `final_minus_quality`: diagnostic for parity-first inflation; large values usually mean the upstream baseline is also far from golden.",
        "",
        "| Example | Parity | Quality | Result→Golden | Ref→Golden | Final | Final-Quality | Rules | Warnings |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for evaluation in evaluations:
        rule_failures = sum(1 for rule in evaluation.rule_results if rule.status == "fail")
        quality = _round(_quality_overall(evaluation))
        inflation = _round(_final_minus_quality(evaluation))
        warning = _inflation_warning(evaluation, inflation_warn_threshold=inflation_warn_threshold)
        warning_cell = "inflation" if warning is not None else ""
        rows.append(
            f"| `{evaluation.name}` | {_round(evaluation.parity.overall)} | {quality} | {_round(evaluation.result_to_golden.overall)} | {_round(evaluation.reference_to_golden.overall)} | {_round(evaluation.final_overall)} | {inflation} | {rule_failures}/{len(evaluation.rule_results)} fail | {warning_cell} |"
        )
    rows.append("")
    rows.append("## Per-example notes")
    rows.append("")
    for evaluation in evaluations:
        quality = _round(_quality_overall(evaluation))
        inflation = _round(_final_minus_quality(evaluation))
        warning = _inflation_warning(evaluation, inflation_warn_threshold=inflation_warn_threshold)
        rows.append(f"### `{evaluation.name}`")
        rows.append("")
        rows.append(f"- parity.text_fidelity: {_round(evaluation.parity.dimensions.get('text_fidelity'))}")
        rows.append(f"- parity.critical_structure: {_round(evaluation.parity.dimensions.get('critical_structure'))}")
        rows.append(f"- parity.decorative_style: {_round(evaluation.parity.dimensions.get('decorative_style'))}")
        rows.append(f"- quality_overall: {quality}")
        rows.append(f"- final_overall: {_round(evaluation.final_overall)}")
        rows.append(f"- final_minus_quality: {inflation}")
        if warning is not None:
            rows.append(f"- warning: {warning['message']} (value={warning['value']}, threshold={warning['threshold']})")
        if evaluation.rule_results:
            rows.append("- rules:")
            for rule in evaluation.rule_results:
                rows.append(f"  - [{rule.status}] {rule.check_id}: {rule.message}")
        rows.append("")
    (out_dir / "summary.md").write_text("\n".join(rows), encoding="utf-8")


def _write_example_reports(out_dir: Path, evaluations: list[ExampleEvaluation]) -> None:
    examples_dir = out_dir / "examples"
    examples_dir.mkdir(parents=True, exist_ok=True)
    for evaluation in evaluations:
        quality = _round(_quality_overall(evaluation))
        inflation = _round(_final_minus_quality(evaluation))
        example_dir = examples_dir / evaluation.name
        example_dir.mkdir(parents=True, exist_ok=True)
        (example_dir / "report.json").write_text(
            json.dumps(
                {
                    "name": evaluation.name,
                    "parity": _pair_payload(evaluation, "parity"),
                    "result_to_golden": _pair_payload(evaluation, "result_to_golden"),
                    "reference_to_golden": _pair_payload(evaluation, "reference_to_golden"),
                    "quality_overall": quality,
                    "final_dimensions": {key: _round(value) for key, value in evaluation.final_dimensions.items()},
                    "final_overall": _round(evaluation.final_overall),
                    "final_minus_quality": inflation,
                    "rules": [
                        {
                            "check_id": rule.check_id,
                            "check_type": rule.check_type,
                            "status": rule.status,
                            "severity": rule.severity,
                            "message": rule.message,
                        }
                        for rule in evaluation.rule_results
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        md_lines = [
            f"# `{evaluation.name}`",
            "",
            f"- parity_overall: {_round(evaluation.parity.overall)}",
            f"- result_to_golden_overall: {_round(evaluation.result_to_golden.overall)}",
            f"- reference_to_golden_overall: {_round(evaluation.reference_to_golden.overall)}",
            f"- quality_overall: {quality}",
            f"- final_overall: {_round(evaluation.final_overall)}",
            f"- final_minus_quality: {inflation}",
            "",
            "## Final dimensions",
            "",
        ]
        for name, value in evaluation.final_dimensions.items():
            md_lines.append(f"- {name}: {_round(value)}")
        md_lines.append("")
        md_lines.append("## Rules")
        md_lines.append("")
        if evaluation.rule_results:
            for rule in evaluation.rule_results:
                md_lines.append(f"- [{rule.status}] `{rule.check_id}` ({rule.check_type}): {rule.message}")
        else:
            md_lines.append("- none")
        md_lines.append("")
        (example_dir / "report.md").write_text("\n".join(md_lines), encoding="utf-8")


def _write_junit(out_dir: Path, evaluations: list[ExampleEvaluation], *, fail_under: float | None) -> None:
    cases: list[str] = []
    failures = 0
    for evaluation in evaluations:
        failure_messages: list[str] = []
        if fail_under is not None and evaluation.final_overall is not None and evaluation.final_overall < fail_under:
            failure_messages.append(f"final_overall {_round(evaluation.final_overall)} below threshold {fail_under}")
        for rule in evaluation.rule_results:
            if rule.status == "fail" and rule.severity == "error":
                failure_messages.append(f"rule {rule.check_id} failed: {rule.message}")
        body_parts: list[str] = []
        if failure_messages:
            failures += 1
            for message in failure_messages:
                body_parts.append(f'<failure message="{escape(message)}"></failure>')
        body = "".join(body_parts)
        cases.append(f'<testcase classname="example_eval" name="{escape(evaluation.name)}">{body}</testcase>')
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<testsuite name="example_eval" tests="{len(evaluations)}" failures="{failures}">'
        + "".join(cases)
        + "</testsuite>"
    )
    (out_dir / "junit.xml").write_text(xml, encoding="utf-8")


def write_reports(
    out_dir: Path,
    evaluations: list[ExampleEvaluation],
    *,
    fail_under: float | None,
    inflation_warn_threshold: float | None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_summary_json(
        out_dir,
        evaluations,
        fail_under=fail_under,
        inflation_warn_threshold=inflation_warn_threshold,
    )
    _write_summary_md(
        out_dir,
        evaluations,
        fail_under=fail_under,
        inflation_warn_threshold=inflation_warn_threshold,
    )
    _write_example_reports(out_dir, evaluations)
    _write_junit(out_dir, evaluations, fail_under=fail_under)
