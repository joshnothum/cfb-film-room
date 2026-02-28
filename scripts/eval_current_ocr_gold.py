#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.ocr_labeling import evaluate_gold_file


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate current OCR gold file against predictions by game.")
    parser.add_argument("path", help="Path to OCR gold JSONL file.")
    parser.add_argument(
        "--pred-base",
        default="data/plays",
        help="Base directory containing <game_id>/plays.jsonl prediction outputs.",
    )
    parser.add_argument("--json", action="store_true", help="Print report as JSON.")
    parser.add_argument(
        "--exclude-disposition",
        action="append",
        default=["skip_unusable", "delete_candidate"],
        help="Gold rows with this review_disposition are excluded from metrics. Repeatable.",
    )
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=None,
        help="Optional quality gate per game; exit non-zero if any evaluated game is below this value.",
    )
    args = parser.parse_args()

    report = evaluate_gold_file(
        args.path,
        pred_base=args.pred_base,
        excluded_dispositions=tuple(args.exclude_disposition),
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Gold file: {report['gold_path']}")
        print(
            f"Excluded rows: {report.get('excluded_rows', 0)} "
            f"(dispositions={', '.join(report.get('excluded_dispositions', []))})"
        )
        failures: list[str] = []
        for game_id, game_report in report["games"].items():
            if "error" in game_report:
                print(f"- {game_id}: skipped ({game_report['error']})")
                continue
            metrics = game_report["metrics"]
            pass_rate = metrics["play_pass_rate"]
            matched = metrics["rows"]["matched"]
            print(
                f"- {game_id}: matched={matched}, "
                f"play_pass_rate={_pct(pass_rate)}, "
                f"pred={game_report['prediction_path']}"
            )
            if args.min_pass_rate is not None and pass_rate < args.min_pass_rate:
                failures.append(f"{game_id}={pass_rate:.4f}")
        if failures:
            print(f"\nFAIL: below min pass rate {args.min_pass_rate:.4f} -> {', '.join(failures)}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
