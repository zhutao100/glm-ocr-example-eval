from pathlib import Path

import pytest

from example_eval.evaluator import evaluate_repo


def test_handwritten_is_rewarded_against_golden() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    if not (repo_root / "examples" / "result" / "handwritten" / "handwritten.md").is_file():
        pytest.skip("integration corpus not present; this test is meant to run after drop-in to GLM-OCR-Swift")
    result = evaluate_repo(repo_root, examples=["handwritten"])
    evaluation = result["examples"][0]
    assert evaluation.parity.overall is not None
    assert evaluation.final_overall is not None
    assert evaluation.final_overall >= evaluation.parity.overall
