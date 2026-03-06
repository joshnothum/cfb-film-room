#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.route_eval import build_prediction_row
from pipeline.route_gold import build_route_gold_template_rows, load_jsonl, write_jsonl
from pipeline.route_parser import parse_routes_from_playart


def _build_seed_predictions(
    rows: list[dict],
    route_parser_dir: str | None,
    route_detector_backend: str,
    route_yolo_model: str | None,
    route_yolo_confidence: float,
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        play_id = str(row.get("play_id") or "")
        play_art_path = row.get("play_art_path")
        if not play_id or not play_art_path:
            continue
        try:
            parsed = parse_routes_from_playart(
                image_path=str(play_art_path),
                output_dir=route_parser_dir,
                detector_backend=route_detector_backend,
                yolo_model_path=route_yolo_model,
                yolo_confidence=route_yolo_confidence,
            )
        except (FileNotFoundError, RuntimeError):
            continue
        out[play_id] = build_prediction_row(row=row, parse_result=parsed)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a route-recognition gold JSONL from a play-art manifest."
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to manifest JSONL containing play_id + play_art_path.",
    )
    parser.add_argument(
        "--out",
        default="data/qa/route_gold.jsonl",
        help="Destination path for scaffolded route gold labels.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional number of rows to include.")
    parser.add_argument(
        "--offense-only",
        action="store_true",
        help="Include only rows where playbook_side is offense.",
    )
    parser.add_argument(
        "--seed-with-predictions",
        action="store_true",
        help="Pre-fill route fields from current heuristic parser output.",
    )
    parser.add_argument(
        "--route-parser-dir",
        default=None,
        help="Optional directory to store parser debug artifacts when seeding.",
    )
    parser.add_argument(
        "--route-detector-backend",
        choices=("auto", "heuristic", "yolo"),
        default="auto",
        help="Route detector backend for seeded predictions.",
    )
    parser.add_argument(
        "--route-yolo-model",
        default=None,
        help="Path to YOLO model weights for route detection backend.",
    )
    parser.add_argument(
        "--route-yolo-confidence",
        type=float,
        default=0.25,
        help="Confidence threshold for YOLO route detector.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite destination file if it exists.",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    if out_path.exists() and not args.overwrite:
        print(f"Refusing to overwrite existing file: {out_path}")
        print("Re-run with --overwrite if you want to replace it.")
        return 1

    rows = load_jsonl(args.manifest)
    if args.offense_only:
        rows = [row for row in rows if str(row.get("playbook_side") or "").lower() == "offense"]
    if args.limit is not None:
        rows = rows[: args.limit]

    predicted_by_play_id = {}
    if args.seed_with_predictions:
        predicted_by_play_id = _build_seed_predictions(
            rows,
            route_parser_dir=args.route_parser_dir,
            route_detector_backend=args.route_detector_backend,
            route_yolo_model=args.route_yolo_model,
            route_yolo_confidence=args.route_yolo_confidence,
        )

    scaffold = build_route_gold_template_rows(
        manifest_rows=rows,
        include_predicted_values=args.seed_with_predictions,
        predicted_by_play_id=predicted_by_play_id,
    )
    write_jsonl(out_path, scaffold)
    print(f"Wrote {len(scaffold)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
