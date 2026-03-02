# Agent notes

## Purpose

This tool evaluates the OCR/example outputs under `examples/result` against two baselines:

1. `examples/reference_result` for upstream parity
2. `examples/golden_result` for adjudicated quality

The key design constraint is: **parity remains the primary target, but the golden baseline can reward genuine improvements or penalize regressions**.

## Main entry point

- CLI: `src/example_eval/cli.py`
- Main command: `example-eval evaluate --repo-root .`

## Important modules

- `policy.py`: loads the scoring policy YAML and fills defaults
- `markdown_ir.py`: canonicalizes markdown-like OCR output into block IR and table IR
- `text_metrics.py`: text, block, table, and style metrics
- `json_metrics.py`: OCR JSON block-list structural metrics
- `rules.py`: deterministic example-specific checks
- `evaluator.py`: pairwise scoring + golden adjudication
- `report.py`: summary/report writers

## Assumptions

- Example names come from `examples/source/*` stems.
- Each example output lives in `examples/{result,reference_result,golden_result}/{name}/`.
- Markdown file is `{name}.md`.
- OCR JSON file is `{name}.json` when present.
- Images, when present, live under `imgs/`.

## Extension guidance

If you add a new metric:

1. keep it continuous in `[0, 1]`
2. wire it into a named dimension, not directly into the final score
3. let `policy.yaml` control its weighting
4. keep the golden adjudication formula unchanged unless there is a strong reason to revise it

## Current intentional simplifications

- Table scoring uses canonical rows/cells, row/column shape similarity, and cell text similarity; it does not implement full TEDS.
- Text scoring uses a char n-gram F-score style metric implemented locally, avoiding heavy runtime dependencies.
- Rule evaluation is deliberately deterministic and transparent, favoring maintainability over benchmark-style complexity.

## Useful Tools / Resources

- use Python virtual env `playground313` for development within this tool, you may modify the packages in this env as needed.
