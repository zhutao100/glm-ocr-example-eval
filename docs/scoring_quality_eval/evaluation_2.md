> Note (2026-03-17): This is one of two parallel writeups. See `docs/scoring_quality_eval/consolidated.md` for the cross-validated analysis, updated numbers, and consolidated improvement plan.

## Projects

- `project 1`: `~/workspace/vlm-ocr/GLM-OCR-Swift/examples`
- `project 2`: `~/workspace/vlm-ocr/glm-ocr.swift/examples`

## Verdict

**Project 2 is slightly better overall on actual OCR quality**, but the margin is small.

My grounded ranking, after inspecting the source images/PDF-derived outputs, the `result/`, `reference_result/`, `golden_result/`, and the scorer implementation, is:

* **Project 2:** **85.8 / 100**
* **Project 1:** **84.6 / 100**

That said, the aggregate hides an important split:

* **Project 2** is better for **general prose/document OCR**.
* **Project 1** is better for the **code/XML example** and slightly better on the **GLM PDF page exports**.

So the practical recommendation is:

* If you care more about **document OCR quality in general**, pick **Project 2**.
* If you care more about **copy-pastable code/config OCR fidelity**, **Project 1** is safer on the current corpus.

---

## My scoring by example

Scoring standard: **actual usefulness and faithfulness as OCR deliverables**, not parity to upstream, and not markdown cosmetics unless they materially affect usability.

| Example                | Project 1 | Project 2 | Grounded judgment                                                                                                                                |
| ---------------------- | --------: | --------: | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GLM-4.5V_Page_1`      |        92 |        88 | Both are strong. Project 1 is slightly cleaner in text and URL rendering; Project 2 has rougher placeholder handling.                            |
| `GLM-4.5V_Pages_1_2_3` |        90 |        87 | Both are strong. Project 1 is slightly cleaner in presentation and text continuity.                                                              |
| `code`                 |        72 |        65 | **Project 1 is better.** Project 2 has cleaner surrounding prose, but the embedded XML is more badly corrupted in semantically important places. |
| `handwritten`          |        96 |        98 | Both are excellent; Project 2 is slightly better. Both improve over the reference on key handwritten recognition.                                |
| `page`                 |        58 |        73 | **Project 2 is materially better.** Project 1 has many semantic substitutions/garbles.                                                           |
| `paper`                |        70 |        76 | Both are readable, but both miss visible page furniture that the golden output preserves. Project 2’s body text is slightly cleaner.             |
| `seal`                 |        99 |        99 | Essentially tied; both are effectively exact.                                                                                                    |
| `table`                |       100 |       100 | Tied; both are effectively exact.                                                                                                                |

### Net result

* **Project 2 wins overall**, mainly because it is much better on `page`, a bit better on `paper`, and slightly better on `handwritten`.
* **Project 1 wins `code` decisively enough that the current evaluator’s ranking on that example is misleading.**

---

## Where the current evaluator is fair vs unfair

## Fair / directionally useful

The current evaluator is directionally reasonable on:

* `handwritten`
* `page`
* `seal`
* `table`

It correctly recognizes that:

* Project 2 is better on handwritten text.
* Project 2 is much better on the Chinese document page.
* Both are essentially tied on seal/table.

## Unfair or materially misleading

### 1. The headline `final_overall` is mostly a **parity score**, not a **quality score**

From `config/policy.yaml` and `src/example_eval/evaluator.py`, the current logic is:

* compute **parity** against `reference_result`
* compute result-to-golden and reference-to-golden
* then set final as:

`parity + 0.25 * (result_to_golden - reference_to_golden)`, per dimension, with a deadband

That means the golden signal is only a **small adjustment** to parity.

So if the reference output is mediocre, and your output is similarly mediocre, you can still get an excellent final score.

That is exactly what happens on several examples.

### 2. `paper` is badly inflated

The evaluator gives:

* Project 1: about **0.965**
* Project 2: about **0.985**

But visually, both outputs miss page furniture that is clearly present in the source and preserved in the golden output, especially the visible top title treatment and bottom footer/page artifacts. In other words, these are **good parity scores**, not **near-perfect OCR quality scores**.

### 3. `code` is ranked the wrong way for real OCR usefulness

The evaluator prefers Project 2 strongly:

* Project 1 final: about **0.902**
* Project 2 final: about **0.946**

But for actual code/config OCR, Project 2 is worse in the most important area: the XML payload.

Examples of more severe Project 2 corruption include things like:

* wrong bean/tag spellings
* wrong identifier names
* broken closing tag text
* more dangerous code-token corruption inside the fenced block

Project 1 has some prose and tag issues too, but the core XML block is closer to something a human could repair and use. For this example, the current scorer is over-rewarding parity/style/structure signals and under-weighting **exact code token fidelity**.

### 4. `GLM-4.5V_Page_1` has a scoring hole

For the single-page PDF example, golden adjudication is effectively absent because the expected golden markdown file is missing for that exact example path, so the score falls back to parity only.

That is a real blind spot. The single-page example is clearly related to page 1 of `GLM-4.5V_Pages_1_2_3`, but the current evaluator does not bridge that gap.

### 5. Golden structural quality is often not being scored at all

For several examples, `result_to_golden.critical_structure` is `None`, because there is no golden JSON structural baseline for that example. So the “golden” correction often only touches text/style, not structure.

That weakens the very mechanism that is supposed to correct parity bias.

---

## Bottom-line assessment of the current evaluator

## Does it fairly reflect implementation quality?

**Not as a headline quality score.**

It is useful as a:

* **parity/regression detector**
* **upstream-compatibility checker**
* **stable CI guardrail**

It is **not** reliable as a top-line measure of real OCR quality.

## Is it still useful?

Yes, but only if interpreted correctly:

* `parity_overall` tells you how close you are to the upstream checked-in reference.
* `final_overall` currently tells you “parity with a light golden nudge.”
* It does **not** tell you “how good the OCR actually is” in a strong sense.

So the answer is:

* **Useful for regression control:** yes
* **Fair as an actual OCR-quality score:** no

---

## What should be corrected

## Immediate scoring interpretation change

The project should stop treating `final_overall` as the headline “quality” score.

Instead, report two separate top-line numbers:

* **Parity score**: similarity to upstream reference
* **Quality score**: similarity to golden / adjudicated correctness

Then optionally derive a third label like:

* **Contract score** or **port score**: whether the implementation preserves upstream behavior

That separation would remove most of the current confusion.

---

## Code-level improvement plan

## Phase 1 — fix the scoring model architecture

### 1. `src/example_eval/evaluator.py`

Change the current finalization model.

### Current problem

`final_overall` is parity-centered, with only a weak golden correction.

### Plan

Emit **separate scores**:

* `parity_overall`
* `golden_quality_overall`
* `contract_overall` or `port_overall`

Do **not** compress them into one scalar by default.

If a single scalar must exist, make it **golden-first**, for example:

* with golden available: `0.75 * golden_quality + 0.20 * parity + 0.05 * rules`
* without golden: fall back to parity, but mark it clearly as fallback

Also add an explicit flag in reports such as:

* `quality_signal_strength`
* `golden_available`
* `golden_structure_available`

That will make score confidence visible.

### 2. `config/policy.yaml`

Add separate weights for:

* `headline_quality_weights`
* `parity_weights`
* `contract_weights`

Also increase the role of golden when golden exists. The current `golden_adjudication.strength: 0.25` is too weak if the goal is actual quality measurement.

---

## Phase 2 — fix the biggest blind spots in metric behavior

### 3. `src/example_eval/text_metrics.py`

Improve block and content scoring.

#### Problems

* Block alignment is mostly positional (`zip_longest`), which is brittle.
* Global char n-gram similarity is too forgiving for semantically important token corruption.
* Code blocks are under-modeled.

#### Plan

Replace simple positional pairing with **sequence alignment over blocks**.

Use a cost model that considers:

* block kind
* normalized text similarity
* insertion/deletion penalties
* stronger penalties for missing headings, code blocks, or equations

For code blocks, add a dedicated metric:

* line-exact match
* token exactness for identifiers/tags
* delimiter correctness
* tag-pair balance
* closing-tag validity
* numeric literal exactness

For code/config OCR, exact token corruption should hurt much more than prose punctuation drift.

### 4. `src/example_eval/markdown_ir.py`

Improve canonicalization.

#### Problems

* Some formatting differences that should be low-impact still affect style scoring.
* Some semantically important wrappers/captions/page boundaries are not modeled robustly enough.

#### Plan

Canonicalize more aggressively for:

* trivial punctuation spacing
* equivalent image placeholder forms
* equivalent table HTML variants

But preserve explicit semantic signals for:

* page breaks
* centered captions
* footers/page numbers when present
* fenced code language and block boundaries

---

## Phase 3 — strengthen golden adjudication coverage

### 5. `src/example_eval/evaluator.py`

Add **golden alias / page-slice support**.

#### Problem

`GLM-4.5V_Page_1` lacks a direct golden file and therefore escapes golden adjudication.

#### Plan

Support a mapping such as:

* `GLM-4.5V_Page_1 -> golden slice of GLM-4.5V_Pages_1_2_3 page 1`

This could live in config, for example:

* `config/golden_aliases.yaml`

Then the evaluator can synthesize expected golden text for single-page variants from multi-page golden data.

### 6. `src/example_eval/json_metrics.py`

Add structure fallback when golden JSON is missing.

#### Problem

Many golden comparisons have `critical_structure = None`.

#### Plan

When golden JSON is absent, derive structure from golden markdown IR:

* heading count/order
* table count/shape
* image placeholder count/order
* formula block count/order
* page break count

This is weaker than full golden JSON, but much better than `None`.

---

## Phase 4 — add example-specific quality checks where generic similarity is insufficient

### 7. `config/rules/*.yaml`

Add rules for examples where domain semantics matter.

#### `code`

Add checks for exact presence of critical substrings such as:

* `local-jndi-name`
* `AddressEJB`
* `titan-dataSource`
* `ADDRESS_SEQUENCE`
* valid `</key-cache-size>`

This will catch the exact kind of failure the current scorer under-penalizes.

#### `page`

Add checks for:

* section identifiers `7.4.1`, `7.4.2`, `8.1.1`, etc.
* critical formula tags `(7.4.2-1)`, `(8.1.5-4)`
* critical values like `0.2N/mm^2`, `6mm`, `8mm`, `10mm`

#### `paper`

Add checks for:

* page header/title presence
* footer presence if intended to be captured
* page number
* major section headings

### 8. Add rule severity tiers

In `rules.py`, support stronger weighting for:

* `critical`
* `major`
* `minor`

Not every failure should perturb the score equally.

---

## Phase 5 — improve reports so humans can trust them

### 9. `src/example_eval/report.py`

Report inflation and disagreement explicitly.

Add sections like:

* **Parity vs Golden disagreement**
* **Examples where final score is likely inflated**
* **Top semantic mismatches**
* **Missing-golden / missing-structure warnings**

A report should be able to say, in plain text:

> This example scores high on parity but remains meaningfully below golden quality.

That would have exposed `paper` immediately.

---

## Phase 6 — lock in calibration with tests

### 10. `tests/`

Add calibration tests for the exact failure modes observed here.

Suggested tests:

* `test_code_quality_prefers_token_correctness_over_wrapper_style`
* `test_single_page_pdf_can_use_multi_page_golden_alias`
* `test_missing_golden_json_falls_back_to_markdown_structure`
* `test_paper_missing_header_footer_cannot_score_near_perfect_quality`
* `test_rule_severity_affects_quality_score`

These should be based on the checked-in corpus so future scoring changes remain explainable.

---

## Recommended project-level scoring model after recalibration

Use this mental model:

### Score families

* **Parity score**: “How close are we to upstream?”
* **Quality score**: “How good is the OCR against adjudicated truth?”
* **Regression status**: “Did we materially worsen the checked-in contract?”

### Headline rule

* In docs and CI dashboards, **headline the quality score**, not the parity score.
* Keep parity visible, but secondary.

That matches what you actually asked for: **actual deliverable OCR quality**.

---

## Final recommendation

**Project 2 is the better implementation overall on this corpus, but only slightly.**
**Project 1 is the better implementation for the code/config OCR case.**

The current `glm-ocr-example-eval` is **useful but misnamed in practice**: it behaves more like an **upstream parity evaluator with light golden calibration** than a true OCR-quality scorer.

If you want, I can turn this into a concrete patch plan with file-by-file change lists and proposed formulas.
