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
    assert enriched[0]["ocr_sample_time_sec"] == 4.0


def test_enrich_records_with_ocr_marks_needs_review_on_failure():
    records = [{"play_id": "g:play:0001", "start_sec": 3.0, "end_sec": 9.0}]
    with patch("pipeline.ocr.extract_text_at_time", side_effect=ValueError("bad")):
        enriched = ocr.enrich_records_with_ocr(records=records, source_video="videos/game.mp4")
    assert enriched[0]["quality_flag"] == "needs_review"
    assert enriched[0]["ocr_raw_text"] is None
