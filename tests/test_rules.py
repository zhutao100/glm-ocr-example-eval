from example_eval.rules import evaluate_rules


def test_page_rules_and_continuation_pass() -> None:
    text = """Page one
---
1 Introduction
performance. Therefore, we propose strategies including Reinforcement Learning with Curriculum
---
Sampling (RLCS) and dynamic sampling expansion via ratio-based Exponential Moving Average
capabilities."""
    checks = [
        {"id": "page2_start", "type": "page_start", "page": 2, "must_contain": "1 Introduction", "severity": "warn"},
        {
            "id": "continuation",
            "type": "continuation",
            "left_page": 2,
            "left_must_contain": "Reinforcement Learning with Curriculum",
            "right_page": 3,
            "right_must_contain": "Sampling (RLCS) and dynamic sampling expansion",
            "severity": "warn",
        },
    ]
    results = evaluate_rules(text, checks)
    assert [result.status for result in results] == ["pass", "pass"]
