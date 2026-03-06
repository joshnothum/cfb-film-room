import os
from pathlib import Path
import subprocess
import tempfile

_YOLO_MODEL_CACHE: dict[str, object] = {}


def _mask_pixels(hsv_image, color: str) -> list[tuple[int, int]]:
    width, height = hsv_image.size
    pts: list[tuple[int, int]] = []
    for y in range(height):
        for x in range(width):
            h, s, v = hsv_image.getpixel((x, y))
            if s < 85 or v < 60:
                continue
            if color == "red" and (h <= 8 or h >= 245):
                pts.append((x, y))
            elif color == "yellow" and 18 <= h <= 40:
                pts.append((x, y))
            elif color == "blue" and 132 <= h <= 185:
                pts.append((x, y))
    return pts


def _classify_route_from_geometry(points: list[tuple[int, int]], width: int, height: int) -> tuple[str, float, dict]:
    if len(points) < 120:
        return "unknown", 0.35, {"reason": "low_pixel_count"}

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max_x - min_x
    span_y = max_y - min_y

    horizontal_ratio = span_x / max(1, width)
    vertical_ratio = span_y / max(1, height)

    # Heuristics from shape proportions.
    if vertical_ratio > 0.35 and horizontal_ratio < 0.10:
        return "fade_or_go", 0.75, {"span_x": span_x, "span_y": span_y}
    if horizontal_ratio > 0.22 and vertical_ratio < 0.14:
        return "flat_or_hitch", 0.7, {"span_x": span_x, "span_y": span_y}
    if horizontal_ratio > 0.20 and vertical_ratio > 0.20:
        return "cross_or_over", 0.68, {"span_x": span_x, "span_y": span_y}
    if vertical_ratio > 0.20 and horizontal_ratio > 0.10:
        return "in_or_out_break", 0.64, {"span_x": span_x, "span_y": span_y}

    return "unknown", 0.45, {"span_x": span_x, "span_y": span_y}


def _classify_route_from_bbox(
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    width: int,
    height: int,
) -> tuple[str, dict]:
    span_x = max(0, x1 - x0)
    span_y = max(0, y1 - y0)
    horizontal_ratio = span_x / max(1, width)
    vertical_ratio = span_y / max(1, height)

    if vertical_ratio > 0.35 and horizontal_ratio < 0.10:
        return "fade_or_go", {"span_x": span_x, "span_y": span_y}
    if horizontal_ratio > 0.22 and vertical_ratio < 0.14:
        return "flat_or_hitch", {"span_x": span_x, "span_y": span_y}
    if horizontal_ratio > 0.20 and vertical_ratio > 0.20:
        return "cross_or_over", {"span_x": span_x, "span_y": span_y}
    if vertical_ratio > 0.20 and horizontal_ratio > 0.10:
        return "in_or_out_break", {"span_x": span_x, "span_y": span_y}
    return "unknown", {"span_x": span_x, "span_y": span_y}


def _normalize_detector_class(name: str | None) -> str:
    return str(name or "").strip().lower().replace("-", "_").replace(" ", "_")


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _looks_like_label_class(class_name: str) -> bool:
    if class_name in {"x", "y", "a", "b", "rb"}:
        return True
    if "assignment" in class_name or "label" in class_name:
        return True
    return False


def _route_family_from_class_name(class_name: str) -> str | None:
    aliases = {
        "go": "fade_or_go",
        "fade": "fade_or_go",
        "fade_or_go": "fade_or_go",
        "flat": "flat_or_hitch",
        "hitch": "flat_or_hitch",
        "flat_or_hitch": "flat_or_hitch",
        "cross": "cross_or_over",
        "over": "cross_or_over",
        "cross_or_over": "cross_or_over",
        "in": "in_or_out_break",
        "out": "in_or_out_break",
        "in_or_out_break": "in_or_out_break",
    }
    return aliases.get(class_name)


def _load_yolo_model(model_path: str):
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("ultralytics is required for YOLO route detection") from exc

    model_file = Path(model_path).expanduser()
    if not model_file.exists():
        raise FileNotFoundError(f"YOLO model not found: {model_path}")
    cache_key = str(model_file.resolve())
    model = _YOLO_MODEL_CACHE.get(cache_key)
    if model is None:
        model = YOLO(cache_key)
        _YOLO_MODEL_CACHE[cache_key] = model
    return model


def _extract_route_candidates_with_yolo(
    *,
    image_path: Path,
    model_path: str,
    confidence: float,
    width: int,
    height: int,
) -> tuple[list[dict], list[str], list[str]]:
    model = _load_yolo_model(model_path)
    predictions = model.predict(source=str(image_path), conf=confidence, verbose=False)

    routes: list[dict] = []
    labels: list[str] = []
    quality_flags: list[str] = []

    for pred in predictions:
        boxes = getattr(pred, "boxes", None)
        if boxes is None:
            continue

        names = getattr(pred, "names", {}) or {}
        for idx in range(len(boxes)):
            x0f, y0f, x1f, y1f = boxes.xyxy[idx].tolist()
            x0 = max(0, int(round(x0f)))
            y0 = max(0, int(round(y0f)))
            x1 = min(width - 1, int(round(x1f)))
            y1 = min(height - 1, int(round(y1f)))
            conf = float(boxes.conf[idx].item())
            cls_idx = int(boxes.cls[idx].item())
            if isinstance(names, dict):
                raw_name = names.get(cls_idx, f"class_{cls_idx}")
            else:
                raw_name = names[cls_idx] if cls_idx < len(names) else f"class_{cls_idx}"
            class_name = _normalize_detector_class(raw_name)

            if _looks_like_label_class(class_name):
                token = class_name.upper()
                if token in {"X", "Y", "A", "B", "RB"}:
                    labels.append(token)
                continue

            route_family = _route_family_from_class_name(class_name)
            route_meta: dict = {"detector_class": class_name}
            if route_family is None:
                # Only treat detector outputs that look route-related as route candidates.
                if "route" not in class_name:
                    continue
                route_family, bbox_meta = _classify_route_from_bbox(
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                    width=width,
                    height=height,
                )
                route_meta.update(bbox_meta)
                if route_family == "unknown":
                    continue
            elif "route" in class_name:
                route_meta["from_class"] = True

            routes.append(
                {
                    "color": "model",
                    "pixel_count": None,
                    "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                    "route_type_candidate": route_family,
                    "confidence": round(conf, 2),
                    "meta": route_meta,
                }
            )

    if not routes:
        quality_flags.append("no_route_candidates_detected")
    return routes, _dedupe_preserve_order(labels), quality_flags


def _extract_assignment_labels(image_path: Path) -> list[str]:
    cmd = [
        "tesseract",
        str(image_path),
        "stdout",
        "--psm",
        "11",
        "-c",
        "tessedit_char_whitelist=XYABRBTN0123456789",
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.SubprocessError):
        return []

    tokens = (result.stdout or "").upper().replace("\n", " ").split()
    valid = {"X", "Y", "A", "B", "RB"}
    out: list[str] = []
    for token in tokens:
        normalized = token.strip(".,:;()[]{}")
        if normalized in valid and normalized not in out:
            out.append(normalized)
    return out


def _extract_route_candidates_with_heuristics(enhanced_image) -> list[dict]:
    hsv = enhanced_image.convert("HSV")
    width, height = enhanced_image.size

    routes: list[dict] = []
    for color in ("red", "yellow", "blue"):
        points = _mask_pixels(hsv, color)
        route_type, conf, meta = _classify_route_from_geometry(points, width, height)
        if len(points) < 120:
            continue
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        routes.append(
            {
                "color": color,
                "pixel_count": len(points),
                "bbox": {
                    "x0": min(xs),
                    "y0": min(ys),
                    "x1": max(xs),
                    "y1": max(ys),
                },
                "route_type_candidate": route_type,
                "confidence": round(conf, 2),
                "meta": meta,
            }
        )
    return routes


def parse_routes_from_playart(
    *,
    image_path: str,
    output_dir: str | None = None,
    detector_backend: str = "auto",
    yolo_model_path: str | None = None,
    yolo_confidence: float = 0.25,
) -> dict:
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is required for route parsing") from exc

    if detector_backend not in {"auto", "heuristic", "yolo"}:
        raise ValueError("detector_backend must be one of: auto, heuristic, yolo")

    source = Path(image_path)
    if not source.exists():
        raise FileNotFoundError(f"Play art image not found: {image_path}")

    if output_dir:
        out_root = Path(output_dir)
        out_root.mkdir(parents=True, exist_ok=True)
    else:
        out_root = Path(tempfile.mkdtemp(prefix="route_parser_"))

    base = Image.open(source).convert("RGB")
    width, height = base.size
    cropped = base.crop((0, int(height * 0.05), width, int(height * 0.90)))
    enhanced = ImageOps.autocontrast(cropped)
    enhanced = ImageEnhance.Color(enhanced).enhance(1.2)
    enhanced = ImageEnhance.Contrast(enhanced).enhance(1.25)
    enhanced = enhanced.filter(ImageFilter.SHARPEN)

    enhanced_path = out_root / f"routes_enhanced_{source.stem}.png"
    enhanced.save(enhanced_path)
    ew, eh = enhanced.size
    configured_model = yolo_model_path or os.getenv("CFB_ROUTE_YOLO_MODEL")
    if detector_backend == "yolo" and not configured_model:
        raise ValueError(
            "detector_backend='yolo' requires yolo_model_path or CFB_ROUTE_YOLO_MODEL"
        )

    routes: list[dict] = []
    labels: list[str] = []
    quality_flags: list[str] = []
    detector_backend_used = "heuristic"

    use_yolo = detector_backend == "yolo" or (detector_backend == "auto" and configured_model)
    if use_yolo and configured_model:
        try:
            routes, labels, yolo_flags = _extract_route_candidates_with_yolo(
                image_path=enhanced_path,
                model_path=configured_model,
                confidence=yolo_confidence,
                width=ew,
                height=eh,
            )
            quality_flags.extend(yolo_flags)
            detector_backend_used = "yolo"
        except (RuntimeError, FileNotFoundError, ValueError) as exc:
            quality_flags.append(f"yolo_detector_failed:{type(exc).__name__}")
            if detector_backend == "yolo":
                quality_flags.append("forced_yolo_mode_fallback_to_heuristic")

    if not routes:
        routes = _extract_route_candidates_with_heuristics(enhanced)
        detector_backend_used = "heuristic"
        if not routes and "no_route_candidates_detected" not in quality_flags:
            quality_flags.append("no_route_candidates_detected")

    if not labels:
        labels = _extract_assignment_labels(enhanced_path)
    labels = _dedupe_preserve_order(labels)
    if not labels:
        quality_flags.append("assignment_labels_not_detected")

    return {
        "source_image_path": str(source),
        "enhanced_image_path": str(enhanced_path),
        "assignment_labels": labels,
        "route_candidates": routes,
        "detector_backend_used": detector_backend_used,
        "yolo_model_path": configured_model if detector_backend_used == "yolo" else None,
        "quality_flags": quality_flags,
    }
