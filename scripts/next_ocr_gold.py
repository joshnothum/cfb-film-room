#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.ocr_gold import load_jsonl
from pipeline.ocr_labeling import find_first_unlabeled, missing_target_fields


def main() -> int:
    parser = argparse.ArgumentParser(description="Show the next unlabeled OCR gold row.")
    parser.add_argument("path", help="Path to OCR gold JSONL file.")
    parser.add_argument("--json", action="store_true", help="Print full JSON object for the row.")
    args = parser.parse_args()

    rows = load_jsonl(args.path)
    line_no, row = find_first_unlabeled(rows)
    if row is None:
        print("All rows are fully labeled. Nice.")
        return 0

    missing = missing_target_fields(row)
    print(f"Next unlabeled row: line {line_no}")
    print(f"play_id: {row.get('play_id')}")
    print(f"clip_path: {row.get('clip_path')}")
    print(f"missing: {', '.join(missing)}")
    if args.json:
        print(json.dumps(row, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
