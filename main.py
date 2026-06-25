#!/usr/bin/env python3
"""CLI entry point for AI-text detection research project."""

from __future__ import annotations

import argparse
import sys

from heuristics import format_report, quick_check
from models import ModelPair
from scoring import binoculars_score, log_perplexity


DEFAULT_THRESHOLD_BINOCULARS = 1.0
DEFAULT_THRESHOLD_PERPLEXITY = 4.0


def classify_score(score: float, threshold: float) -> str:
    """Map score to human/AI label (higher score => human)."""
    if score >= threshold:
        return "human"
    return "ai"


def cmd_quick_check(args: argparse.Namespace) -> int:
    result = quick_check(args.text)
    print(format_report(result))
    return 0


def cmd_score_text(args: argparse.Namespace) -> int:
    pair = ModelPair(
        observer_name=args.observer,
        performer_name=args.performer,
        max_length=args.max_length,
    )

    method = args.method
    if method == "auto":
        method = "binoculars"

    if method == "binoculars":
        score = binoculars_score(args.text, pair.observer, pair.performer)
        threshold = args.threshold if args.threshold is not None else DEFAULT_THRESHOLD_BINOCULARS
        score_name = "binoculars"
    else:
        score = log_perplexity(args.text, pair.observer)
        threshold = args.threshold if args.threshold is not None else DEFAULT_THRESHOLD_PERPLEXITY
        score_name = "log_perplexity"

    label = classify_score(score, threshold)
    print(f"method:       {score_name}")
    print(f"score:        {score:.4f}")
    print(f"threshold:    {threshold:.4f}")
    print(f"classification: {label}")
    print(f"observer:     {args.observer}")
    print(f"performer:    {args.performer}")
    print("\nNote: Scores are probabilistic signals, not proof. Short or non-native text may misclassify.")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    from evaluate import run_evaluation

    run_evaluation(
        max_per_class=args.max_per_class,
        output_path=args.output,
        observer=args.observer,
        performer=args.performer,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Training-free AI text detector (Binoculars-style cross-perplexity)."
    )
    parser.add_argument(
        "--observer",
        default="gpt2",
        help="Smaller observer model (default: gpt2)",
    )
    parser.add_argument(
        "--performer",
        default="gpt2-medium",
        help="Larger performer model (default: gpt2-medium)",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=512,
        help="Max token length for scoring",
    )

    sub = parser.add_subparsers(dest="command")

    score_p = sub.add_parser("score", help="Score a single text (default mode)")
    score_p.add_argument("--text", required=True, help="Text to classify")
    score_p.add_argument(
        "--method",
        choices=("binoculars", "perplexity", "auto"),
        default="auto",
        help="Scoring method (auto uses binoculars)",
    )
    score_p.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Classification threshold (higher => human)",
    )

    # Legacy: `python main.py --text "..."` without subcommand
    parser.add_argument("--text", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--quick", action="store_true", help="Instant heuristic scan (no models)")
    parser.add_argument("--evaluate", action="store_true", help="Run full benchmark")
    parser.add_argument(
        "--max-per-class",
        type=int,
        default=40,
        help="Max human/AI samples per class for evaluation",
    )
    parser.add_argument(
        "--output",
        default="results.csv",
        help="CSV path for evaluation summary",
    )
    parser.add_argument("--method", default="auto", choices=("binoculars", "perplexity", "auto"), help=argparse.SUPPRESS)
    parser.add_argument("--threshold", type=float, default=None, help=argparse.SUPPRESS)

    quick_p = sub.add_parser("quick", help="Instant heuristic scan (no models)")
    quick_p.add_argument("--text", required=True, help="Text to scan")

    eval_p = sub.add_parser("evaluate", help="Run benchmark evaluation")
    eval_p.add_argument("--max-per-class", type=int, default=40)
    eval_p.add_argument("--output", default="results.csv")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.evaluate or args.command == "evaluate":
        return cmd_evaluate(args)

    if args.quick or args.command == "quick":
        if not args.text:
            parser.error("--text is required for quick check")
        return cmd_quick_check(args)

    text = args.text
    if text or args.command == "score":
        if not text:
            parser.error("--text is required for scoring")
        return cmd_score_text(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
