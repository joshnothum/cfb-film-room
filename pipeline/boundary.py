import re
import subprocess


def detect_scene_change_times(
    *,
    video_path: str,
    threshold: float = 0.25,
) -> list[float]:
    """Return scene-change timestamps from ffmpeg metadata output."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        video_path,
        "-filter:v",
        f"select='gt(scene,{threshold})',metadata=print",
        "-an",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    pattern = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")

    points: list[float] = []
    for line in (result.stderr or "").splitlines():
        match = pattern.search(line)
        if match:
            points.append(float(match.group(1)))
    return points


def scene_points_to_segments(
    *,
    scene_points: list[float],
    duration_seconds: float,
    pre_snap_padding: float = 2.0,
    post_whistle_padding: float = 3.0,
    min_play_seconds: float = 3.0,
    max_play_seconds: float = 25.0,
) -> list[tuple[float, float]]:
    """Convert scene points into pre-snap -> whistle candidate segments."""
    if duration_seconds <= 0:
        return []

    if max_play_seconds <= 0 or min_play_seconds <= 0:
        raise ValueError("min/max play seconds must be positive")
    if min_play_seconds > max_play_seconds:
        raise ValueError("min_play_seconds must be <= max_play_seconds")

    points = sorted({p for p in scene_points if 0 < p < duration_seconds})
    if not points:
        return [(0.0, round(duration_seconds, 3))]

    segments: list[tuple[float, float]] = []
    for p in points:
        start = max(0.0, p - pre_snap_padding)
        end = min(duration_seconds, p + post_whistle_padding)
        if end <= start:
            continue
        if (end - start) < min_play_seconds:
            end = min(duration_seconds, start + min_play_seconds)
        if (end - start) > max_play_seconds:
            end = start + max_play_seconds
        segments.append((round(start, 3), round(end, 3)))

    # Deduplicate and merge overlaps to avoid fragmented clip spam.
    merged: list[tuple[float, float]] = []
    for start, end in sorted(segments):
        if not merged:
            merged.append((start, end))
            continue
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, round(max(prev_end, end), 3))
        else:
            merged.append((start, end))
    return merged
