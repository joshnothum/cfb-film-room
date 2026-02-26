import re
import subprocess
import tempfile
from pathlib import Path


def _safe_float(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 3)


def extract_text_at_time(
    *,
    video_path: str,
    timestamp_sec: float,
    engine: str = "tesseract",
) -> str:
    if engine != "tesseract":
        raise ValueError(f"Unsupported OCR engine: {engine}")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        frame_path = tmp.name

    try:
        ffmpeg_cmd = [
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
            frame_path,
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)

        tesseract_cmd = ["tesseract", frame_path, "stdout"]
        result = subprocess.run(tesseract_cmd, check=True, capture_output=True, text=True)
        return (result.stdout or "").strip()
    finally:
        Path(frame_path).unlink(missing_ok=True)


def _parse_score_from_text(text: str) -> int | None:
    cleaned = (text or "").strip()
    match = re.search(r"\b(\d{1,2})\b", cleaned)
    if not match:
        return None
    return int(match.group(1))


def _score_read_confidence(text: str, score: int | None) -> float:
    cleaned = (text or "").strip()
    if score is None:
        return 0.0
    if re.fullmatch(r"\d{1,2}", cleaned):
        return 0.98
    if re.search(r"\d", cleaned):
        return 0.75
    return 0.55


def _read_score_from_crop(image_path: str) -> tuple[int | None, str, float]:
    tesseract_cmd = [
        "tesseract",
        image_path,
        "stdout",
        "--psm",
        "7",
        "-c",
        "tessedit_char_whitelist=0123456789",
    ]
    result = subprocess.run(tesseract_cmd, check=True, capture_output=True, text=True)
    text = (result.stdout or "").strip()
    score = _parse_score_from_text(text)
    return score, text, _score_read_confidence(text, score)


def extract_scorebug_scores_at_time(
    *,
    video_path: str,
    timestamp_sec: float,
    engine: str = "tesseract",
) -> dict:
    if engine != "tesseract":
        raise ValueError(f"Unsupported OCR engine: {engine}")

    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise ValueError("Pillow is required for scorebug score extraction") from exc

    with tempfile.TemporaryDirectory() as tmp_dir:
        frame_path = str(Path(tmp_dir) / "frame.png")
        ffmpeg_cmd = [
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
            frame_path,
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)

        image = Image.open(frame_path).convert("L")
        w, h = image.size

        presets = {
            "live": {"x0": 0.18, "x1": 0.82, "y0": 0.84, "y1": 0.995},
            "menu": {"x0": 0.16, "x1": 0.84, "y0": 0.865, "y1": 0.995},
        }

        def _prep(region, out_name: str) -> str:
            # Improve OCR signal on stylized UI text.
            region = ImageOps.autocontrast(region)
            region = region.resize((region.size[0] * 2, region.size[1] * 2))
            region = region.point(lambda p: 255 if p > 150 else 0)
            out_path = str(Path(tmp_dir) / out_name)
            region.save(out_path)
            return out_path

        best = {
            "offense_score": None,
            "defense_score": None,
            "offense_score_confidence": 0.0,
            "defense_score_confidence": 0.0,
            "score_ocr_debug": "",
        }
        best_total = -1.0

        for preset_name, p in presets.items():
            bug = image.crop((int(w * p["x0"]), int(h * p["y0"]), int(w * p["x1"]), int(h * p["y1"])))
            bw, bh = bug.size
            left = bug.crop((0, 0, int(bw * 0.38), bh))
            right = bug.crop((int(bw * 0.62), 0, bw, bh))
            left_path = _prep(left, f"{preset_name}_left_score.png")
            right_path = _prep(right, f"{preset_name}_right_score.png")
            left_score, left_raw, left_conf = _read_score_from_crop(left_path)
            right_score, right_raw, right_conf = _read_score_from_crop(right_path)
            total = left_conf + right_conf
            if total > best_total:
                best_total = total
                best = {
                    "offense_score": left_score,
                    "defense_score": right_score,
                    "offense_score_confidence": round(left_conf, 3),
                    "defense_score_confidence": round(right_conf, 3),
                    "score_ocr_debug": (
                        f"preset={preset_name} ts={timestamp_sec:.2f} "
                        f"left_raw='{left_raw}' right_raw='{right_raw}'"
                    ),
                }

        return best


def _score_sample_times(start: float, end: float) -> list[float]:
    duration = max(0.0, end - start)
    if duration <= 0:
        return [round(start, 3)]
    quarter = duration / 4.0
    return [
        round(start + min(0.15, quarter), 3),
        round(start + quarter, 3),
        round(start + (duration / 2.0), 3),
        round(end - quarter, 3),
        round(max(start, end - min(0.15, quarter)), 3),
    ]


def extract_best_scorebug_scores_for_record(
    *,
    video_path: str,
    start_sec: float,
    end_sec: float,
    engine: str = "tesseract",
) -> dict:
    best = {
        "offense_score": None,
        "defense_score": None,
        "offense_score_confidence": 0.0,
        "defense_score_confidence": 0.0,
        "score_ocr_debug": "",
        "score_sample_time_sec": None,
    }
    best_total = -1.0

    for ts in _score_sample_times(start_sec, end_sec):
        result = extract_scorebug_scores_at_time(
            video_path=video_path,
            timestamp_sec=ts,
            engine=engine,
        )
        total = float(result.get("offense_score_confidence", 0.0)) + float(
            result.get("defense_score_confidence", 0.0)
        )
        if total > best_total:
            best_total = total
            best = dict(result)
            best["score_sample_time_sec"] = ts
    return best


def parse_scorebug_text(text: str) -> dict:
    normalized = " ".join((text or "").upper().split())
    output = {
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
    }

    quarter_match = re.search(r"\b(?:Q([1-4])|([1-4])(?:ST|ND|RD|TH)\b)", normalized)
    if quarter_match:
        quarter = quarter_match.group(1) or quarter_match.group(2)
        output["quarter"] = int(quarter)
        output["quarter_confidence"] = 0.9

    clock_match = re.search(r"\b([0-1]?\d:[0-5]\d)\b", normalized)
    if clock_match:
        output["clock"] = clock_match.group(1)
        output["clock_confidence"] = 0.95

    down_distance_match = re.search(r"\b([1-4])(?:ST|ND|RD|TH)?\s*&\s*(\d{1,2})\b", normalized)
    if down_distance_match:
        output["down"] = int(down_distance_match.group(1))
        output["distance"] = int(down_distance_match.group(2))
        output["down_confidence"] = 0.85
        output["distance_confidence"] = 0.85

    field_pos_match = re.search(r"\b([A-Z]{2,3}\s?\d{1,2})\b", normalized)
    if field_pos_match:
        output["field_position"] = field_pos_match.group(1)
        output["field_position_confidence"] = 0.55

    score_pairs = re.findall(r"\b[A-Z]{2,4}\s+(\d{1,2})\b", normalized)
    if len(score_pairs) >= 2:
        # Scorebug text often includes a field-position token (e.g. "UGA 35")
        # before team scores. Use trailing pairs as the score candidates.
        score_candidates = score_pairs[-2:]
        output["offense_score"] = int(score_candidates[0])
        output["defense_score"] = int(score_candidates[1])
        output["offense_score_confidence"] = 0.7
        output["defense_score_confidence"] = 0.7

    return output


def _sample_timestamp(record: dict, mode: str) -> float:
    start = float(record["start_sec"])
    end = float(record["end_sec"])
    if mode == "start":
        return start
    if mode == "end":
        return max(start, end - 0.1)
    return start + (max(0.0, end - start) / 2.0)


def _compute_quality_flag(record: dict, min_confidence: float) -> str:
    critical_fields = (
        ("quarter", "quarter_confidence"),
        ("clock", "clock_confidence"),
        ("down", "down_confidence"),
        ("distance", "distance_confidence"),
    )
    for field, conf_field in critical_fields:
        if record.get(field) is None:
            return "needs_review"
        conf = record.get(conf_field)
        if conf is None or float(conf) < min_confidence:
            return "needs_review"
    return "ok"


def enrich_records_with_ocr(
    *,
    records: list[dict],
    source_video: str,
    engine: str = "tesseract",
    sample_frame: str = "mid",
    min_confidence: float = 0.75,
    progress_callback=None,
) -> list[dict]:
    if sample_frame not in {"start", "mid", "end"}:
        raise ValueError("sample_frame must be one of: start, mid, end")

    enriched: list[dict] = []
    total = len(records)
    prev_scores: tuple[int, int] | None = None
    for idx, record in enumerate(records, start=1):
        record_copy = dict(record)
        timestamp = _sample_timestamp(record_copy, sample_frame)
        try:
            raw_text = extract_text_at_time(
                video_path=source_video,
                timestamp_sec=timestamp,
                engine=engine,
            )
            parsed = parse_scorebug_text(raw_text)
            score_result = extract_best_scorebug_scores_for_record(
                video_path=source_video,
                start_sec=float(record_copy.get("start_sec", 0.0)),
                end_sec=float(record_copy.get("end_sec", 0.0)),
                engine=engine,
            )
            for key, value in parsed.items():
                if key.endswith("_confidence"):
                    record_copy[key] = _safe_float(value)
                else:
                    record_copy[key] = value
            left = score_result.get("offense_score")
            right = score_result.get("defense_score")
            left_conf = score_result.get("offense_score_confidence")
            right_conf = score_result.get("defense_score_confidence")
            record_copy["score_ocr_debug"] = score_result.get("score_ocr_debug")
            record_copy["score_sample_time_sec"] = score_result.get("score_sample_time_sec")

            if left is not None and right is not None:
                record_copy["offense_score"] = left
                record_copy["defense_score"] = right
                record_copy["offense_score_confidence"] = _safe_float(left_conf)
                record_copy["defense_score_confidence"] = _safe_float(right_conf)
                record_copy["score_imputed_from_previous"] = False
                prev_scores = (int(left), int(right))
            elif prev_scores is not None:
                record_copy["offense_score"] = prev_scores[0]
                record_copy["defense_score"] = prev_scores[1]
                record_copy["offense_score_confidence"] = 0.6
                record_copy["defense_score_confidence"] = 0.6
                record_copy["score_imputed_from_previous"] = True
            record_copy["ocr_raw_text"] = raw_text
            record_copy["ocr_sample_time_sec"] = round(timestamp, 3)
            record_copy["quality_flag"] = _compute_quality_flag(record_copy, min_confidence)
        except (subprocess.SubprocessError, ValueError):
            record_copy["ocr_raw_text"] = None
            record_copy["ocr_sample_time_sec"] = round(timestamp, 3)
            record_copy["quality_flag"] = "needs_review"
            record_copy["score_ocr_debug"] = None
            record_copy["score_sample_time_sec"] = None
            record_copy["score_imputed_from_previous"] = False
        enriched.append(record_copy)
        if progress_callback:
            progress_callback(idx, total)
    return enriched
