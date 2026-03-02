from pathlib import Path

import pytest

from example_eval import ExampleEvalError
from example_eval.evaluator import evaluate_repo
from example_eval.json_metrics import score_json_structure


def test_score_json_structure_invalid_json_is_unavailable(tmp_path: Path) -> None:
    actual = tmp_path / "actual.json"
    expected = tmp_path / "expected.json"
    actual.write_text("{", encoding="utf-8")
    expected.write_text("[]", encoding="utf-8")

    score, details = score_json_structure(actual, expected, policy={})
    assert score is None
    assert details["available"] is False
    assert "failed to parse json" in str(details["reason"])
    assert details["path"] == str(actual)


def test_evaluate_repo_unknown_example_raises(tmp_path: Path) -> None:
    (tmp_path / "examples" / "source").mkdir(parents=True)
    (tmp_path / "examples" / "source" / "known.png").write_text("placeholder", encoding="utf-8")

    with pytest.raises(ExampleEvalError, match="Unknown example"):
        evaluate_repo(tmp_path, out_dir=tmp_path / "out", examples=["missing"])


def test_evaluate_repo_rejects_invalid_fail_under(tmp_path: Path) -> None:
    (tmp_path / "examples" / "source").mkdir(parents=True)
    (tmp_path / "examples" / "source" / "known.png").write_text("placeholder", encoding="utf-8")

    with pytest.raises(ExampleEvalError, match="fail-under"):
        evaluate_repo(tmp_path, out_dir=tmp_path / "out", fail_under=1.5)
