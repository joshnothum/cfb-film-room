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
) -> list[dict]:
    if sample_frame not in {"start", "mid", "end"}:
        raise ValueError("sample_frame must be one of: start, mid, end")

    enriched: list[dict] = []
    for record in records:
        record_copy = dict(record)
        timestamp = _sample_timestamp(record_copy, sample_frame)
        try:
            raw_text = extract_text_at_time(
                video_path=source_video,
                timestamp_sec=timestamp,
                engine=engine,
            )
            parsed = parse_scorebug_text(raw_text)
            for key, value in parsed.items():
                if key.endswith("_confidence"):
                    record_copy[key] = _safe_float(value)
                else:
                    record_copy[key] = value
            record_copy["ocr_raw_text"] = raw_text
            record_copy["ocr_sample_time_sec"] = round(timestamp, 3)
            record_copy["quality_flag"] = _compute_quality_flag(record_copy, min_confidence)
        except (subprocess.SubprocessError, ValueError):
            record_copy["ocr_raw_text"] = None
            record_copy["ocr_sample_time_sec"] = round(timestamp, 3)
            record_copy["quality_flag"] = "needs_review"
        enriched.append(record_copy)
    return enriched
