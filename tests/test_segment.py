import csv
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pipeline import segment


def test_build_fixed_segments_returns_expected_windows():
    segments = segment.build_fixed_segments(duration_seconds=20.0, clip_seconds=8.0)
    assert segments == [(0.0, 8.0), (8.0, 16.0), (16.0, 20.0)]


def test_build_fixed_segments_rejects_non_positive_clip_length():
    with pytest.raises(ValueError):
        segment.build_fixed_segments(duration_seconds=20.0, clip_seconds=0.0)


def test_build_play_records_schema_fields():
    records = segment.build_play_records(
        game_id="uga_vs_bama_2026wk01",
        source_video="videos/game.mp4",
        clips_dir="data/plays/clips",
        segments=[(0.0, 8.0)],
    )
    assert len(records) == 1
    rec = records[0]
    assert rec["play_id"] == "uga_vs_bama_2026wk01:play:0001"
    assert rec["clip_path"].endswith("data/plays/clips/play_0001.mp4")
    assert rec["start_sec"] == 0.0
    assert rec["end_sec"] == 8.0
    assert rec["duration_sec"] == 8.0
    assert rec["quarter"] is None
    assert rec["quality_flag"] == "unreviewed"


def test_write_jsonl_and_preview_csv(tmp_path: Path):
    records = [
        {
            "play_id": "g:play:0001",
            "clip_path": "clips/play_0001.mp4",
            "start_sec": 0.0,
            "end_sec": 8.0,
            "duration_sec": 8.0,
            "quarter": None,
            "clock": None,
            "down": None,
            "distance": None,
            "field_position": None,
            "result_type": None,
            "result_yards": None,
            "quality_flag": "unreviewed",
        }
    ]

    jsonl_path = tmp_path / "plays.jsonl"
    csv_path = tmp_path / "plays_preview.csv"
    segment.write_jsonl(records, str(jsonl_path))
    segment.write_preview_csv(records, str(csv_path))

    loaded = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert loaded[0]["play_id"] == "g:play:0001"

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert rows[0]["play_id"] == "g:play:0001"


def test_probe_duration_seconds_parses_ffprobe_stdout():
    fake = Mock(stdout="120.50\n")
    with patch("pipeline.segment.subprocess.run", return_value=fake) as run_mock:
        duration = segment.probe_duration_seconds("game.mp4")
    assert duration == 120.5
    run_mock.assert_called_once()
