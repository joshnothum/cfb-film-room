#!/usr/bin/env python3
import argparse
from datetime import datetime
from pathlib import Path
import shutil


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a timestamped backup copy of a JSONL file.")
    parser.add_argument("path", help="Path to JSONL file.")
    parser.add_argument(
        "--out-dir",
        default="data/qa/backups",
        help="Directory where backup file will be written.",
    )
    args = parser.parse_args()

    source = Path(args.path)
    if not source.exists():
        print(f"Source file does not exist: {source}")
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_name = f"{source.stem}.{stamp}{source.suffix}"
    backup_path = out_dir / backup_name
    shutil.copy2(source, backup_path)
    print(f"Backup written: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
