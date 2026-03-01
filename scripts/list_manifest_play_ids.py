#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="list-manifest-play-ids",
        description="List play_id values from a playbook manifest JSONL file.",
    )
    parser.add_argument("--manifest", required=True, help="Manifest JSONL path.")
    parser.add_argument("--contains", default="", help="Optional case-insensitive filter applied to play_id, formation, and play_name.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum rows to print.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.manifest)
    if not path.exists():
        raise SystemExit(f"Manifest not found: {path}")

    query = args.contains.strip().lower()
    shown = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            hay = " ".join(
                [
                    str(row.get("play_id", "")),
                    str(row.get("formation_slug", "")),
                    str(row.get("play_name", "")),
                ]
            ).lower()
            if query and query not in hay:
                continue
            print(row.get("play_id"))
            shown += 1
            if shown >= max(1, args.limit):
                break

    print(f"-- shown {shown} rows from {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
