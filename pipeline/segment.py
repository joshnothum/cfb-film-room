import argparse
import csv
import json
import subprocess
from pathlib import Path


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
                "clock": None,
                "down": None,
                "distance": None,
                "field_position": None,
                "offense_score": None,
                "defense_score": None,
                "offensive_play_id": None,
                "defensive_shell": None,
                "result_type": None,
                "result_yards": None,
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
    return len(segments)


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
        help="Fixed clip length for MVP segmentation (seconds).",
    )
    parser.add_argument(
        "--skip-clips",
        action="store_true",
        help="Write metadata only and skip ffmpeg clip extraction.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_video = str(Path(args.input))
    out_dir = Path(args.out_dir)
    clips_dir = out_dir / "clips"
    jsonl_path = out_dir / "plays.jsonl"
    csv_path = out_dir / "plays_preview.csv"

    duration = probe_duration_seconds(source_video)
    segments = build_fixed_segments(duration, args.clip_seconds)
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
        )

    write_jsonl(records, str(jsonl_path))
    write_preview_csv(records, str(csv_path))
    print(f"Wrote {len(records)} plays to {jsonl_path} and {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
