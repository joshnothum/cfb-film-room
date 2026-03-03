import subprocess
import tempfile
from pathlib import Path


def _route_color_density(image) -> dict:
    hsv = image.convert("HSV")
    width, height = hsv.size

    # Focus on field region where route overlays appear most often.
    x0, x1 = int(width * 0.10), int(width * 0.90)
    y0, y1 = int(height * 0.18), int(height * 0.86)

    total = max(1, (x1 - x0) * (y1 - y0))
    red = 0
    yellow = 0
    blue = 0

    for y in range(y0, y1):
        for x in range(x0, x1):
            h, s, v = hsv.getpixel((x, y))
            if s < 90 or v < 65:
                continue
            if h <= 8 or h >= 245:
                red += 1
            elif 18 <= h <= 40:
                yellow += 1
            elif 132 <= h <= 185:
                blue += 1

    return {
        "red": round(red / total, 4),
        "yellow": round(yellow / total, 4),
        "blue": round(blue / total, 4),
    }


def _extract_assignment_labels(image_path: Path) -> list[str]:
    # Best-effort only: keep pipeline working if tesseract is unavailable.
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


def build_playart_feature_record(
    *,
    image_path: str,
    output_dir: str | None = None,
    side: str,
) -> dict:
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is required for play-art feature extraction") from exc

    source = Path(image_path)
    if not source.exists():
        raise FileNotFoundError(f"Play art image not found: {image_path}")

    if output_dir:
        out_root = Path(output_dir)
        out_root.mkdir(parents=True, exist_ok=True)
    else:
        out_root = Path(tempfile.mkdtemp(prefix="playart_features_"))

    image = Image.open(source).convert("RGB")
    width, height = image.size

    # Crop out bottom UI strip to emphasize play diagram area.
    cropped = image.crop((0, int(height * 0.05), width, int(height * 0.90)))
    enhanced = ImageOps.autocontrast(cropped)
    enhanced = ImageEnhance.Color(enhanced).enhance(1.15)
    enhanced = ImageEnhance.Contrast(enhanced).enhance(1.2)
    enhanced = enhanced.filter(ImageFilter.SHARPEN)

    enhanced_path = out_root / f"{side}_enhanced_{source.stem}.png"
    enhanced.save(enhanced_path)

    densities = _route_color_density(enhanced)
    assignment_labels = _extract_assignment_labels(enhanced_path)

    quality_flags: list[str] = []
    if sum(densities.values()) < 0.002:
        quality_flags.append("low_route_overlay_signal")
    if not assignment_labels:
        quality_flags.append("assignment_labels_not_detected")

    return {
        "source_image_path": str(source),
        "enhanced_image_path": str(enhanced_path),
        "color_density": densities,
        "assignment_labels": assignment_labels,
        "quality_flags": quality_flags,
    }


def build_playart_feature_bundle(
    *,
    offensive_image_path: str,
    defensive_image_path: str,
    output_dir: str | None = None,
) -> dict:
    offense = build_playart_feature_record(
        image_path=offensive_image_path,
        output_dir=output_dir,
        side="offense",
    )
    defense = build_playart_feature_record(
        image_path=defensive_image_path,
        output_dir=output_dir,
        side="defense",
    )
    return {
        "offense": offense,
        "defense": defense,
    }
