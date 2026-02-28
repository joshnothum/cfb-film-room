#!/usr/bin/env python3
import argparse
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.ocr_gold import load_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="List or delete clips marked review_disposition=delete_candidate.")
    parser.add_argument("path", help="Path to OCR gold JSONL file.")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete candidate clips from disk. Requires --confirm.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required with --delete to avoid accidental removal.",
    )
    args = parser.parse_args()

    rows = load_jsonl(args.path)
    candidates = [row for row in rows if row.get("review_disposition") == "delete_candidate"]

    if not candidates:
        print("No delete candidates found.")
        return 0

    print(f"Found {len(candidates)} delete candidate row(s):")
    for row in candidates:
        print(f"- {row.get('play_id')}: {row.get('clip_path')}")

    if not args.delete:
        return 0

    if not args.confirm:
        print("Refusing to delete without --confirm.")
        return 1

    deleted = 0
    missing = 0
    for row in candidates:
        clip_path = row.get("clip_path")
        if not clip_path:
            continue
        clip = Path(clip_path)
        if clip.exists():
            clip.unlink()
            deleted += 1
        else:
            missing += 1

    print(f"Deleted {deleted} file(s). Missing {missing} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
