from unittest.mock import patch

from pipeline import playart


def test_sample_times_returns_three_points():
    times = playart._sample_times(10.0, 20.0)
    assert len(times) == 3
    assert times[0] >= 10.0
    assert times[2] <= 20.0


def test_enrich_records_with_play_art_marks_visible_when_confident():
    records = [{"play_id": "g:1", "start_sec": 0.0, "end_sec": 8.0}]
    with patch(
        "pipeline.playart.detect_play_art_in_clip",
        return_value={
            "play_art_visible": None,
            "play_art_confidence": 0.82,
            "play_art_sample_time_sec": 4.0,
        },
    ):
        enriched = playart.enrich_records_with_play_art(
            records=records,
            source_video="videos/game.mp4",
            min_confidence=0.55,
        )
    assert enriched[0]["play_art_visible"] is True
    assert enriched[0]["play_art_confidence"] == 0.82


def test_enrich_records_with_play_art_handles_detection_failure():
    records = [{"play_id": "g:1", "start_sec": 0.0, "end_sec": 8.0}]
    with patch("pipeline.playart.detect_play_art_in_clip", side_effect=RuntimeError("no pil")):
        enriched = playart.enrich_records_with_play_art(
            records=records,
            source_video="videos/game.mp4",
        )
    assert enriched[0]["play_art_visible"] is None
    assert enriched[0]["play_art_confidence"] is None
