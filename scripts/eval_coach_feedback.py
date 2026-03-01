#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.coach_feedback import REQUIRED_TOP_LEVEL_KEYS


def load_jsonl(path: str) -> list[dict]:
    rows: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _required_sections_present(analysis: dict) -> tuple[bool, list[str]]:
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(analysis.keys()))
    return (len(missing) == 0, missing)


def evaluate(golden_path: str) -> int:
    rows = load_jsonl(golden_path)
    total = len(rows)
    with_output = 0
    schema_ok = 0
    approved = 0

    for row in rows:
        if row.get("approved") is True:
            approved += 1

        analysis = row.get("analysis")
        analysis_path = row.get("analysis_path")
        if analysis is None and analysis_path:
            path = Path(analysis_path)
            if path.exists():
                analysis = json.loads(path.read_text(encoding="utf-8"))

        if analysis is None:
            continue

        with_output += 1
        ok, _missing = _required_sections_present(analysis)
        if ok:
            schema_ok += 1

    print(f"cases_total={total}")
    print(f"cases_with_analysis={with_output}")
    print(f"schema_complete={schema_ok}")
    print(f"approved={approved}")

    if with_output and schema_ok != with_output:
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eval-coach-feedback",
        description="Evaluate coach feedback golden set for schema completeness and approvals.",
    )
    parser.add_argument("--gold", required=True, help="Path to coach feedback golden JSONL file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return evaluate(args.gold)


if __name__ == "__main__":
    raise SystemExit(main())
