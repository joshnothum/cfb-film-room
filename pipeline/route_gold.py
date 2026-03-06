import json
from pathlib import Path

RUN_KEYWORDS = (
    "inside_zone",
    "outside_zone",
    "zone_split",
    "power",
    "counter",
    "draw",
    "sweep",
    "dive",
    "read_option",
    "jet",
    "trap",
    "iso",
    "duo",
)
KICK_KEYWORDS = (
    "kickoff",
    "onside",
    "punt",
    "field_goal",
    "fg_",
    "pat",
    "extra_point",
)
RPO_KEYWORDS = (
    "rpo",
    "run_pass_option",
    "run-pass-option",
)


CONTEXT_FIELDS = (
    "play_id",
    "team_slug",
    "formation_slug",
    "play_slug",
    "play_name",
    "playbook_side",
    "play_art_path",
    "source_url",
    "play_type",
)

TARGET_FIELDS = (
    "review_state",
    "review_disposition",
    "primary_route_family",
    "secondary_route_family",
    "assignment_labels_expected",
    "labeler_notes",
)
DEFAULT_ASSIGNMENT_LABELS = ["X", "Y", "A", "B", "RB"]


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


def infer_route_play_type(*, play_slug: str, play_name: str, formation_slug: str = "") -> str:
    text = f"{play_slug} {play_name} {formation_slug}".lower()
    if any(keyword in text for keyword in KICK_KEYWORDS):
        return "kick"
    if any(keyword in text for keyword in RPO_KEYWORDS):
        return "rpo"
    if any(keyword in text for keyword in RUN_KEYWORDS):
        return "run"
    return "pass"


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
        if template.get("play_type") is None:
            template["play_type"] = infer_route_play_type(
                play_slug=str(row.get("play_slug") or ""),
                play_name=str(row.get("play_name") or ""),
                formation_slug=str(row.get("formation_slug") or ""),
            )

        predicted = predictions.get(str(row.get("play_id")), {})
        if include_predicted_values:
            template["review_state"] = "pending"
            template["review_disposition"] = "keep"
            template["primary_route_family"] = predicted.get("primary_route_family")
            template["secondary_route_family"] = predicted.get("secondary_route_family")
            predicted_labels = predicted.get("assignment_labels_predicted")
            if predicted_labels:
                template["assignment_labels_expected"] = list(predicted_labels)
            else:
                template["assignment_labels_expected"] = list(DEFAULT_ASSIGNMENT_LABELS)
            template["labeler_notes"] = None
        else:
            for field in TARGET_FIELDS:
                template[field] = None
            template["assignment_labels_expected"] = list(DEFAULT_ASSIGNMENT_LABELS)
        output.append(template)
    return output
