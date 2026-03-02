# glm-ocr-example-eval

This repository is a sub-project intended to be integrated at the `tools/example_eval` of the main `GLM-OCR` project. It scores the `examples/result` against:

- `examples/reference_result` for upstream parity
- `examples/golden_result` for golden-adjudicated quality
- `tools/example_eval/config/rules/*.yaml` for deterministic example-specific checks

The evaluator is intentionally **stand-alone from the main project**. It lives under
`tools/example_eval/`, reads the existing example corpus, and writes reports under
`.build/example_eval/` in the project root.

## What it scores

The scorer produces three primary dimensions per example:

- **text_fidelity**: first-class text/content quality, including stricter handling for fenced code
- **critical_structure**: first-class structure quality, especially tables and OCR JSON block structure
- **decorative_style**: second-class markdown/style fidelity (bold, centering wrappers, fence labels, etc.)

It then computes:

- **parity_overall**: `result` vs `reference_result`
- **golden_result_overall**: `result` vs `golden_result`
- **reference_to_golden_overall**: `reference_result` vs `golden_result`
- **final_overall**: parity adjusted by whether the result is better or worse than upstream when judged against golden

## Quick start

From the project root:

```bash
uv run --project tools/example_eval example-eval evaluate --repo-root .
```

Or without installing the package:

```bash
PYTHONPATH=tools/example_eval/src python -m example_eval evaluate --repo-root .
```

The default report directory is:

```text
.build/example_eval/
```

## Useful commands

Evaluate all examples:

```bash
uv run --project tools/example_eval example-eval evaluate --repo-root .
```

Evaluate one example:

```bash
uv run --project tools/example_eval example-eval evaluate --repo-root . --example handwritten
```

Fail the command if any example falls below a threshold:

```bash
uv run --project tools/example_eval example-eval evaluate --repo-root . --fail-under 0.90
```

Run tests:

```bash
uv run --project tools/example_eval pytest tools/example_eval/tests
```

## Repo layout

```text
tools/example_eval/
  README.md
  AGENTS.md
  pyproject.toml
  config/
    policy.yaml
    rules/
      GLM-4.5V_Pages_1_2_3.yaml
      handwritten.yaml
  src/example_eval/
    cli.py
    evaluator.py
    json_metrics.py
    markdown_ir.py
    policy.py
    report.py
    rules.py
    text_metrics.py
    types.py
  tests/
```

## Configuration

### `config/policy.yaml`

Controls:

- scoring weights
- table vs JSON structure weighting
- golden adjudication strength
- optional CI failure threshold

### `config/rules/*.yaml`

Stores deterministic, example-specific checks. The starter repo already includes:

- `handwritten.yaml` to reward the corrected `人间` reading
- `GLM-4.5V_Pages_1_2_3.yaml` to encode the verified page-boundary/continuation notes

## Notes on implementation scope

This scaffold is meant to be immediately useful, not just aspirational. It already:

- canonicalizes HTML tables and Markdown pipe tables to the same internal representation
- scores prose/code/table content separately
- reads OCR JSON block lists for structural signals
- applies golden adjudication per dimension
- emits Markdown, JSON, and JUnit reports

It is still a starter repo. Obvious next extensions are:

- stronger Markdown/HTML AST canonicalization
- richer table tree-edit metrics
- more rule types
- CI wiring in the parent repository
