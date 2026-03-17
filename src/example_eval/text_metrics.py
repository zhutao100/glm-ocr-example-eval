from __future__ import annotations

import re
from collections import Counter
from itertools import zip_longest
from typing import Iterable

from .markdown_ir import normalize_text, split_markdown_pages
from .types import Block, TableIR


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def weighted_mean(items: Iterable[tuple[float | None, float]]) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for value, weight in items:
        if value is None or weight <= 0:
            continue
        numerator += value * weight
        denominator += weight
    if denominator == 0:
        return None
    return numerator / denominator


def ratio_similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    import difflib

    return difflib.SequenceMatcher(a=a, b=b).ratio()


def char_ngram_fscore(a: str, b: str, *, n: int = 3) -> float:
    a = normalize_text(a)
    b = normalize_text(b)
    if a == b:
        return 1.0
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    if min(len(a), len(b)) < n:
        return ratio_similarity(a, b)

    def grams(text: str) -> Counter[str]:
        return Counter(text[index : index + n] for index in range(len(text) - n + 1))

    grams_a = grams(a)
    grams_b = grams(b)
    overlap = sum((grams_a & grams_b).values())
    total_a = sum(grams_a.values())
    total_b = sum(grams_b.values())
    if total_a == 0 or total_b == 0:
        return 0.0
    precision = overlap / total_b
    recall = overlap / total_a
    if precision == 0 or recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def token_fscore(tokens_a: Iterable[str], tokens_b: Iterable[str]) -> float:
    counts_a = Counter(tokens_a)
    counts_b = Counter(tokens_b)
    if not counts_a and not counts_b:
        return 1.0
    if not counts_a or not counts_b:
        return 0.0
    overlap = sum((counts_a & counts_b).values())
    total_a = sum(counts_a.values())
    total_b = sum(counts_b.values())
    if total_a == 0 or total_b == 0:
        return 0.0
    precision = overlap / total_b
    recall = overlap / total_a
    if precision == 0 or recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


_NUMERIC_DOT_RE = re.compile(r"(?<=\\d)\\s*\\.\\s*(?=\\d)")
_NUMERIC_RE = re.compile(r"\\d+(?:\\.\\d+)?")
_UNIT_TOKEN_RE = re.compile(r"[A-Za-z]+(?:[A-Za-z0-9/^_-]*[A-Za-z0-9])?")
_LATEX_TOKEN_RE = re.compile(r"\\\\[A-Za-z]+|\\d+(?:\\.\\d+)?|[A-Za-z]+|[^\\s]")


def _normalize_numeric_text(text: str) -> str:
    return _NUMERIC_DOT_RE.sub(".", text)


def _extract_numeric_tokens(text: str) -> list[str]:
    return _NUMERIC_RE.findall(_normalize_numeric_text(text))


def _simplify_latex(text: str) -> str:
    text = re.sub(r"\\\\(?:mathrm|text)\\{([^}]*)\\}", r"\\1", text)
    text = re.sub(r"\\^\\{([^}]*)\\}", r"^\\1", text)
    text = re.sub(r"_\\{([^}]*)\\}", r"_\\1", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\\\\[A-Za-z]+", " ", text)
    return text


def _extract_unitish_tokens(text: str) -> list[str]:
    simplified = _simplify_latex(text)
    candidates = [token.lower() for token in _UNIT_TOKEN_RE.findall(simplified)]
    keep: list[str] = []
    for token in candidates:
        if any(ch.isdigit() for ch in token) or "/" in token or "^" in token:
            keep.append(token)
            continue
        if token in {"mm", "cm", "m", "n", "pa", "kpa", "mpa", "kg"}:
            keep.append(token)
    return keep


def _numeric_unit_fscore(a: str, b: str) -> float:
    tokens_a = _extract_numeric_tokens(a) + _extract_unitish_tokens(a)
    tokens_b = _extract_numeric_tokens(b) + _extract_unitish_tokens(b)
    return token_fscore(tokens_a, tokens_b)


def _latex_token_fscore(a: str, b: str) -> float:
    a_compact = re.sub(r"\\s+", "", a)
    b_compact = re.sub(r"\\s+", "", b)
    return token_fscore(_LATEX_TOKEN_RE.findall(a_compact), _LATEX_TOKEN_RE.findall(b_compact))


def _extract_inline_math(text: str) -> str:
    parts: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != "$":
            index += 1
            continue
        if index + 1 < len(text) and text[index + 1] == "$":
            index += 2
            continue
        end = text.find("$", index + 1)
        if end == -1:
            break
        parts.append(text[index + 1 : end])
        index = end + 1
    return "\n".join(parts)


def _is_digit_heavy(text: str) -> bool:
    fixed = _normalize_numeric_text(text)
    if not _NUMERIC_RE.search(fixed):
        return False
    digit_ratio = sum(ch.isdigit() for ch in fixed) / max(len(fixed), 1)
    return digit_ratio >= 0.06 or len(_extract_numeric_tokens(fixed)) >= 2


def score_code_block_text(a: Block, b: Block, policy: dict[str, object]) -> float:
    weights = policy.get("code_block_text_weights", {})
    exact_weight = float(weights.get("exact_line_match", 0.70))
    char_weight = float(weights.get("char_fscore", 0.30))
    identifier_weight = float(weights.get("identifier_fscore", 0.0))
    tag_weight = float(weights.get("tag_fscore", 0.0))

    a_text = normalize_text(a.canonical_text, collapse_whitespace=False)
    b_text = normalize_text(b.canonical_text, collapse_whitespace=False)
    exact = 1.0 if a_text == b_text else 0.0
    char_score = char_ngram_fscore(a_text, b_text)

    identifier_score = token_fscore(
        re.findall(r"[A-Za-z_][A-Za-z0-9_:-]*", a_text),
        re.findall(r"[A-Za-z_][A-Za-z0-9_:-]*", b_text),
    )

    open_tags_a = re.findall(r"<\\s*([A-Za-z][A-Za-z0-9:_-]*)\\b", a_text)
    open_tags_b = re.findall(r"<\\s*([A-Za-z][A-Za-z0-9:_-]*)\\b", b_text)
    close_tags_a = re.findall(r"<\\s*/\\s*([A-Za-z][A-Za-z0-9:_-]*)\\b", a_text)
    close_tags_b = re.findall(r"<\\s*/\\s*([A-Za-z][A-Za-z0-9:_-]*)\\b", b_text)
    tag_score = 0.5 * (token_fscore(open_tags_a, open_tags_b) + token_fscore(close_tags_a, close_tags_b))

    numerator = (
        exact * exact_weight + char_score * char_weight + identifier_score * identifier_weight + tag_score * tag_weight
    )
    denominator = exact_weight + char_weight + identifier_weight + tag_weight
    return clamp01(numerator / max(denominator, 1e-9))


def score_block_text(a: Block, b: Block, policy: dict[str, object]) -> float:
    if a.kind == "table" or b.kind == "table":
        raise ValueError("Table blocks must be scored with score_table_pair")
    if a.kind == "code" or b.kind == "code":
        return score_code_block_text(a, b, policy)
    char_score = char_ngram_fscore(a.canonical_text, b.canonical_text)

    if a.kind == "formula" or b.kind == "formula":
        weights = policy.get("formula_block_text_weights", {})
        char_weight = float(weights.get("char_fscore", 0.40))
        latex_weight = float(weights.get("latex_token_fscore", 0.60))
        latex_score = _latex_token_fscore(a.canonical_text, b.canonical_text)
        numerator = char_score * char_weight + latex_score * latex_weight
        denominator = char_weight + latex_weight
        return clamp01(numerator / max(denominator, 1e-9))

    score = char_score
    if _is_digit_heavy(a.canonical_text) or _is_digit_heavy(b.canonical_text):
        weights = policy.get("numeric_block_text_weights", {})
        char_weight = float(weights.get("char_fscore", 0.65))
        token_weight = float(weights.get("token_fscore", 0.35))
        numeric_score = _numeric_unit_fscore(a.canonical_text, b.canonical_text)
        numerator = score * char_weight + numeric_score * token_weight
        denominator = char_weight + token_weight
        score = clamp01(numerator / max(denominator, 1e-9))

    if "$" in a.canonical_text or "$" in b.canonical_text:
        math_a = _extract_inline_math(a.canonical_text)
        math_b = _extract_inline_math(b.canonical_text)
        if math_a or math_b:
            weights = policy.get("inline_math_text_weights", {})
            char_weight = float(weights.get("char_fscore", 0.70))
            latex_weight = float(weights.get("latex_token_fscore", 0.30))
            latex_score = _latex_token_fscore(math_a, math_b)
            numerator = score * char_weight + latex_score * latex_weight
            denominator = char_weight + latex_weight
            score = clamp01(numerator / max(denominator, 1e-9))

    return score


def score_block_text_fidelity(
    actual: list[Block], expected: list[Block], policy: dict[str, object]
) -> tuple[float | None, dict[str, object]]:
    def filter_blocks(blocks: list[Block]) -> list[Block]:
        filtered: list[Block] = []
        for block in blocks:
            if block.kind == "paragraph" and not block.canonical_text:
                continue
            filtered.append(block)
        return filtered

    actual = filter_blocks(actual)
    expected = filter_blocks(expected)

    alignment_policy = policy.get("text_alignment", {})
    if not isinstance(alignment_policy, dict):
        alignment_policy = {}
    aligned_weight = float(alignment_policy.get("aligned_weight", 0.35))
    global_weight = float(alignment_policy.get("global_weight", 0.65))
    gap_penalty = float(alignment_policy.get("gap_penalty", 0.40))
    kind_match_bonus = float(alignment_policy.get("kind_match_bonus", 0.20))

    def token_set(block: Block) -> set[str]:
        text = block.canonical_text or ""
        if len(text) > 400:
            text = text[:400]
        tokens = set(re.findall(r"[a-z0-9_]+", text.lower()))
        tokens.update(_extract_numeric_tokens(text))
        tokens.update(re.findall(r"\\\\[A-Za-z]+", text))
        tokens.update(ch for ch in text if "\u4e00" <= ch <= "\u9fff")
        return tokens

    def jaccard(a_tokens: set[str], b_tokens: set[str]) -> float:
        if not a_tokens and not b_tokens:
            return 1.0
        union = a_tokens | b_tokens
        if not union:
            return 1.0
        return len(a_tokens & b_tokens) / len(union)

    def align_blocks() -> list[tuple[int | None, int | None]]:
        n = len(actual)
        m = len(expected)
        if n == 0 and m == 0:
            return []
        max_cells = 500_000
        if n * m > max_cells:
            return [(a, b) for a, b in zip_longest(range(n), range(m))]

        a_tokens = [token_set(block) for block in actual]
        b_tokens = [token_set(block) for block in expected]

        dp = [[0.0] * (m + 1) for _ in range(n + 1)]
        back = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            dp[i][0] = dp[i - 1][0] - gap_penalty
            back[i][0] = 1
        for j in range(1, m + 1):
            dp[0][j] = dp[0][j - 1] - gap_penalty
            back[0][j] = 2

        for i in range(1, n + 1):
            a_block = actual[i - 1]
            a_kind = a_block.kind
            for j in range(1, m + 1):
                b_block = expected[j - 1]
                bonus = kind_match_bonus if a_kind == b_block.kind else 0.0
                sim = bonus + (1.0 - bonus) * jaccard(a_tokens[i - 1], b_tokens[j - 1])

                diag = dp[i - 1][j - 1] + sim
                up = dp[i - 1][j] - gap_penalty
                left = dp[i][j - 1] - gap_penalty

                if diag >= up and diag >= left:
                    dp[i][j] = diag
                    back[i][j] = 0
                elif up >= left:
                    dp[i][j] = up
                    back[i][j] = 1
                else:
                    dp[i][j] = left
                    back[i][j] = 2

        alignment: list[tuple[int | None, int | None]] = []
        i = n
        j = m
        while i > 0 or j > 0:
            direction = back[i][j]
            if direction == 0 and i > 0 and j > 0:
                alignment.append((i - 1, j - 1))
                i -= 1
                j -= 1
            elif direction == 1 and i > 0:
                alignment.append((i - 1, None))
                i -= 1
            else:
                alignment.append((None, j - 1))
                j -= 1
        alignment.reverse()
        return alignment

    kind_weights = policy.get("text_block_kind_weights", {})
    block_scores: list[tuple[float | None, float]] = []
    details: list[dict[str, object]] = []

    for step, (actual_index, expected_index) in enumerate(align_blocks()):
        actual_block = actual[actual_index] if actual_index is not None else None
        expected_block = expected[expected_index] if expected_index is not None else None
        if actual_block is None and expected_block is None:
            continue

        if actual_block is None or expected_block is None:
            kind = actual_block.kind if actual_block is not None else expected_block.kind
            weight = float(kind_weights.get(kind, kind_weights.get("other", 1.0)))
            block_scores.append((0.0, weight))
            details.append(
                {
                    "step": step,
                    "status": "missing_expected" if actual_block is None else "extra_actual",
                    "actual_index": actual_index,
                    "expected_index": expected_index,
                    "kind": kind,
                    "score": 0.0,
                }
            )
            continue

        kind_weight = float(kind_weights.get(expected_block.kind, kind_weights.get("other", 1.0)))
        kind_penalty = 1.0 if actual_block.kind == expected_block.kind else 0.75
        score = score_block_text(actual_block, expected_block, policy) * kind_penalty
        block_scores.append((score, kind_weight))
        details.append(
            {
                "step": step,
                "status": "paired",
                "actual_index": actual_index,
                "expected_index": expected_index,
                "actual_kind": actual_block.kind,
                "expected_kind": expected_block.kind,
                "score": round(score, 4),
            }
        )

    aligned_score = weighted_mean(block_scores)
    global_actual = "\n".join(block.canonical_text for block in actual if block.canonical_text)
    global_expected = "\n".join(block.canonical_text for block in expected if block.canonical_text)
    global_score = char_ngram_fscore(global_actual, global_expected)
    if aligned_score is None:
        final_score = global_score
    else:
        numerator = aligned_weight * aligned_score + global_weight * global_score
        denominator = aligned_weight + global_weight
        final_score = numerator / max(denominator, 1e-9)
    return (
        final_score,
        {
            "blocks": details,
            "aligned_score": aligned_score,
            "global_score": global_score,
            "alignment": {
                "aligned_weight": aligned_weight,
                "global_weight": global_weight,
                "gap_penalty": gap_penalty,
                "kind_match_bonus": kind_match_bonus,
            },
        },
    )


def _table_shape_score(actual: TableIR, expected: TableIR) -> float:
    if not actual.rows and not expected.rows:
        return 1.0
    if not actual.rows or not expected.rows:
        return 0.0
    row_score = 1.0 - (abs(len(actual.rows) - len(expected.rows)) / max(len(actual.rows), len(expected.rows), 1))
    row_details: list[float] = []
    for row_a, row_b in zip_longest(actual.rows, expected.rows, fillvalue=[]):
        row_details.append(1.0 - (abs(len(row_a) - len(row_b)) / max(len(row_a), len(row_b), 1)))
    col_score = sum(row_details) / len(row_details) if row_details else 1.0
    return clamp01((row_score + col_score) / 2.0)


def _table_content_score(actual: TableIR, expected: TableIR) -> float:
    cell_scores: list[float] = []
    for row_a, row_b in zip_longest(actual.rows, expected.rows, fillvalue=[]):
        for cell_a, cell_b in zip_longest(row_a, row_b, fillvalue=""):
            cell_scores.append(char_ngram_fscore(cell_a, cell_b))
    if not cell_scores:
        return 1.0
    return sum(cell_scores) / len(cell_scores)


def score_table_pair(actual: TableIR | None, expected: TableIR | None) -> tuple[float | None, dict[str, float] | None]:
    if actual is None and expected is None:
        return 1.0, {"shape": 1.0, "content": 1.0}
    if actual is None or expected is None:
        return 0.0, {"shape": 0.0, "content": 0.0}
    shape = _table_shape_score(actual, expected)
    content = _table_content_score(actual, expected)
    overall = 0.60 * shape + 0.40 * content
    return overall, {"shape": shape, "content": content}


def score_table_blocks(actual: list[Block], expected: list[Block]) -> tuple[float | None, dict[str, object]]:
    parts: list[tuple[float | None, float]] = []
    details: list[dict[str, object]] = []
    for index, (actual_block, expected_block) in enumerate(zip_longest(actual, expected)):
        score, sub = score_table_pair(
            actual_block.table if actual_block is not None else None,
            expected_block.table if expected_block is not None else None,
        )
        parts.append((score, 1.0))
        details.append({"index": index, "score": score, "subscores": sub})
    return weighted_mean(parts), {"tables": details}


def score_block_shape(actual: list[Block], expected: list[Block]) -> float:
    actual_kinds = [block.kind for block in actual]
    expected_kinds = [block.kind for block in expected]
    if not actual_kinds and not expected_kinds:
        return 1.0
    pair_scores: list[float] = []
    for actual_kind, expected_kind in zip_longest(actual_kinds, expected_kinds, fillvalue="<missing>"):
        pair_scores.append(1.0 if actual_kind == expected_kind else 0.0)
    return sum(pair_scores) / len(pair_scores)


_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*]\([^)]+\)")


def _is_page_break_marker(line: str) -> bool:
    stripped = line.strip()
    return bool(re.fullmatch(r"(?:-{3,}|\*{3,}|_{3,})", stripped))


def _is_image_only_line(line: str) -> bool:
    stripped = line.strip()
    return bool(re.fullmatch(r"!\[[^\]]*]\([^)]+\)", stripped))


def _count_markdown_images(text: str) -> int:
    return len(_MARKDOWN_IMAGE_RE.findall(text))


def _count_similarity(a: int, b: int) -> float:
    return clamp01(1.0 - (abs(a - b) / max(a, b, 1)))


def score_markdown_structure(
    actual_markdown: str,
    expected_markdown: str,
    actual_blocks: list[Block],
    expected_blocks: list[Block],
) -> tuple[float, dict[str, object]]:
    def kind_sequence(blocks: list[Block]) -> list[str]:
        sequence: list[str] = []
        for block in blocks:
            if block.kind == "paragraph" and not block.canonical_text:
                continue
            if block.kind == "paragraph":
                if _is_page_break_marker(block.raw_text):
                    continue
                if _is_image_only_line(block.raw_text):
                    sequence.append("image")
                    continue
            sequence.append(block.kind)
        return sequence

    kinds_a = kind_sequence(actual_blocks)
    kinds_b = kind_sequence(expected_blocks)
    headings_a = [int(block.meta.get("level", 0)) for block in actual_blocks if block.kind == "heading"]
    headings_b = [int(block.meta.get("level", 0)) for block in expected_blocks if block.kind == "heading"]

    table_shapes_a = [
        (len(block.table.rows), max((len(row) for row in block.table.rows), default=0))
        for block in actual_blocks
        if block.kind == "table" and block.table is not None
    ]
    table_shapes_b = [
        (len(block.table.rows), max((len(row) for row in block.table.rows), default=0))
        for block in expected_blocks
        if block.kind == "table" and block.table is not None
    ]

    image_count_a = _count_markdown_images(actual_markdown)
    image_count_b = _count_markdown_images(expected_markdown)
    formula_count_a = sum(1 for block in actual_blocks if block.kind == "formula")
    formula_count_b = sum(1 for block in expected_blocks if block.kind == "formula")
    page_breaks_a = max(0, len(split_markdown_pages(actual_markdown)) - 1)
    page_breaks_b = max(0, len(split_markdown_pages(expected_markdown)) - 1)

    import difflib

    kind_score = difflib.SequenceMatcher(a=kinds_a, b=kinds_b).ratio() if kinds_a or kinds_b else 1.0
    heading_score = difflib.SequenceMatcher(a=headings_a, b=headings_b).ratio() if headings_a or headings_b else 1.0
    table_shape_score = (
        difflib.SequenceMatcher(a=table_shapes_a, b=table_shapes_b).ratio() if table_shapes_a or table_shapes_b else 1.0
    )

    components = {
        "kind_sequence": kind_score,
        "heading_levels": heading_score,
        "table_shape": table_shape_score,
        "image_count": _count_similarity(image_count_a, image_count_b),
        "formula_count": _count_similarity(formula_count_a, formula_count_b),
        "page_break_count": _count_similarity(page_breaks_a, page_breaks_b),
    }
    overall = sum(components.values()) / len(components) if components else 1.0
    return overall, {
        "components": {name: round(score, 4) for name, score in components.items()},
        "actual": {
            "kind_count": len(kinds_a),
            "heading_levels": headings_a,
            "table_shapes": table_shapes_a,
            "image_count": image_count_a,
            "formula_count": formula_count_a,
            "page_break_count": page_breaks_a,
        },
        "expected": {
            "kind_count": len(kinds_b),
            "heading_levels": headings_b,
            "table_shapes": table_shapes_b,
            "image_count": image_count_b,
            "formula_count": formula_count_b,
            "page_break_count": page_breaks_b,
        },
    }


def score_decorative_style(actual: list[Block], expected: list[Block]) -> tuple[float | None, dict[str, object]]:
    if not actual and not expected:
        return 1.0, {}

    def fingerprint(blocks: list[Block]) -> dict[str, object]:
        return {
            "heading_levels": [int(block.meta.get("level", 0)) for block in blocks if block.kind == "heading"],
            "bold_markers": sum(block.raw_text.count("**") + block.raw_text.count("__") for block in blocks),
            "center_wrappers": sum(block.raw_text.lower().count('align="center"') for block in blocks),
            "code_languages": [str(block.meta.get("language", "")) for block in blocks if block.kind == "code"],
        }

    actual_fp = fingerprint(actual)
    expected_fp = fingerprint(expected)
    components = [
        ratio_similarity(str(actual_fp["heading_levels"]), str(expected_fp["heading_levels"])),
        ratio_similarity(str(actual_fp["bold_markers"]), str(expected_fp["bold_markers"])),
        ratio_similarity(str(actual_fp["center_wrappers"]), str(expected_fp["center_wrappers"])),
        ratio_similarity(str(actual_fp["code_languages"]), str(expected_fp["code_languages"])),
    ]
    score = sum(components) / len(components)
    return score, {"actual": actual_fp, "expected": expected_fp}
