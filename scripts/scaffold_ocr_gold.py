#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.ocr_gold import build_gold_template_rows, load_jsonl, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a label-ready OCR gold JSONL from plays.jsonl.")
    parser.add_argument("--plays", required=True, help="Path to source plays.jsonl.")
    parser.add_argument(
        "--out",
        default="data/qa/ocr_gold.jsonl",
        help="Destination path for scaffolded gold labels.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional number of plays to include.")
    parser.add_argument(
        "--only-needs-review",
        action="store_true",
        help="Include only rows where quality_flag is needs_review.",
    )
    parser.add_argument(
        "--seed-with-predictions",
        action="store_true",
        help="Pre-fill target OCR fields using current predictions instead of nulls.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite destination file if it exists.",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    if out_path.exists() and not args.overwrite:
        print(f"Refusing to overwrite existing file: {out_path}")
        print("Re-run with --overwrite if you want to replace it.")
        return 1

    plays_rows = load_jsonl(args.plays)
    if args.only_needs_review:
        plays_rows = [row for row in plays_rows if row.get("quality_flag") == "needs_review"]
    if args.limit is not None:
        plays_rows = plays_rows[: args.limit]

    scaffold = build_gold_template_rows(
        plays_rows=plays_rows,
        include_predicted_values=args.seed_with_predictions,
    )
    write_jsonl(out_path, scaffold)
    print(f"Wrote {len(scaffold)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
