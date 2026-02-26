from unittest.mock import Mock, patch

import pytest

from pipeline import boundary


def test_detect_scene_change_times_parses_pts_time_lines():
    stderr = "\n".join(
        [
            "frame:10   pts:100 pts_time:4.000",
            "frame:20   pts:200 pts_time:8.500",
        ]
    )
    fake = Mock(stderr=stderr)
    with patch("pipeline.boundary.subprocess.run", return_value=fake):
        points = boundary.detect_scene_change_times(video_path="game.mp4", threshold=0.22)
    assert points == [4.0, 8.5]


def test_detect_scene_change_times_builds_expected_ffmpeg_command():
    fake = Mock(stderr="")
    with patch("pipeline.boundary.subprocess.run", return_value=fake) as run_mock:
        boundary.detect_scene_change_times(video_path="film.mp4", threshold=0.31)

    cmd = run_mock.call_args.args[0]
    assert cmd[0] == "ffmpeg"
    assert "film.mp4" in cmd
    assert "select='gt(scene,0.31)',metadata=print" in cmd


def test_scene_points_to_segments_applies_padding_and_bounds():
    segments = boundary.scene_points_to_segments(
        scene_points=[1.0, 10.0, 30.0],
        duration_seconds=35.0,
        pre_snap_padding=2.0,
        post_whistle_padding=3.0,
        min_play_seconds=3.0,
        max_play_seconds=25.0,
    )
    assert segments == [(0.0, 4.0), (8.0, 13.0), (28.0, 33.0)]


def test_scene_points_to_segments_merges_overlaps():
    segments = boundary.scene_points_to_segments(
        scene_points=[10.0, 11.0],
        duration_seconds=50.0,
        pre_snap_padding=2.0,
        post_whistle_padding=3.0,
    )
    assert segments == [(8.0, 14.0)]


def test_scene_points_to_segments_without_points_returns_full_duration():
    segments = boundary.scene_points_to_segments(scene_points=[], duration_seconds=12.0)
    assert segments == [(0.0, 12.0)]


def test_scene_points_to_segments_rejects_invalid_ranges():
    with pytest.raises(ValueError):
        boundary.scene_points_to_segments(
            scene_points=[5.0],
            duration_seconds=20.0,
            min_play_seconds=9.0,
            max_play_seconds=3.0,
        )


def test_scene_points_to_segments_clamps_to_max_duration():
    segments = boundary.scene_points_to_segments(
        scene_points=[10.0],
        duration_seconds=40.0,
        pre_snap_padding=2.0,
        post_whistle_padding=40.0,
        min_play_seconds=3.0,
        max_play_seconds=6.0,
    )
    assert segments == [(8.0, 14.0)]
