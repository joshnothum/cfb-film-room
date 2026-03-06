from pathlib import Path
import subprocess
import tempfile


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


def parse_routes_from_playart(*, image_path: str, output_dir: str | None = None) -> dict:
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is required for route parsing") from exc

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

    hsv = enhanced.convert("HSV")
    ew, eh = enhanced.size

    routes: list[dict] = []
    for color in ("red", "yellow", "blue"):
        points = _mask_pixels(hsv, color)
        route_type, conf, meta = _classify_route_from_geometry(points, ew, eh)
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

    labels = _extract_assignment_labels(enhanced_path)
    quality_flags: list[str] = []
    if not routes:
        quality_flags.append("no_route_candidates_detected")
    if not labels:
        quality_flags.append("assignment_labels_not_detected")

    return {
        "source_image_path": str(source),
        "enhanced_image_path": str(enhanced_path),
        "assignment_labels": labels,
        "route_candidates": routes,
        "quality_flags": quality_flags,
    }
