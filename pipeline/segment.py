import argparse
import csv
import json
import subprocess
import time
from pathlib import Path

from pipeline.boundary import detect_scene_change_times, scene_points_to_segments
from pipeline.ocr import enrich_records_with_ocr
from pipeline.playart import enrich_records_with_play_art


def probe_duration_seconds(video_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def build_fixed_segments(duration_seconds: float, clip_seconds: float) -> list[tuple[float, float]]:
    if duration_seconds <= 0:
        return []
    if clip_seconds <= 0:
        raise ValueError("clip_seconds must be greater than 0")

    segments: list[tuple[float, float]] = []
    start = 0.0
    while start < duration_seconds:
        end = min(start + clip_seconds, duration_seconds)
        segments.append((round(start, 3), round(end, 3)))
        start = end
    return segments


def _format_play_id(game_id: str, index: int) -> str:
    return f"{game_id}:play:{index:04d}"


def _clip_name(index: int) -> str:
    return f"play_{index:04d}.mp4"


def build_play_records(
    *,
    game_id: str,
    source_video: str,
    clips_dir: str,
    segments: list[tuple[float, float]],
) -> list[dict]:
    records: list[dict] = []
    for idx, (start, end) in enumerate(segments, start=1):
        clip_path = str(Path(clips_dir) / _clip_name(idx))
        records.append(
            {
                "play_id": _format_play_id(game_id, idx),
                "game_id": game_id,
                "source_video": source_video,
                "clip_path": clip_path,
                "start_sec": start,
                "end_sec": end,
                "duration_sec": round(end - start, 3),
                "quarter": None,
                "quarter_confidence": None,
                "clock": None,
                "clock_confidence": None,
                "down": None,
                "down_confidence": None,
                "distance": None,
                "distance_confidence": None,
                "field_position": None,
                "field_position_confidence": None,
                "offense_score": None,
                "offense_score_confidence": None,
                "defense_score": None,
                "defense_score_confidence": None,
                "home_score": None,
                "home_score_confidence": None,
                "away_score": None,
                "away_score_confidence": None,
                "offensive_play_id": None,
                "defensive_shell": None,
                "result_type": None,
                "result_yards": None,
                "ocr_raw_text": None,
                "ocr_sample_time_sec": None,
                "play_art_visible": None,
                "play_art_confidence": None,
                "play_art_sample_time_sec": None,
                "quality_flag": "unreviewed",
            }
        )
    return records


def write_jsonl(records: list[dict], output_path: str) -> int:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return len(records)


def write_preview_csv(records: list[dict], output_path: str) -> int:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "play_id",
        "clip_path",
        "start_sec",
        "end_sec",
        "duration_sec",
        "quarter",
        "clock",
        "down",
        "distance",
        "field_position",
        "result_type",
        "result_yards",
        "quality_flag",
    ]
    with output_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({k: record.get(k) for k in fieldnames})
    return len(records)


def export_clips(
    *,
    source_video: str,
    clips_dir: str,
    segments: list[tuple[float, float]],
    progress_callback=None,
) -> int:
    clips_path = Path(clips_dir)
    clips_path.mkdir(parents=True, exist_ok=True)

    for idx, (start, end) in enumerate(segments, start=1):
        out_clip = clips_path / _clip_name(idx)
        duration = max(0.0, end - start)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            source_video,
            "-t",
            str(duration),
            "-c",
            "copy",
            str(out_clip),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        if progress_callback:
            progress_callback(idx, len(segments))
    return len(segments)


def _format_elapsed(start_time: float) -> str:
    elapsed = max(0.0, time.time() - start_time)
    mins, secs = divmod(int(elapsed), 60)
    return f"{mins:02d}:{secs:02d}"


def _make_progress_callback(
    *,
    label: str,
    started_at: float,
    show_progress: bool,
    every: int,
):
    if not show_progress:
        return None

    def _callback(done: int, total: int) -> None:
        if total <= 0:
            return
        if done % max(1, every) != 0 and done != total:
            return
        percent = (done / total) * 100.0
        print(
            f"[{_format_elapsed(started_at)}] {label}: {done}/{total} ({percent:.0f}%)",
            flush=True,
        )

    return _callback


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cfb-film-room-segment",
        description="Segment game video into per-play clips and metadata stubs.",
    )
    parser.add_argument("--input", required=True, help="Path to source game video.")
    parser.add_argument(
        "--game-id",
        required=True,
        help="Stable id for this recording, e.g. uga_vs_bama_2026wk01",
    )
    parser.add_argument(
        "--out-dir",
        default="data/plays",
        help="Directory for clips and metadata outputs.",
    )
    parser.add_argument(
        "--clip-seconds",
        type=float,
        default=8.0,
        help="Fixed clip length in seconds (used only with --segmentation-mode fixed).",
    )
    parser.add_argument(
        "--segmentation-mode",
        choices=("scene", "fixed"),
        default="scene",
        help="Segmentation strategy. scene uses scene-change boundaries; fixed uses equal windows.",
    )
    parser.add_argument(
        "--scene-threshold",
        type=float,
        default=0.25,
        help="Scene-change threshold passed to ffmpeg select=gt(scene,THRESHOLD).",
    )
    parser.add_argument(
        "--pre-snap-padding",
        type=float,
        default=2.0,
        help="Seconds added before each detected boundary.",
    )
    parser.add_argument(
        "--post-whistle-padding",
        type=float,
        default=3.0,
        help="Seconds added after each detected boundary.",
    )
    parser.add_argument(
        "--min-play-seconds",
        type=float,
        default=3.0,
        help="Minimum play clip duration after boundary normalization.",
    )
    parser.add_argument(
        "--max-play-seconds",
        type=float,
        default=25.0,
        help="Maximum play clip duration after boundary normalization.",
    )
    parser.add_argument(
        "--skip-clips",
        action="store_true",
        help="Write metadata only and skip ffmpeg clip extraction.",
    )
    parser.add_argument(
        "--enable-ocr",
        action="store_true",
        help="Run OCR enrichment on sampled play frames.",
    )
    parser.add_argument(
        "--ocr-engine",
        choices=("tesseract",),
        default="tesseract",
        help="OCR engine used for scorebug extraction.",
    )
    parser.add_argument(
        "--ocr-sample-frame",
        choices=("start", "mid", "end"),
        default="mid",
        help="Frame position within each segment for OCR sampling.",
    )
    parser.add_argument(
        "--ocr-min-confidence",
        type=float,
        default=0.75,
        help="Minimum confidence threshold for OCR-derived quality_flag=ok.",
    )
    parser.add_argument(
        "--enable-play-art-detection",
        action="store_true",
        help="Detect whether play-art overlays are visible in each clip.",
    )
    parser.add_argument(
        "--play-art-min-confidence",
        type=float,
        default=0.55,
        help="Minimum confidence threshold for play_art_visible=true.",
    )
    parser.add_argument(
        "--show-progress",
        action="store_true",
        help="Print stage progress and elapsed time while processing.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=5,
        help="When showing progress, print every N items (default: 5).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    started_at = time.time()
    args = build_parser().parse_args(argv)
    source_video = str(Path(args.input))
    out_dir = Path(args.out_dir)
    clips_dir = out_dir / "clips"
    jsonl_path = out_dir / "plays.jsonl"
    csv_path = out_dir / "plays_preview.csv"

    if args.show_progress:
        print(f"[{_format_elapsed(started_at)}] Starting segmentation for {source_video}", flush=True)

    duration = probe_duration_seconds(source_video)
    if args.show_progress:
        print(f"[{_format_elapsed(started_at)}] Video duration: {duration:.2f}s", flush=True)
    if args.segmentation_mode == "fixed":
        segments = build_fixed_segments(duration, args.clip_seconds)
    else:
        scene_points = detect_scene_change_times(
            video_path=source_video,
            threshold=args.scene_threshold,
        )
        segments = scene_points_to_segments(
            scene_points=scene_points,
            duration_seconds=duration,
            pre_snap_padding=args.pre_snap_padding,
            post_whistle_padding=args.post_whistle_padding,
            min_play_seconds=args.min_play_seconds,
            max_play_seconds=args.max_play_seconds,
        )
        if not segments:
            segments = build_fixed_segments(duration, args.clip_seconds)
    if args.show_progress:
        print(f"[{_format_elapsed(started_at)}] Segments detected: {len(segments)}", flush=True)

    records = build_play_records(
        game_id=args.game_id,
        source_video=source_video,
        clips_dir=str(clips_dir),
        segments=segments,
    )

    if not args.skip_clips:
        export_clips(
            source_video=source_video,
            clips_dir=str(clips_dir),
            segments=segments,
            progress_callback=_make_progress_callback(
                label="Export clips",
                started_at=started_at,
                show_progress=args.show_progress,
                every=args.progress_every,
            ),
        )

    if args.enable_ocr:
        records = enrich_records_with_ocr(
            records=records,
            source_video=source_video,
            engine=args.ocr_engine,
            sample_frame=args.ocr_sample_frame,
            min_confidence=args.ocr_min_confidence,
            progress_callback=_make_progress_callback(
                label="OCR",
                started_at=started_at,
                show_progress=args.show_progress,
                every=args.progress_every,
            ),
        )

    if args.enable_play_art_detection:
        records = enrich_records_with_play_art(
            records=records,
            source_video=source_video,
            min_confidence=args.play_art_min_confidence,
            progress_callback=_make_progress_callback(
                label="Play-art detection",
                started_at=started_at,
                show_progress=args.show_progress,
                every=args.progress_every,
            ),
        )

    write_jsonl(records, str(jsonl_path))
    write_preview_csv(records, str(csv_path))
    print(
        f"[{_format_elapsed(started_at)}] Wrote {len(records)} plays to {jsonl_path} and {csv_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
