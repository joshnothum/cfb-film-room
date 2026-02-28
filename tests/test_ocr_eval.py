from pipeline import ocr_eval


def test_evaluate_predictions_reports_field_metrics_and_pass_rate():
    gold = [
        {
            "play_id": "g:1",
            "quarter": 1,
            "clock": "12:30",
            "down": 1,
            "distance": 10,
            "home_score": 0,
            "away_score": 0,
            "quality_flag": "ok",
        },
        {
            "play_id": "g:2",
            "quarter": 1,
            "clock": "10:10",
            "down": 3,
            "distance": 6,
            "home_score": 7,
            "away_score": 0,
            "quality_flag": "ok",
        },
        {
            "play_id": "g:3",
            "quarter": 1,
            "clock": "08:55",
            "down": 2,
            "distance": 4,
            "home_score": 7,
            "away_score": 3,
            "quality_flag": "needs_review",
        },
    ]
    pred = [
        {
            "play_id": "g:1",
            "quarter": 1,
            "clock": "12:30",
            "down": 1,
            "distance": 10,
            "home_score": 0,
            "away_score": 0,
            "quality_flag": "ok",
        },
        {
            "play_id": "g:2",
            "quarter": 1,
            "clock": "10:10",
            "down": 3,
            "distance": 5,
            "home_score": 7,
            "away_score": 0,
            "quality_flag": "needs_review",
        },
        {
            "play_id": "g:3",
            "quarter": 1,
            "clock": "08:55",
            "down": 2,
            "distance": 4,
            "home_score": None,
            "away_score": 3,
            "quality_flag": "needs_review",
        },
    ]

    metrics = ocr_eval.evaluate_predictions(gold_rows=gold, predicted_rows=pred)

    assert metrics["rows"]["matched"] == 3
    assert metrics["plays_all_core_fields_correct"] == 1
    assert metrics["play_pass_rate"] == 0.3333
    assert metrics["fields"]["distance"]["tp"] == 2
    assert metrics["fields"]["distance"]["fp"] == 1
    assert metrics["fields"]["distance"]["fn"] == 1
    assert metrics["fields"]["home_score"]["recall"] == 0.6667


def test_evaluate_predictions_quality_gate_sample_passes_target():
    gold = [
        {
            "play_id": "g:1",
            "quarter": 1,
            "clock": "14:00",
            "down": 1,
            "distance": 10,
            "home_score": 0,
            "away_score": 0,
            "quality_flag": "ok",
        },
        {
            "play_id": "g:2",
            "quarter": 1,
            "clock": "11:40",
            "down": 2,
            "distance": 7,
            "home_score": 0,
            "away_score": 0,
            "quality_flag": "ok",
        },
        {
            "play_id": "g:3",
            "quarter": 1,
            "clock": "09:20",
            "down": 3,
            "distance": 5,
            "home_score": 7,
            "away_score": 0,
            "quality_flag": "ok",
        },
        {
            "play_id": "g:4",
            "quarter": 1,
            "clock": "07:01",
            "down": 1,
            "distance": 10,
            "home_score": 7,
            "away_score": 3,
            "quality_flag": "needs_review",
        },
    ]
    pred = [
        dict(gold[0]),
        dict(gold[1]),
        dict(gold[2]),
        {
            "play_id": "g:4",
            "quarter": 1,
            "clock": "07:01",
            "down": 1,
            "distance": 9,
            "home_score": 7,
            "away_score": 3,
            "quality_flag": "needs_review",
        },
    ]

    metrics = ocr_eval.evaluate_predictions(gold_rows=gold, predicted_rows=pred)

    # CI guardrail sample: if evaluator logic regresses, this should fail.
    assert metrics["play_pass_rate"] >= 0.75
    assert metrics["quality_flag_confusion"]["ok->ok"] == 3
