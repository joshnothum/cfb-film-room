from unittest.mock import patch

from pipeline import ocr


def test_parse_scorebug_text_extracts_core_fields():
    text = "Q3 4:52 3RD & 7 UGA 35 BAMA 14 UGA 21"
    parsed = ocr.parse_scorebug_text(text)
    assert parsed["quarter"] == 3
    assert parsed["clock"] == "4:52"
    assert parsed["down"] == 3
    assert parsed["distance"] == 7
    assert parsed["offense_score"] == 14
    assert parsed["defense_score"] == 21
    assert parsed["quarter_confidence"] is not None


def test_enrich_records_with_ocr_sets_ok_quality_when_confident():
    records = [
        {
            "play_id": "g:play:0001",
            "start_sec": 0.0,
            "end_sec": 8.0,
            "quality_flag": "unreviewed",
        }
    ]
    with patch(
        "pipeline.ocr.extract_text_at_time",
        return_value="Q2 5:10 2ND & 6 UGA 40 UGA 17 BAMA 14",
    ), patch(
        "pipeline.ocr.extract_best_scorebug_scores_for_record",
        return_value={
            "offense_score": 17,
            "defense_score": 14,
            "offense_score_confidence": 0.93,
            "defense_score_confidence": 0.94,
            "score_ocr_debug": "ok",
            "score_sample_time_sec": 4.0,
        },
    ):
        enriched = ocr.enrich_records_with_ocr(
            records=records,
            source_video="videos/game.mp4",
            sample_frame="mid",
            min_confidence=0.7,
        )

    assert enriched[0]["quality_flag"] == "ok"
    assert enriched[0]["quarter"] == 2
    assert enriched[0]["down"] == 2
    assert enriched[0]["distance"] == 6
    assert enriched[0]["offense_score"] == 17
    assert enriched[0]["defense_score"] == 14
    assert enriched[0]["ocr_sample_time_sec"] == 4.0


def test_enrich_records_with_ocr_marks_needs_review_on_failure():
    records = [{"play_id": "g:play:0001", "start_sec": 3.0, "end_sec": 9.0}]
    with patch("pipeline.ocr.extract_text_at_time", side_effect=ValueError("bad")):
        enriched = ocr.enrich_records_with_ocr(records=records, source_video="videos/game.mp4")
    assert enriched[0]["quality_flag"] == "needs_review"
    assert enriched[0]["ocr_raw_text"] is None


def test_parse_score_from_text_returns_expected_digits():
    assert ocr._parse_score_from_text("  14  ") == 14
    assert ocr._parse_score_from_text("TEAM 7") == 7
    assert ocr._parse_score_from_text("NONE") is None


def test_score_sample_times_returns_multiple_points():
    times = ocr._score_sample_times(0.0, 8.0)
    assert len(times) >= 3
    assert min(times) >= 0.0
    assert max(times) <= 8.0


def test_enrich_records_with_ocr_carries_forward_previous_scores():
    records = [
        {"play_id": "g:1", "start_sec": 0.0, "end_sec": 8.0},
        {"play_id": "g:2", "start_sec": 8.0, "end_sec": 16.0},
    ]

    def _score_result(*, start_sec, **kwargs):
        if start_sec < 1.0:
            return {
                "offense_score": 10,
                "defense_score": 7,
                "offense_score_confidence": 0.9,
                "defense_score_confidence": 0.9,
                "score_ocr_debug": "first",
                "score_sample_time_sec": 4.0,
            }
        return {
            "offense_score": None,
            "defense_score": None,
            "offense_score_confidence": 0.0,
            "defense_score_confidence": 0.0,
            "score_ocr_debug": "missing",
            "score_sample_time_sec": 12.0,
        }

    with patch("pipeline.ocr.extract_text_at_time", return_value="Q1 7:00 1ST & 10"), patch(
        "pipeline.ocr.extract_best_scorebug_scores_for_record", side_effect=_score_result
    ):
        enriched = ocr.enrich_records_with_ocr(records=records, source_video="videos/game.mp4")

    assert enriched[1]["offense_score"] == 10
    assert enriched[1]["defense_score"] == 7
    assert enriched[1]["score_imputed_from_previous"] is True


def test_quality_flag_regression_fixture_requires_all_critical_fields():
    record = {
        "quarter": 2,
        "quarter_confidence": 0.9,
        "clock": None,
        "clock_confidence": None,
        "down": 2,
        "down_confidence": 0.9,
        "distance": 8,
        "distance_confidence": 0.9,
    }
    assert ocr._compute_quality_flag(record, min_confidence=0.75) == "needs_review"


def test_parse_scorebug_text_regression_fixture_parses_compact_down_distance():
    parsed = ocr.parse_scorebug_text("Q4 1:05 4TH&1 UGA 39 BAMA 24 UGA 27")
    assert parsed["quarter"] == 4
    assert parsed["clock"] == "1:05"
    assert parsed["down"] == 4
    assert parsed["distance"] == 1
