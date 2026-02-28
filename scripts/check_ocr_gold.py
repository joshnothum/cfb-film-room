#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.ocr_labeling import CORE_FIELDS

REQUIRED_FIELDS = (
    "play_id",
    "game_id",
    "quarter",
    "clock",
    "down",
    "distance",
    "offense_score",
    "defense_score",
    "quality_flag",
)
QUALITY_VALUES = {"ok", "needs_review", None}
CLOCK_RE = re.compile(r"^[0-5]?\d:[0-5]\d$")
FLAVOR_START = "Sending label sheet to replay booth..."
FLAVOR_PASS = "Scoreboard crew says the sheet looks game-ready."
FLAVOR_FAIL = "Replay booth found some flags to review."


def _is_int_or_none(value) -> bool:
    return value is None or (isinstance(value, int) and not isinstance(value, bool))


def validate_row(row: dict, line_no: int, strict_ok_complete: bool) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in row:
            errors.append(f"line {line_no}: missing required field '{field}'")

    quarter = row.get("quarter")
    if not _is_int_or_none(quarter) or (isinstance(quarter, int) and not 1 <= quarter <= 4):
        errors.append(f"line {line_no}: quarter must be null or int 1-4")

    clock = row.get("clock")
    if clock is not None and (not isinstance(clock, str) or not CLOCK_RE.fullmatch(clock)):
        errors.append(f"line {line_no}: clock must be null or M:SS")

    down = row.get("down")
    if not _is_int_or_none(down) or (isinstance(down, int) and not 1 <= down <= 4):
        errors.append(f"line {line_no}: down must be null or int 1-4")

    distance = row.get("distance")
    if not _is_int_or_none(distance) or (isinstance(distance, int) and distance < 0):
        errors.append(f"line {line_no}: distance must be null or non-negative int")

    for score_field in ("offense_score", "defense_score"):
        score = row.get(score_field)
        if not _is_int_or_none(score) or (isinstance(score, int) and score < 0):
            errors.append(f"line {line_no}: {score_field} must be null or non-negative int")

    quality = row.get("quality_flag")
    if quality not in QUALITY_VALUES:
        errors.append(f"line {line_no}: quality_flag must be one of: ok, needs_review, null")
    elif strict_ok_complete and quality == "ok":
        missing_core = [field for field in CORE_FIELDS if row.get(field) is None]
        if missing_core:
            errors.append(
                f"line {line_no}: quality_flag=ok requires all core fields; missing: {', '.join(missing_core)}"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate OCR gold JSONL labels.")
    parser.add_argument("path", help="Path to OCR gold JSONL file.")
    parser.add_argument(
        "--strict-ok-complete",
        action="store_true",
        help="Require all core fields to be non-null when quality_flag is ok.",
    )
    args = parser.parse_args()

    path = Path(args.path)
    print(f"[validate] {FLAVOR_START}")
    print(f"[validate] Checking {path}")
    errors: list[str] = []
    rows = 0
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            rows += 1
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append(f"line {idx}: invalid JSON ({exc})")
                continue
            if not isinstance(row, dict):
                errors.append(f"line {idx}: each JSONL line must be an object")
                continue
            errors.extend(validate_row(row, idx, strict_ok_complete=args.strict_ok_complete))

    if errors:
        print(f"[validate] {FLAVOR_FAIL}")
        print(f"Found {len(errors)} validation error(s) in {path}:")
        for err in errors:
            print(f"- {err}")
        return 1

    print(f"[validate] {FLAVOR_PASS}")
    print(f"OK: {path} ({rows} rows validated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
