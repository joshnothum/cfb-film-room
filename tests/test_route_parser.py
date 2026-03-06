from pathlib import Path

from PIL import Image, ImageDraw

from pipeline.route_parser import parse_routes_from_playart


def _make_sample_playart(path: Path) -> None:
    img = Image.new("RGB", (640, 360), color=(20, 100, 20))
    draw = ImageDraw.Draw(img)
    draw.line([(80, 300), (220, 220), (280, 220)], fill=(255, 0, 0), width=5)
    draw.line([(120, 320), (120, 180)], fill=(255, 255, 0), width=5)
    draw.line([(180, 320), (320, 200)], fill=(0, 120, 255), width=5)
    img.save(path)


def test_parse_routes_from_playart_returns_candidates(tmp_path: Path):
    src = tmp_path / "play.jpg"
    _make_sample_playart(src)

    parsed = parse_routes_from_playart(
        image_path=str(src),
        output_dir=str(tmp_path / "route_parse"),
    )

    assert Path(parsed["enhanced_image_path"]).exists()
    assert isinstance(parsed["route_candidates"], list)
    assert parsed["route_candidates"]
