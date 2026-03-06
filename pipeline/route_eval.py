from collections import Counter


TARGET_FIELDS = ("primary_route_family", "secondary_route_family")


def normalize_route_family(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    if not cleaned:
        return None
    aliases = {
        "go": "fade_or_go",
        "fade": "fade_or_go",
        "hitch": "flat_or_hitch",
        "flat": "flat_or_hitch",
        "screen": "screen_or_swing",
        "swing": "screen_or_swing",
        "bubble": "screen_or_swing",
        "smoke": "screen_or_swing",
        "screen_or_swing": "screen_or_swing",
        "cross": "cross_or_over",
        "over": "cross_or_over",
        "in": "in_or_out_break",
        "out": "in_or_out_break",
        "post": "post_or_corner",
        "corner": "post_or_corner",
        "post_or_corner": "post_or_corner",
    }
    return aliases.get(cleaned, cleaned)


def _top_two_route_families(route_candidates: list[dict]) -> tuple[str | None, str | None]:
    if not route_candidates:
        return None, None
    scored: list[tuple[str, float]] = []
    for candidate in route_candidates:
        family = normalize_route_family(candidate.get("route_type_candidate"))
        if family is None or family == "unknown":
            continue
        conf = float(candidate.get("confidence") or 0.0)
        scored.append((family, conf))
    if not scored:
        return None, None
    scored.sort(key=lambda item: item[1], reverse=True)
    first = scored[0][0]
    second = None
    for family, _ in scored[1:]:
        if family != first:
            second = family
            break
    return first, second


def build_prediction_row(*, row: dict, parse_result: dict) -> dict:
    primary, secondary = _top_two_route_families(parse_result.get("route_candidates") or [])
    return {
        "play_id": row.get("play_id"),
        "primary_route_family": primary,
        "secondary_route_family": secondary,
        "assignment_labels_predicted": list(parse_result.get("assignment_labels") or []),
        "route_parse_quality_flags": list(parse_result.get("quality_flags") or []),
    }


def evaluate_predictions(
    *,
    gold_rows: list[dict],
    predicted_rows: list[dict],
    key_field: str = "play_id",
    fields: tuple[str, ...] = TARGET_FIELDS,
) -> dict:
    gold_by_key = {row[key_field]: row for row in gold_rows if row.get(key_field)}
    predicted_by_key = {row[key_field]: row for row in predicted_rows if row.get(key_field)}
    common_keys = sorted(set(gold_by_key).intersection(predicted_by_key))
    if not common_keys:
        raise ValueError(
            f"No overlapping rows by '{key_field}' between gold ({len(gold_rows)}) and predictions "
            f"({len(predicted_rows)})"
        )

    by_field: dict[str, dict] = {}
    for field in fields:
        compared = 0
        correct = 0
        coverage = 0
        confusion = Counter()

        for key in common_keys:
            gold_value = normalize_route_family(gold_by_key[key].get(field))
            pred_value = normalize_route_family(predicted_by_key[key].get(field))
            if gold_value is None:
                continue
            compared += 1
            if pred_value is not None and pred_value != "unknown":
                coverage += 1
            if pred_value == gold_value:
                correct += 1
            confusion[f"{gold_value}->{pred_value or 'missing'}"] += 1

        accuracy = correct / compared if compared else 0.0
        coverage_rate = coverage / compared if compared else 0.0
        by_field[field] = {
            "compared_rows": compared,
            "correct_rows": correct,
            "accuracy": round(accuracy, 4),
            "coverage": round(coverage_rate, 4),
            "confusion": dict(sorted(confusion.items())),
        }

    fully_correct = 0
    fully_compared = 0
    for key in common_keys:
        gold = gold_by_key[key]
        pred = predicted_by_key[key]
        if any(normalize_route_family(gold.get(field)) is None for field in fields):
            continue
        fully_compared += 1
        if all(normalize_route_family(gold.get(field)) == normalize_route_family(pred.get(field)) for field in fields):
            fully_correct += 1

    play_pass_rate = fully_correct / fully_compared if fully_compared else 0.0
    return {
        "rows": {
            "gold": len(gold_rows),
            "predicted": len(predicted_rows),
            "matched": len(common_keys),
        },
        "fields": by_field,
        "plays_all_route_fields_correct": fully_correct,
        "plays_all_route_fields_compared": fully_compared,
        "play_pass_rate": round(play_pass_rate, 4),
    }
