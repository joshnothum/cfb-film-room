#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


FLAVOR_LINES = (
    "Polishing JSONL helmets before kickoff...",
    "Tidying line spacing so the refs do not throw flags...",
    "Running a quick pre-snap format check...",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize JSONL to one valid JSON object per line.")
    parser.add_argument("path", help="Path to JSONL file.")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Rewrite the input file in-place. If omitted, output goes to stdout.",
    )
    args = parser.parse_args()

    path = Path(args.path)
    print(f"[format] {FLAVOR_LINES[0]}")
    print(f"[format] Reading {path}")
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{idx}: invalid JSON ({exc})") from exc

    print(f"[format] Parsed {len(rows)} row(s). {FLAVOR_LINES[1]}")
    output = "\n".join(json.dumps(row, ensure_ascii=False, separators=(", ", ": ")) for row in rows) + "\n"
    if args.in_place:
        path.write_text(output, encoding="utf-8")
        print(f"[format] Wrote normalized JSONL to {path}. {FLAVOR_LINES[2]}")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
