import json
from pathlib import Path


CORE_FIELDS = (
    "review_state",
    "quarter",
    "clock",
    "down",
    "distance",
    "offense_score",
    "defense_score",
    "quality_flag",
    "review_disposition",
)

CONTEXT_FIELDS = (
    "play_id",
    "game_id",
    "start_sec",
    "end_sec",
    "clip_path",
    "source_video",
    "ocr_raw_text",
)


def load_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
    return rows


def build_gold_template_rows(
    *,
    plays_rows: list[dict],
    include_predicted_values: bool = False,
) -> list[dict]:
    output: list[dict] = []
    for row in plays_rows:
        template = {}
        for field in CONTEXT_FIELDS:
            template[field] = row.get(field)
        for field in CORE_FIELDS:
            template[field] = row.get(field) if include_predicted_values else None
        output.append(template)
    return output


def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
