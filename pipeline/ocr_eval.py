import json
from collections import Counter
from pathlib import Path


CORE_FIELDS = (
    "quarter",
    "clock",
    "down",
    "distance",
    "offense_score",
    "defense_score",
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


def _normalize(value):
    if isinstance(value, str):
        return value.strip()
    return value


def evaluate_predictions(
    *,
    gold_rows: list[dict],
    predicted_rows: list[dict],
    key_field: str = "play_id",
    fields: tuple[str, ...] = CORE_FIELDS,
) -> dict:
    gold_by_key = {row[key_field]: row for row in gold_rows if row.get(key_field) is not None}
    predicted_by_key = {
        row[key_field]: row for row in predicted_rows if row.get(key_field) is not None
    }

    common_keys = sorted(set(gold_by_key).intersection(predicted_by_key))
    if not common_keys:
        raise ValueError(
            f"No overlapping rows by '{key_field}' between gold ({len(gold_rows)}) and predictions "
            f"({len(predicted_rows)})"
        )

    by_field: dict[str, dict] = {}
    for field in fields:
        tp = 0
        fp = 0
        fn = 0
        exact = 0
        compared = 0

        for key in common_keys:
            gold_value = _normalize(gold_by_key[key].get(field))
            predicted_value = _normalize(predicted_by_key[key].get(field))

            if gold_value is not None:
                compared += 1
            if predicted_value is not None and gold_value is not None and predicted_value == gold_value:
                tp += 1
                exact += 1
            elif predicted_value is not None and gold_value is None:
                fp += 1
            elif predicted_value is not None and gold_value is not None and predicted_value != gold_value:
                fp += 1
                fn += 1
            elif predicted_value is None and gold_value is not None:
                fn += 1

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        accuracy = exact / compared if compared else 0.0

        by_field[field] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "accuracy": round(accuracy, 4),
            "compared_rows": compared,
        }

    fully_correct = 0
    for key in common_keys:
        gold = gold_by_key[key]
        pred = predicted_by_key[key]
        if all(_normalize(gold.get(field)) == _normalize(pred.get(field)) for field in fields):
            fully_correct += 1

    quality_confusion = Counter()
    for key in common_keys:
        gold_quality = _normalize(gold_by_key[key].get("quality_flag")) or "missing"
        pred_quality = _normalize(predicted_by_key[key].get("quality_flag")) or "missing"
        quality_confusion[f"{gold_quality}->{pred_quality}"] += 1

    pass_rate = fully_correct / len(common_keys)
    return {
        "rows": {
            "gold": len(gold_rows),
            "predicted": len(predicted_rows),
            "matched": len(common_keys),
        },
        "fields": by_field,
        "play_pass_rate": round(pass_rate, 4),
        "plays_all_core_fields_correct": fully_correct,
        "quality_flag_confusion": dict(sorted(quality_confusion.items())),
    }
