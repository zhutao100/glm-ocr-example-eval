from __future__ import annotations

import argparse
from pathlib import Path

from .evaluator import default_policy_path, evaluate_repo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate GLM-OCR-Swift examples/result outputs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate = subparsers.add_parser("evaluate", help="Run the scorer over the example corpus.")
    evaluate.add_argument("--repo-root", type=Path, default=Path("."), help="Parent GLM-OCR-Swift repository root.")
    evaluate.add_argument(
        "--policy",
        type=Path,
        default=default_policy_path(),
        help="Path to the scoring policy YAML.",
    )
    evaluate.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Default: <repo-root>/.build/example_eval",
    )
    evaluate.add_argument(
        "--example",
        action="append",
        default=[],
        help="Evaluate only the named example. Repeatable.",
    )
    evaluate.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Exit non-zero if any example final score falls below this threshold.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "evaluate":
        result = evaluate_repo(
            args.repo_root,
            policy_path=args.policy,
            out_dir=args.out_dir,
            examples=args.example,
            fail_under=args.fail_under,
        )
        print(f"Wrote reports to: {result['out_dir']}")
        examples = result["examples"]
        for evaluation in examples:
            print(
                f"- {evaluation.name}: parity={evaluation.parity.overall!s} final={evaluation.final_overall!s} rules={len(evaluation.rule_results)}"
            )
        return 1 if result["should_fail"] else 0

    parser.error(f"Unknown command: {args.command}")
    return 2
