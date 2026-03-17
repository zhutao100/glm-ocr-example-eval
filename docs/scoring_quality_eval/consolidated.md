# Scoring quality evaluation (consolidated)

This document consolidates the two parallel writeups:

- `docs/scoring_quality_eval/evaluation_1.md`
- `docs/scoring_quality_eval/evaluation_2.md`

It cross-validates their claims against the current scorer implementation in this repo and against the latest checked-out external example outputs for the two compared projects.

## What we validated in the codebase

### 1) The scorer’s headline `final_overall` is parity-first by design

From `config/policy.yaml` and `src/example_eval/evaluator.py`:

- Base: `parity = result vs reference_result`
- Golden comparisons: `result_to_golden` and `reference_to_golden`
- Per-dimension finalization:

  - `final_dim = parity_dim + strength * (result_to_golden_dim - reference_to_golden_dim)` with a deadband
  - default `strength = 0.25`, `deadband = 0.02`
- Optional rule adjustment:

  - `final_overall += rule_strength * (result_rule_pass_rate - reference_rule_pass_rate)`
  - default `rule_strength = 0.05`

Net: `final_overall` is an **upstream-parity score with a small golden correction**, not an absolute “OCR quality” score.

### 2) Golden structural signal is currently missing for almost all examples

In both external repos’ `examples/golden_result/*/`, golden baselines are markdown-only (no `*.json`), so:

- `result_to_golden.dimensions.critical_structure` is `None` for every example except `table` (which can be scored via table IR).
- Golden adjudication therefore cannot meaningfully affect `critical_structure`, and mostly only nudges `text_fidelity` (and tiny `decorative_style`).

This is the largest reason `final_overall` can look “too high” while absolute golden quality is mediocre.

### 3) Example-specific rule coverage is currently narrow

Only these starter rule files exist:

- `config/rules/handwritten.yaml`
- `config/rules/GLM-4.5V_Pages_1_2_3.yaml`

The most fragile examples (`page`, `paper`, `code`) currently have no deterministic semantic guardrails.

## External results re-run (2026-03-17)

### Inputs (paths + commits)

- Scorer repo: `~/workspace/vlm-ocr/glm-ocr-example-eval` @ `3b6e29ef3deec566580986b9ebe26bf8b51e46e1`
- Project 1: `~/workspace/vlm-ocr/GLM-OCR-Swift` @ `cb0ceb1933434db858665f291b38141f8a712ada`
- Project 2: `~/workspace/vlm-ocr/glm-ocr.swift` @ `c6eefd219dd9246976f406d04b530c8a7aef86f7`

### How to reproduce

From the scorer repo root:

```bash
PYENV_VERSION=venv313 pyenv exec env PYTHONPATH=src \
  python3 -c "from example_eval.cli import main; raise SystemExit(main())" \
  evaluate --repo-root ~/workspace/vlm-ocr/GLM-OCR-Swift

PYENV_VERSION=venv313 pyenv exec env PYTHONPATH=src \
  python3 -c "from example_eval.cli import main; raise SystemExit(main())" \
  evaluate --repo-root ~/workspace/vlm-ocr/glm-ocr.swift
```

Reports are written to `<repo-root>/.build/example_eval/` (see `summary.json` / `summary.md`).

### What “quality” means in the table below

To match the intent in `evaluation_1.md`, we define a derived score:

- `quality_overall = result_to_golden.overall` if a golden markdown exists for that example
- otherwise: `quality_overall = parity.overall` (fallback)

### Per-example comparison (current data)

| Example | P1 parity | P1 quality | P1 final | P2 parity | P2 quality | P2 final | Δ quality (P2−P1) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `GLM-4.5V_Page_1` | 0.7884 | 0.7884 | 0.7884 | 0.7723 | 0.7723 | 0.7723 | -0.0161 |
| `GLM-4.5V_Pages_1_2_3` | 0.7954 | 0.7615 | 0.7816 | 0.7887 | 0.7501 | 0.7730 | -0.0114 |
| `code` | 0.9017 | 0.7171 | 0.9013 | 0.9444 | 0.7202 | 0.9451 | +0.0031 |
| `handwritten` | 0.8448 | 0.7855 | 0.8948 | 0.9873 | 0.8091 | 1.0000 | +0.0236 |
| `page` | 0.7161 | 0.4735 | 0.7020 | 0.8030 | 0.5249 | 0.7973 | +0.0514 |
| `paper` | 0.9636 | 0.6513 | 0.9636 | 0.9853 | 0.6511 | 0.9853 | -0.0002 |
| `seal` | 0.9804 | 0.9808 | 0.9804 | 0.9894 | 0.9808 | 0.9894 | +0.0000 |
| `table` | 0.9944 | 1.0000 | 0.9944 | 0.9987 | 1.0000 | 0.9987 | +0.0000 |

### Headline means (simple mean over 8 examples)

| Metric | Project 1 | Project 2 |
|---|---:|---:|
| mean parity | 0.8731 | 0.9086 |
| mean quality (derived) | 0.7698 | 0.7761 |
| mean final | 0.8758 | 0.9076 |

### Cross-validation note: some numbers in `evaluation_1.md` are stale

The qualitative conclusions in both writeups largely match the current situation, but the per-example numeric table in `evaluation_1.md` no longer matches the current checked-out external results and/or the current scorer behavior (see the table above for an updated run with pinned commits).

## Unified conclusions (what both writeups agree on, after validation)

### 1) `final_overall` is a good parity/regression signal, but can be a misleading “quality” headline

Current runs show large “inflation” (final − quality) on examples where upstream reference is also far from golden, e.g.:

- `paper`: quality ≈ 0.651 while final ≈ 0.964–0.985
- `page`: quality ≈ 0.474–0.525 while final ≈ 0.702–0.797
- `code`: quality ≈ 0.717–0.720 while final ≈ 0.901–0.945

This is expected under the parity-first design and is amplified by missing golden structural baselines.

### 2) Project 2 wins on parity and slightly on golden-quality; Project 1 is slightly better on the long PDF cases

On the current corpus:

- Project 2 is substantially better on **parity** and slightly better on derived **quality** (mainly `page` and `handwritten`).
- Project 1 is slightly better on the long PDF outputs (`GLM-4.5V_Page_1`, `GLM-4.5V_Pages_1_2_3`) under the available baselines.

### 3) The scorer still under-penalizes “semantic” corruption in math/numerics/code

Concrete external-output checks (current external repos):

- `page`: Project 1 drops the key `0.2 N/mm^2`; Project 2 has a decimal but wrong unit/value (`0.5 MPa`).
- `paper`: Project 1 has “not divisible by O” where golden has `Q`; Project 2 fixes this (but the aggregate score barely moves).
- `code`: Project 2’s XML payload contains several more dangerous tag/identifier corruptions than Project 1, yet the scorer prefers Project 2 (parity/fidelity signals outweigh token-exactness).

These are exactly the failure modes where lightweight char n-gram similarity needs help (rules and/or token-aware metrics).

## Consolidated improvement plan (minimal → structural)

### Phase 0 — reporting/interpretation (low risk, immediate)

Goal: remove “quality vs parity” confusion without changing the existing parity-first contract.

- Add `quality_overall` (derived) to `summary.json`/`summary.md` and per-example reports:
  - `quality_overall = result_to_golden.overall if available else parity.overall`
- Add an “inflation” diagnostic:
  - `final_minus_quality = final_overall - quality_overall`
  - surface warnings when `final_minus_quality` exceeds a threshold (e.g., 0.15)
- Document these meanings prominently in `README.md` and `summary.md`:
  - “Use parity/final for regression; use quality for absolute OCR usefulness.”

Status / decisions (implemented in this repo):

- Reports now include:
  - `quality_overall = result_to_golden.overall if available else parity.overall`
  - `final_minus_quality = final_overall - quality_overall` (when both are available)
- Inflation warnings:
  - emitted when `final_minus_quality >= report.inflation_warn_threshold`
  - default threshold: `0.15` (configurable via `config/policy.yaml`)
- Reporting-only change: no scoring contract changes in Phase 0.

### Phase 1 — plug the biggest baseline holes (medium)

Goal: make golden adjudication apply to more than just text similarity.

- Add golden aliasing for `GLM-4.5V_Page_1`:
  - Map it to page 1 of `GLM-4.5V_Pages_1_2_3` golden (config-driven).
- Add a golden-structure fallback when golden JSON is missing:
  - Derive a lightweight structure signature from markdown IR (block-kind sequence, heading levels, table count/shape, image count, formula blocks, page breaks).
  - Score it into `critical_structure` so `result_to_golden` and `reference_to_golden` get non-`None` structure values.

Status / decisions (implemented in this repo):

- Golden aliasing is config-driven via `config/policy.yaml:golden_aliases`.
  - `GLM-4.5V_Page_1` uses `GLM-4.5V_Pages_1_2_3` golden, page `1` (split by `\f` or `\n---\n`).
- `critical_structure_components.block_shape` is replaced by `critical_structure_components.markdown_structure`.
  - `markdown_structure` is a lightweight signature score (continuous `[0, 1]`) combining:
    - block-kind sequence similarity (with image-only lines treated as `image`, and HTML wrapper-only blocks ignored)
    - heading level sequence similarity
    - table shape sequence similarity
    - image / formula / page-break count similarity
  - component aggregation: simple mean over the sub-scores (equal weighting).

### Phase 2 — add semantic guardrails via rules (medium, high ROI)

Goal: make regressions visible on “fragile” examples without heavy ML metrics.

- Add rule YAMLs for:
  - `config/rules/page.yaml` (critical constants/units/formula tags like `0.2N/mm^2`, `(8.1.5-4)`)
  - `config/rules/paper.yaml` (anchors like “not divisible by Q”, key LaTeX substrings)
  - `config/rules/code.yaml` (anchors like `WebLogic Workbook`, `<weblogic-rdbms-bean>`, `</key-cache-size>`)
- Extend rule severities beyond `warn`/`error` (e.g., `minor`/`major`/`critical`) and wire severity into score impact.

### Phase 3 — metric upgrades (higher effort, but removes known mis-rankings)

Goal: reduce reliance on global char similarity where it’s known to be misleading.

- Block alignment:
  - replace `zip_longest` block pairing with sequence alignment (DP) over block kinds + text similarity
  - reduces line-wrap/paragraph-splitting artifacts and strengthens missing-block penalties
- Token-aware scoring:
  - numeric token fidelity (numbers + unit-ish tokens) for digit-heavy blocks
  - LaTeX token fidelity for `$...$` / `$$...$$`
  - stricter code-block fidelity (identifiers/tags, delimiter correctness, closing-tag balance)

### Phase 4 — calibration tests + end-to-end score snapshots (to prevent regressions)

- Add tests in `tests/` for the observed failure modes:
  - `code` should penalize broken closing tags and tag-name corruption
  - `page` should strongly penalize key constant/unit corruption
  - `paper` should reflect Q vs O and basic LaTeX structure
- Record end-to-end summary snapshots (parity/quality/final means) for the two external repos in this directory, with pinned commits and a short reproduce command.
