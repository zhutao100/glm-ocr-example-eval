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
- **result_to_golden_overall**: `result` vs `golden_result`
- **reference_to_golden_overall**: `reference_result` vs `golden_result`
- **quality_overall** (derived): `result_to_golden_overall` when available; otherwise `parity_overall`
- **final_overall**: parity-first score with a small golden correction
- **final_minus_quality** (diagnostic): `final_overall - quality_overall` (high values usually mean upstream is also far from golden)

Recommended usage:

- use `parity_overall` / `final_overall` for regression detection against upstream reference
- use `quality_overall` for absolute OCR usefulness when a golden baseline exists

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

Note: `--example` must match an example discovered from `examples/source/*` stems; unknown names now fail fast.

Fail the command if any example falls below a threshold:

```bash
uv run --project tools/example_eval example-eval evaluate --repo-root . --fail-under 0.90
```

`--fail-under` must be within `[0, 1]`.

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
      code.yaml
      handwritten.yaml
      page.yaml
      paper.yaml
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
- rule adjudication strength/weights
- report thresholds (e.g., inflation warnings)
- optional CI failure threshold

### `config/rules/*.yaml`

Stores deterministic, example-specific checks (with severities like `minor`/`major`/`critical`). The repo currently includes:

- `handwritten.yaml` to reward the corrected `人间` reading
- `GLM-4.5V_Pages_1_2_3.yaml` to encode the verified page-boundary/continuation notes
- `page.yaml` to anchor the `0.2\\mathrm{N} / \\mathrm{mm}^{2}` glue-strength constant/unit
- `paper.yaml` to anchor fragile math/notation phrases (e.g., `not divisible by Q`, `\\nabla^2`)
- `code.yaml` to anchor critical XML tags/identifiers (e.g., `local-jndi-name`, `weblogic-rdbms-bean`)

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
