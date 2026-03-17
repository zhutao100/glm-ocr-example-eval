from example_eval.policy import load_policy
from example_eval.rules import evaluate_rules
from example_eval.text_metrics import score_block_text
from example_eval.types import Block


def _block(kind: str, text: str) -> Block:
    return Block(kind=kind, raw_text=text, canonical_text=text)


def test_code_block_penalizes_tag_corruption() -> None:
    policy = load_policy(None)
    expected = "<key-cache-size>10</key-cache-size>\n</weblogic-rdbms-bean>"
    missing_slash = "<key-cache-size>10<key-cache-size>\n</weblogic-rdbms-bean>"
    tag_name_corrupt = "<key-cache-size>10</key-cache-size>\n</weblogic-rdbms-beam>"

    exact = score_block_text(_block("code", expected), _block("code", expected), policy)
    assert exact > 0.95

    score_missing_slash = score_block_text(_block("code", missing_slash), _block("code", expected), policy)
    score_tag_corrupt = score_block_text(_block("code", tag_name_corrupt), _block("code", expected), policy)
    assert score_missing_slash < 0.70
    assert score_tag_corrupt < 0.70


def test_page_constant_unit_corruption_is_penalized() -> None:
    policy = load_policy(None)
    expected = "f1 value 0.2\\mathrm{N} / \\mathrm{mm}^{2}"
    wrong_value_unit = "f1 value 0.5\\mathrm{MPa}"

    exact = score_block_text(_block("paragraph", expected), _block("paragraph", expected), policy)
    assert exact > 0.95

    corrupted = score_block_text(_block("paragraph", wrong_value_unit), _block("paragraph", expected), policy)
    assert corrupted < 0.70


def test_paper_rules_catch_Q_vs_O() -> None:
    checks = [
        {
            "id": "not_divisible_by_Q",
            "type": "contains",
            "must_contain": "not divisible by Q",
            "severity": "critical",
        }
    ]
    ok = "Suppose R is not divisible by Q; note that the homogeneity implies that ..."
    bad = "Suppose R is not divisible by O; note that the homogeneity implies that ..."

    ok_result = evaluate_rules(ok, checks)[0]
    assert ok_result.status == "pass"
    assert ok_result.severity == "critical"

    bad_result = evaluate_rules(bad, checks)[0]
    assert bad_result.status == "fail"
    assert bad_result.severity == "critical"


def test_formula_token_fidelity_penalizes_structure_changes() -> None:
    policy = load_policy(None)
    expected = r"\\theta = \\frac{w_k b^4}{E t^4}"
    corrupted = r"\\theta = w_k b^4 / (E t^4)"

    exact = score_block_text(_block("formula", expected), _block("formula", expected), policy)
    assert exact > 0.95

    score_corrupted = score_block_text(_block("formula", corrupted), _block("formula", expected), policy)
    assert score_corrupted < 0.85
