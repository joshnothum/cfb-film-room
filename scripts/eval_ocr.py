#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.ocr_eval import CORE_FIELDS, evaluate_predictions, load_jsonl


def _format_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _print_human_report(metrics: dict) -> None:
    rows = metrics["rows"]
    print(f"Matched plays: {rows['matched']} (gold={rows['gold']}, predicted={rows['predicted']})")
    print(f"All-core-fields pass rate: {_format_pct(metrics['play_pass_rate'])}")
    print("")
    print("Field metrics")
    print("field           precision  recall     accuracy   tp  fp  fn")
    for field in CORE_FIELDS:
        stats = metrics["fields"][field]
        print(
            f"{field:<15} {_format_pct(stats['precision']):<10} {_format_pct(stats['recall']):<10} "
            f"{_format_pct(stats['accuracy']):<10} {stats['tp']:<3} {stats['fp']:<3} {stats['fn']:<3}"
        )
    print("")
    print("Quality confusion (gold->pred)")
    for label, count in metrics["quality_flag_confusion"].items():
        print(f"- {label}: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate OCR output against a labeled gold set.")
    parser.add_argument("--gold", required=True, help="Path to gold JSONL (must include play_id).")
    parser.add_argument(
        "--pred",
        required=True,
        help="Path to predicted JSONL (for example data/plays/<game>/plays.jsonl).",
    )
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=None,
        help="Optional quality gate. Exit non-zero if all-core-fields pass rate is below this value.",
    )
    parser.add_argument("--json", action="store_true", help="Print report as JSON.")
    args = parser.parse_args()

    gold_rows = load_jsonl(args.gold)
    predicted_rows = load_jsonl(args.pred)
    metrics = evaluate_predictions(gold_rows=gold_rows, predicted_rows=predicted_rows)

    if args.json:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    else:
        _print_human_report(metrics)

    if args.min_pass_rate is not None and metrics["play_pass_rate"] < args.min_pass_rate:
        print(
            f"\nFAIL: play_pass_rate={metrics['play_pass_rate']:.4f} < min_pass_rate={args.min_pass_rate:.4f}"
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
