> Note (2026-03-17): This is one of two parallel writeups. See `docs/scoring_quality_eval/consolidated.md` for the cross-validated analysis, updated numbers, and consolidated improvement plan.

## Projects

- `project 1`: `~/workspace/vlm-ocr/GLM-OCR-Swift/examples`
- `project 2`: `~/workspace/vlm-ocr/glm-ocr.swift/examples`

## Ground-truth comparison (against `golden_result` / `reference_result`)

### What I used as “quality” (OCR-first)

For each example:

* If a **golden** markdown exists: **quality = `result_to_golden.overall`** (absolute OCR quality vs human-adjudicated target).
* If **golden is missing** (only `GLM-4.5V_Page_1` here): **quality = `parity.overall`** (best available proxy is upstream reference).

This avoids being “blinded” by `final_overall`, which is parity-first by design.

### Quality scores (0–100)

| Example                         | Project 1 | Project 2 | Winner             | What actually mattered in the outputs                                                                                                                                  |
| ------------------------------- | --------: | --------: | ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `table`                         |     100.0 |     100.0 | tie                | Table content and structure match golden exactly (HTML vs Markdown is normalized by the evaluator’s table IR).                                                         |
| `seal`                          |      98.1 |      98.1 | tie                | Only styling differences (e.g., bold); text content is correct.                                                                                                        |
| `handwritten`                   |      96.0 |      97.1 | Project 2          | Both correct the upstream error; minor formatting differences only.                                                                                                    |
| `code`                          |      71.9 |      72.4 | Project 2          | Both contain real OCR faults (missing title line; malformed XML segments), but Project 2 is marginally closer to golden overall.                                       |
| `page`                          |      52.8 |      56.4 | Project 2          | Both regress meaningfully vs golden/reference on critical numeric/unit content; Project 2 is less-bad.                                                                 |
| `paper`                         |      70.6 |      70.6 | tie (but see note) | Both are far from golden on math fidelity/formatting. Project 2 fixes some specific math misreads (e.g., subscripts / “Q vs O”), but not enough to move the aggregate. |
| `GLM-4.5V_Pages_1_2_3`          |      88.9 |      87.9 | Project 1          | Both high-quality; Project 1 is slightly closer to golden on this long multi-page PDF.                                                                                 |
| `GLM-4.5V_Page_1` *(no golden)* |      87.2 |      85.7 | Project 1          | Parity proxy only; Project 1 tracks the upstream reference more closely.                                                                                               |

**Overall quality (simple mean over 8):**

* **Project 1:** **83.19 / 100**
* **Project 2:** **83.51 / 100**

**Bottom line:** **Project 2 is slightly better overall on OCR quality**, primarily because it performs better on the most error-prone items (`page`, `code`, `handwritten`). **Project 1 is slightly better on the long multi-page GLM PDF outputs**.

---

## “Ground fact” qualitative deltas (high-signal examples)

### `page` (Chinese technical standard w/ units + formulas) — both weak; Project 2 better

* **Reference** contains the key constant and unit: *“0.2 N/mm²”* (and generally cleaner text).
* **Project 1**: drops the decimal constant entirely in the visible markdown (no `0.x` present) and introduces multiple semantic substitutions.
* **Project 2**: includes a decimal but **wrong** (*`0.5 MPa`*), and has multiple unit/term corruptions.
  Net: **both are materially below reference/golden**; **Project 2 is closer but still not acceptable if numeric fidelity is required**.

### `paper` (math-heavy English) — both far from golden; Project 2 fixes some “hard” math errors

Concrete issues observed:

* Project 1 includes **“not divisible by O”** where golden has **Q**, and defines the Laplacian shorthand with **missing subscripts** (`∂²/∂x²` instead of `∂²/∂x_i²`).
* Project 2 corrects those specific misreads, but **both** still lose/warp a large amount of inline math formatting relative to golden.

### `code` (XML + prose) — both flawed; Project 2 marginally better on golden alignment

Both miss the leading title (“WebLogic Workbook…”) and both contain **malformed XML** in the fenced block(s):

* Project 1: malformed tag around the data-source line (e.g., `<data-source>name>...`).
* Project 2: malformed key-cache-size line and closing tag mismatch (e.g., `</weblogic-rdms-bean>` typo + broken `</key-cache-size>`).

---

## Does `glm-ocr-example-eval` “fairly reflect” quality?

### It is **fair** for its stated goal (parity-first), but **misleading** if you read `final_overall` as OCR quality.

Key observation from your two runs:

* For **`paper`**, both projects have **~0.706 “Result→Golden”**, but `final_overall` is **~0.965–0.985**.
* Same pattern for **`code`** and **`page`**: `Result→Golden` is **~0.72 / ~0.53–0.56**, yet `final_overall` is **~0.90–0.95 / ~0.74–0.84**.

This is not a bug so much as a *design choice*:

* In `evaluator.py`, `_finalize_dimensions()` starts from **parity** and only adds a **small correction** `strength * (result_to_golden - reference_to_golden)` with default `strength=0.25` and a deadband.
* Therefore, if **reference is also far from golden**, the delta is small and **`final_overall` stays high** even when absolute OCR quality is mediocre.

**Conclusion:**

* If your question is “which repo is closer to upstream reference?”, `final_overall` is appropriate.
* If your question is “which repo has better OCR vs golden?”, you should prioritize **`result_to_golden.overall`** (or a derived score that is golden-forward).

---

## Improvement plan for `glm-ocr-example-eval` (correction + calibration)

### 1) Reporting: make “quality vs golden” a first-class headline score

Today the data is already present (`result_to_golden` is written in `report.py`), but the workflow tends to over-focus on `final_overall`.

**Plan**

* Add an explicit **`quality_overall`** field in `summary.json` / `summary.md`:

  * `quality_overall = result_to_golden.overall if available else parity.overall`
* In `summary.md`, add a column and sort option (or secondary sort) by `quality_overall`.

**Where**

* `src/example_eval/report.py`: `_write_summary_json`, `_write_summary_md`, `_write_example_reports`.

### 2) Add rule coverage for examples where small semantic errors matter (page/paper/code)

Rules currently exist only for:

* `handwritten.yaml`
* `GLM-4.5V_Pages_1_2_3.yaml`

That leaves the most fragile OCR classes **unprotected**.

**Plan (no new rule types required initially)**
Add YAMLs using existing `contains`, `page_start`, `page_end`, `continuation`:

* `config/rules/page.yaml`: require presence of the critical constant and unit variants (with alternatives).
* `config/rules/paper.yaml`: require “not divisible by Q” and a few anchor LaTeX substrings that should not drift.
* `config/rules/code.yaml`: require presence of “WebLogic Workbook”, `<weblogic-rdbms-bean>`, and `</key-cache-size>`.

This immediately makes regressions “visible” and rewards real fixes, similar to how `handwritten.yaml` rewards correcting “人间的饭”.

### 3) Calibration: introduce an OCR-quality mode (optional but recommended)

If you want the tool to directly reflect OCR quality, the smallest conceptual change is:

* Add a CLI/policy switch:

  * **parity mode** (current): `final_overall ≈ parity + small golden delta`
  * **quality mode**: `overall = result_to_golden.overall` when golden exists, else parity

**Where**

* `src/example_eval/evaluator.py`: add a mode flag and compute an alternate aggregate.
* `src/example_eval/policy.py`: allow policy to select mode.

### 4) Metric sensitivity upgrades (targeted)

The current `char_ngram_fscore` is intentionally lightweight, but it is **not very punitive** for:

* numeric/unit substitutions
* LaTeX structure drift
* code well-formedness when fences are missing or malformed

**Plan**

* Add an additional “numeric fidelity” sub-metric to `text_metrics.py` for blocks containing many digits:

  * extract numeric tokens and unit-like tokens; compute token-F1; blend into text_fidelity.
* Add a “math token fidelity” metric for `$...$` / `$$...$$` segments:

  * tokenize LaTeX-ish strings (`\commands`, subscripts, superscripts, digits, braces); score token overlap.
* Add code well-formedness checks via rules (fastest), and optionally a metric for fenced XML/HTML parseability.

---

## My decision recommendation

* If you want the **best overall OCR deliverable quality today**, pick **Project 2** (small but consistent edge on the fragile examples).
* If your priority is **long multi-page PDF extraction fidelity** (GLM paper examples), **Project 1** has a slight advantage.

Either way, the real work items are the same: **raise absolute quality on `page`, `paper`, and `code`** and adjust the evaluator workflow to foreground **`result_to_golden`** (or an explicit `quality_overall`) when you care about OCR quality rather than parity.
