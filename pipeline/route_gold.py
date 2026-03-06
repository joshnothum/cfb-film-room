import json
from pathlib import Path


CONTEXT_FIELDS = (
    "play_id",
    "team_slug",
    "formation_slug",
    "play_slug",
    "play_name",
    "playbook_side",
    "play_art_path",
    "source_url",
)

TARGET_FIELDS = (
    "review_state",
    "review_disposition",
    "primary_route_family",
    "secondary_route_family",
    "assignment_labels_expected",
    "labeler_notes",
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


def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def build_route_gold_template_rows(
    *,
    manifest_rows: list[dict],
    include_predicted_values: bool = False,
    predicted_by_play_id: dict[str, dict] | None = None,
) -> list[dict]:
    predictions = predicted_by_play_id or {}
    output: list[dict] = []
    for row in manifest_rows:
        template = {}
        for field in CONTEXT_FIELDS:
            template[field] = row.get(field)

        predicted = predictions.get(str(row.get("play_id")), {})
        if include_predicted_values:
            template["review_state"] = "pending"
            template["review_disposition"] = "keep"
            template["primary_route_family"] = predicted.get("primary_route_family")
            template["secondary_route_family"] = predicted.get("secondary_route_family")
            template["assignment_labels_expected"] = predicted.get("assignment_labels_predicted", [])
            template["labeler_notes"] = None
        else:
            for field in TARGET_FIELDS:
                template[field] = None
        output.append(template)
    return output
