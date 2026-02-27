from pipeline import ocr_gold


def test_build_gold_template_rows_defaults_target_fields_to_none():
    rows = [
        {
            "play_id": "g:1",
            "game_id": "g",
            "start_sec": 0.0,
            "end_sec": 8.0,
            "clip_path": "clips/play_0001.mp4",
            "source_video": "videos/game.mp4",
            "quarter": 1,
            "clock": "12:34",
            "down": 1,
            "distance": 10,
            "offense_score": 0,
            "defense_score": 0,
            "quality_flag": "ok",
        }
    ]

    template = ocr_gold.build_gold_template_rows(plays_rows=rows)

    assert template[0]["play_id"] == "g:1"
    assert template[0]["quarter"] is None
    assert template[0]["clock"] is None
    assert template[0]["offense_score"] is None
    assert template[0]["quality_flag"] is None


def test_build_gold_template_rows_can_seed_with_predictions():
    rows = [
        {
            "play_id": "g:1",
            "quarter": 3,
            "clock": "05:10",
            "down": 2,
            "distance": 7,
            "offense_score": 14,
            "defense_score": 10,
            "quality_flag": "needs_review",
        }
    ]

    template = ocr_gold.build_gold_template_rows(plays_rows=rows, include_predicted_values=True)

    assert template[0]["quarter"] == 3
    assert template[0]["clock"] == "05:10"
    assert template[0]["down"] == 2
    assert template[0]["distance"] == 7
    assert template[0]["offense_score"] == 14
    assert template[0]["defense_score"] == 10
    assert template[0]["quality_flag"] == "needs_review"
