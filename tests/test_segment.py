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


def test_main_uses_scene_mode_and_writes_outputs(tmp_path: Path):
    out_dir = tmp_path / "plays"
    with patch("pipeline.segment.probe_duration_seconds", return_value=30.0), patch(
        "pipeline.segment.detect_scene_change_times", return_value=[5.0, 15.0]
    ), patch("pipeline.segment.export_clips") as export_mock:
        rc = segment.main(
            [
                "--input",
                "videos/game.mp4",
                "--game-id",
                "uga_vs_bama_2026wk01",
                "--out-dir",
                str(out_dir),
                "--skip-clips",
            ]
        )

    assert rc == 0
    assert not export_mock.called
    assert (out_dir / "plays.jsonl").exists()
    assert (out_dir / "plays_preview.csv").exists()


def test_main_falls_back_to_fixed_when_scene_mode_returns_no_segments(tmp_path: Path):
    out_dir = tmp_path / "plays"
    with patch("pipeline.segment.probe_duration_seconds", return_value=20.0), patch(
        "pipeline.segment.detect_scene_change_times", return_value=[]
    ), patch("pipeline.segment.scene_points_to_segments", return_value=[]):
        rc = segment.main(
            [
                "--input",
                "videos/game.mp4",
                "--game-id",
                "fallback_case",
                "--out-dir",
                str(out_dir),
                "--clip-seconds",
                "8",
                "--skip-clips",
            ]
        )

    assert rc == 0
    lines = (out_dir / "plays.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


def test_main_fixed_mode_skips_scene_detection(tmp_path: Path):
    out_dir = tmp_path / "plays"
    with patch("pipeline.segment.probe_duration_seconds", return_value=16.0), patch(
        "pipeline.segment.detect_scene_change_times"
    ) as scene_mock:
        rc = segment.main(
            [
                "--input",
                "videos/game.mp4",
                "--game-id",
                "fixed_case",
                "--out-dir",
                str(out_dir),
                "--segmentation-mode",
                "fixed",
                "--clip-seconds",
                "8",
                "--skip-clips",
            ]
        )
    assert rc == 0
    scene_mock.assert_not_called()
    lines = (out_dir / "plays.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_main_enable_ocr_calls_enrichment(tmp_path: Path):
    out_dir = tmp_path / "plays"
    with patch("pipeline.segment.probe_duration_seconds", return_value=8.0), patch(
        "pipeline.segment.detect_scene_change_times", return_value=[]
    ), patch("pipeline.segment.scene_points_to_segments", return_value=[(0.0, 8.0)]), patch(
        "pipeline.segment.enrich_records_with_ocr",
        side_effect=lambda **kwargs: kwargs["records"],
    ) as ocr_mock:
        rc = segment.main(
            [
                "--input",
                "videos/game.mp4",
                "--game-id",
                "ocr_case",
                "--out-dir",
                str(out_dir),
                "--skip-clips",
                "--enable-ocr",
            ]
        )

    assert rc == 0
    ocr_mock.assert_called_once()


def test_main_enable_play_art_detection_calls_enrichment(tmp_path: Path):
    out_dir = tmp_path / "plays"
    with patch("pipeline.segment.probe_duration_seconds", return_value=8.0), patch(
        "pipeline.segment.detect_scene_change_times", return_value=[]
    ), patch("pipeline.segment.scene_points_to_segments", return_value=[(0.0, 8.0)]), patch(
        "pipeline.segment.enrich_records_with_play_art",
        side_effect=lambda **kwargs: kwargs["records"],
    ) as playart_mock:
        rc = segment.main(
            [
                "--input",
                "videos/game.mp4",
                "--game-id",
                "art_case",
                "--out-dir",
                str(out_dir),
                "--skip-clips",
                "--enable-play-art-detection",
            ]
        )

    assert rc == 0
    playart_mock.assert_called_once()
