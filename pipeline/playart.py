import subprocess
import tempfile
from pathlib import Path


def _sample_times(start: float, end: float) -> list[float]:
    duration = max(0.0, end - start)
    if duration <= 0:
        return [round(start, 3)]
    return [
        round(start + min(0.2, duration / 4.0), 3),
        round(start + (duration / 2.0), 3),
        round(max(start, end - min(0.2, duration / 4.0)), 3),
    ]


def _extract_frame(video_path: str, timestamp_sec: float, output_path: str) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(max(0.0, timestamp_sec)),
        "-i",
        video_path,
        "-frames:v",
        "1",
        "-y",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _analyze_frame_for_play_art(frame_path: str) -> float:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for play-art detection") from exc

    image = Image.open(frame_path).convert("HSV")
    width, height = image.size

    # Focus on gameplay region where route art overlays appear.
    x0, x1 = int(width * 0.10), int(width * 0.90)
    y0, y1 = int(height * 0.35), int(height * 0.88)

    total = max(1, (x1 - x0) * (y1 - y0))
    red = 0
    yellow = 0
    blue = 0

    # PIL HSV hue range is [0,255], saturation/value [0,255]
    for y in range(y0, y1):
        for x in range(x0, x1):
            h, s, v = image.getpixel((x, y))
            if s < 95 or v < 70:
                continue
            if h <= 8 or h >= 245:
                red += 1
            elif 18 <= h <= 40:
                yellow += 1
            elif 132 <= h <= 185:
                blue += 1

    red_r = red / total
    yellow_r = yellow / total
    blue_r = blue / total

    # Prefer mixed route-art colors; single-color noise should score low.
    active_colors = sum(1 for r in (red_r, yellow_r, blue_r) if r > 0.0015)
    combined = red_r + yellow_r + blue_r
    color_mix_bonus = 0.015 * max(0, active_colors - 1)
    score = min(1.0, (combined + color_mix_bonus) / 0.03)
    return round(score, 3)


def detect_play_art_in_clip(
    *,
    video_path: str,
    start_sec: float,
    end_sec: float,
) -> dict:
    best_score = 0.0
    best_time = start_sec

    with tempfile.TemporaryDirectory() as tmp_dir:
        for idx, ts in enumerate(_sample_times(start_sec, end_sec), start=1):
            frame_path = str(Path(tmp_dir) / f"frame_{idx}.png")
            _extract_frame(video_path, ts, frame_path)
            score = _analyze_frame_for_play_art(frame_path)
            if score > best_score:
                best_score = score
                best_time = ts

    return {
        "play_art_visible": None,
        "play_art_confidence": round(best_score, 3),
        "play_art_sample_time_sec": round(best_time, 3),
    }


def enrich_records_with_play_art(
    *,
    records: list[dict],
    source_video: str,
    min_confidence: float = 0.55,
    progress_callback=None,
) -> list[dict]:
    enriched: list[dict] = []
    total = len(records)
    for idx, record in enumerate(records, start=1):
        record_copy = dict(record)
        try:
            result = detect_play_art_in_clip(
                video_path=source_video,
                start_sec=float(record_copy["start_sec"]),
                end_sec=float(record_copy["end_sec"]),
            )
            confidence = float(result["play_art_confidence"])
            record_copy["play_art_confidence"] = round(confidence, 3)
            record_copy["play_art_sample_time_sec"] = result["play_art_sample_time_sec"]
            record_copy["play_art_visible"] = confidence >= min_confidence
        except (subprocess.SubprocessError, RuntimeError, ValueError):
            record_copy["play_art_visible"] = None
            record_copy["play_art_confidence"] = None
            record_copy["play_art_sample_time_sec"] = None
        enriched.append(record_copy)
        if progress_callback:
            progress_callback(idx, total)
    return enriched
