from collections import defaultdict
from pathlib import Path

from pipeline.ocr_eval import evaluate_predictions
from pipeline.ocr_gold import load_jsonl


CORE_FIELDS = (
    "quarter",
    "clock",
    "down",
    "distance",
    "offense_score",
    "defense_score",
)
TARGET_FIELDS = CORE_FIELDS + ("quality_flag",)


def _is_labeled(row: dict) -> bool:
    return all(row.get(field) is not None for field in TARGET_FIELDS)


def find_first_unlabeled(rows: list[dict]) -> tuple[int, dict] | tuple[None, None]:
    for idx, row in enumerate(rows, start=1):
        if not _is_labeled(row):
            return idx, row
    return None, None


def missing_target_fields(row: dict) -> list[str]:
    return [field for field in TARGET_FIELDS if row.get(field) is None]


def progress_summary(rows: list[dict]) -> dict:
    total = len(rows)
    completed = sum(1 for row in rows if _is_labeled(row))
    remaining = total - completed
    percent = (completed / total) if total else 0.0

    by_priority = defaultdict(lambda: {"total": 0, "completed": 0})
    for row in rows:
        key = str(row.get("label_priority") or "unscored")
        by_priority[key]["total"] += 1
        if _is_labeled(row):
            by_priority[key]["completed"] += 1

    return {
        "total": total,
        "completed": completed,
        "remaining": remaining,
        "percent_complete": round(percent, 4),
        "by_priority": dict(sorted(by_priority.items())),
    }


def evaluate_gold_file(gold_path: str | Path, pred_base: str | Path = "data/plays") -> dict:
    gold_rows = load_jsonl(gold_path)
    rows_by_game: dict[str, list[dict]] = defaultdict(list)
    for row in gold_rows:
        game_id = row.get("game_id")
        if game_id:
            rows_by_game[str(game_id)].append(row)

    by_game: dict[str, dict] = {}
    for game_id, game_rows in sorted(rows_by_game.items()):
        pred_path = Path(pred_base) / game_id / "plays.jsonl"
        if not pred_path.exists():
            by_game[game_id] = {
                "prediction_path": str(pred_path),
                "error": "prediction file missing",
            }
            continue
        pred_rows = load_jsonl(pred_path)
        metrics = evaluate_predictions(gold_rows=game_rows, predicted_rows=pred_rows)
        by_game[game_id] = {
            "prediction_path": str(pred_path),
            "metrics": metrics,
        }

    return {
        "gold_path": str(gold_path),
        "games": by_game,
    }
