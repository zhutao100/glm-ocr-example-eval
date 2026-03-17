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

### 2) Golden structural signal is limited (golden JSON is still missing), but no longer absent

In both external repos’ `examples/golden_result/*/`, golden baselines are markdown-only (no `*.json`), so the scorer still cannot compute golden `json_structure`.

However, the scorer now derives a lightweight `markdown_structure` signature from the golden markdown and includes it in `critical_structure`, so:

- `result_to_golden.dimensions.critical_structure` is now available (via `markdown_structure`, plus table IR when present).
- Golden adjudication can now nudge `critical_structure` based on markdown structure, but it remains less informative than having full golden JSON baselines.

Parity-first inflation (high `final_overall` while `quality_overall` is low) still occurs whenever the upstream reference is itself far from golden.

### 3) Example-specific rule coverage now includes the fragile examples

Rule files in this repo now include:

- `config/rules/GLM-4.5V_Pages_1_2_3.yaml`
- `config/rules/code.yaml`
- `config/rules/handwritten.yaml`
- `config/rules/page.yaml`
- `config/rules/paper.yaml`

Rule severities support `minor`/`major`/`critical` (plus legacy `warn`/`error`), and the final-score rule adjustment is severity-weighted via `config/policy.yaml:rule_adjudication`.

## External results re-run (2026-03-17)

### Inputs (paths + commits)

- Scorer repo: `~/workspace/vlm-ocr/glm-ocr-example-eval` @ `c404ee90cbd3de39b436e32ffbac031b606857b3`
- Project 1: `~/workspace/vlm-ocr/GLM-OCR-Swift_dev` @ `2375d654e2f6158a2d97367c2158e2d25b4a4cdb`
- Project 2: `~/workspace/vlm-ocr/glm-ocr.swift` @ `20c4fb0184085388e29f0bc4a680f7c0160c9b72`

### How to reproduce

From the scorer repo root:

```bash
PYENV_VERSION=venv313 pyenv exec env PYTHONPATH=src \
  python3 -c "from example_eval.cli import main; raise SystemExit(main())" \
  evaluate --repo-root ~/workspace/vlm-ocr/GLM-OCR-Swift_dev

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
| `GLM-4.5V_Page_1` | 0.9600 | 0.9115 | 0.9569 | 0.9224 | 0.8679 | 0.9067 | -0.0436 |
| `GLM-4.5V_Pages_1_2_3` | 0.9494 | 0.8454 | 0.9440 | 0.9627 | 0.8463 | 0.9557 | 0.0009 |
| `code` | 0.8985 | 0.8153 | 0.8708 | 0.9384 | 0.8382 | 0.9105 | 0.0229 |
| `handwritten` | 0.9109 | 0.7842 | 0.9609 | 0.9875 | 0.8034 | 1.0000 | 0.0192 |
| `page` | 0.7829 | 0.4486 | 0.7160 | 0.8836 | 0.4837 | 0.8254 | 0.0351 |
| `paper` | 0.9629 | 0.7316 | 0.9329 | 0.9864 | 0.7326 | 0.9864 | 0.0010 |
| `seal` | 0.9804 | 0.9875 | 0.9804 | 0.9894 | 0.9875 | 0.9894 | 0.0000 |
| `table` | 0.9944 | 1.0000 | 0.9944 | 0.9987 | 1.0000 | 0.9987 | 0.0000 |

### Headline means (simple mean over 8 examples)

| Metric | Project 1 | Project 2 |
|---|---:|---:|
| mean parity | 0.9299 | 0.9586 |
| mean quality_overall | 0.8155 | 0.8199 |
| mean final | 0.9195 | 0.9466 |

### Cross-validation note: some numbers in `evaluation_1.md` are stale

The qualitative conclusions in both writeups largely match the current situation, but the per-example numeric table in `evaluation_1.md` no longer matches the current checked-out external results and/or the current scorer behavior (see the table above for an updated run with pinned commits).

## Unified conclusions (what both writeups agree on, after validation)

### 1) `final_overall` is a good parity/regression signal, but can be a misleading “quality” headline

Current runs show large “inflation” (final − quality) on examples where upstream reference is also far from golden, e.g.:

- `paper`: quality ≈ 0.732 while final ≈ 0.933–0.986
- `page`: quality ≈ 0.449–0.484 while final ≈ 0.716–0.825
- `handwritten`: quality ≈ 0.784–0.803 while final ≈ 0.961–1.000

This is expected under the parity-first design; it is amplified when the upstream reference is also far from golden and golden structure is only partially observed (markdown-only golden baselines).

### 2) Project 2 wins on parity and slightly on golden-quality; Project 1 is slightly better on the long PDF cases

On the current corpus:

- Project 2 is substantially better on **parity** and slightly better on derived **quality** (mainly `page`, `handwritten`, and `code`).
- Project 1 is better on `GLM-4.5V_Page_1`, while `GLM-4.5V_Pages_1_2_3` is effectively tied on derived quality.

### 3) The scorer now surfaces the key semantic failure modes, but `final_overall` remains parity-first

Concrete external-output checks (current external repos):

- `page`: both projects still miss the glue-strength constant `0.2\\mathrm{N} / \\mathrm{mm}^{2}` (rule failure; low `quality_overall`).
- `paper`: Project 1 has “not divisible by O” where golden has `Q`; Project 2 fixes this (rule pass/fail is reflected in `final_overall` via rule adjudication).
- `code`: both projects exhibit different XML-tag corruption patterns; rule failures now highlight these regressions, and the token-aware code scoring keeps `text_fidelity` from being overly optimistic.

These are exactly the failure modes where lightweight char n-gram similarity benefits from deterministic rules and token-aware scoring.

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

Status / decisions (implemented in this repo):

- Added rule files:
  - `config/rules/page.yaml`
  - `config/rules/paper.yaml`
  - `config/rules/code.yaml`
- Rule severities now support: `minor`, `major`, `critical` (in addition to legacy `warn`/`error`).
- Rule adjudication is now severity-weighted (config-driven via `rule_adjudication.severity_weights` in `config/policy.yaml`).
  - CI/JUnit failure behavior remains unchanged: only `severity: error` fails the run.

### Phase 3 — metric upgrades (higher effort, but removes known mis-rankings)

Goal: reduce reliance on global char similarity where it’s known to be misleading.

- Block alignment:
  - replace `zip_longest` block pairing with sequence alignment (DP) over block kinds + text similarity
  - reduces line-wrap/paragraph-splitting artifacts and strengthens missing-block penalties
- Token-aware scoring:
  - numeric token fidelity (numbers + unit-ish tokens) for digit-heavy blocks
  - LaTeX token fidelity for `$...$` / `$$...$$`
  - stricter code-block fidelity (identifiers/tags, delimiter correctness, closing-tag balance)

Status / decisions (implemented in this repo):

- Block alignment:
  - `text_fidelity` block pairing now uses DP sequence alignment instead of `zip_longest`.
  - Alignment is driven by block-kind match bonus + coarse token Jaccard similarity (CJK chars + ASCII tokens + LaTeX commands + numerics).
  - Tunables live in `config/policy.yaml:text_alignment` (`gap_penalty`, `kind_match_bonus`, blend weights).
- Token-aware scoring (all continuous `[0, 1]`, policy-weighted):
  - Numeric/unit token fidelity for digit-heavy blocks (`numeric_block_text_weights`).
  - LaTeX token fidelity for formula blocks (`formula_block_text_weights`) and inline `$...$` segments (`inline_math_text_weights`).
  - Code blocks now include identifier and XML-tag token F-scores (`code_block_text_weights.identifier_fscore` / `tag_fscore`).

### Phase 4 — calibration tests + end-to-end score snapshots (to prevent regressions)

- Add tests in `tests/` for the observed failure modes:
  - `code` should penalize broken closing tags and tag-name corruption
  - `page` should strongly penalize key constant/unit corruption
  - `paper` should reflect Q vs O and basic LaTeX structure
- Record end-to-end summary snapshots (parity/quality/final means) for the two external repos in this directory, with pinned commits and a short reproduce command.

Status / decisions (implemented in this repo):

- Added unit tests for semantic failure modes: `tests/test_semantic_fidelity.py`.
- Recorded pinned external snapshots: `docs/scoring_quality_eval/snapshots/2026-03-17.md`.
