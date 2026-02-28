#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Open the clip for a JSONL row (macOS).")
    parser.add_argument("path", help="Path to OCR gold JSONL file.")
    parser.add_argument(
        "--line",
        type=int,
        required=True,
        help="1-based line number in the JSONL file (use VS Code ${lineNumber}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved clip path without opening it.",
    )
    args = parser.parse_args()

    if args.line < 1:
        print("--line must be >= 1")
        return 1

    source = Path(args.path)
    lines = source.read_text(encoding="utf-8").splitlines()
    if args.line > len(lines):
        print(f"line {args.line} is out of range (file has {len(lines)} lines)")
        return 1

    raw = lines[args.line - 1].strip()
    if not raw:
        print(f"line {args.line} is empty")
        return 1

    row = json.loads(raw)
    clip_path = row.get("clip_path")
    if not clip_path:
        print(f"line {args.line}: clip_path missing")
        return 1

    clip = Path(clip_path)
    if not clip.exists():
        print(f"line {args.line}: clip_path not found -> {clip}")
        return 1

    if args.dry_run:
        print(f"Resolved clip: {clip}")
        return 0

    subprocess.run(["open", str(clip)], check=True)
    print(f"Opened clip: {clip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
