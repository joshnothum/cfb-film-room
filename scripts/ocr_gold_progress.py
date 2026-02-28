#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.ocr_gold import load_jsonl
from pipeline.ocr_labeling import progress_summary


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description="Show OCR gold labeling progress.")
    parser.add_argument("path", help="Path to OCR gold JSONL file.")
    args = parser.parse_args()

    rows = load_jsonl(args.path)
    stats = progress_summary(rows)
    print(
        f"Progress: {stats['completed']}/{stats['total']} complete "
        f"({_pct(stats['percent_complete'])})"
    )
    print(f"Remaining: {stats['remaining']}")
    print("By priority:")
    for priority, values in stats["by_priority"].items():
        total = values["total"]
        completed = values["completed"]
        pct = (completed / total) if total else 0.0
        print(f"- {priority}: {completed}/{total} ({_pct(pct)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
