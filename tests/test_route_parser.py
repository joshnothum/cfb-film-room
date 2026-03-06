from pathlib import Path

import pipeline.route_parser as route_parser
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


def test_parse_routes_from_playart_falls_back_when_yolo_fails(tmp_path: Path, monkeypatch):
    src = tmp_path / "play.jpg"
    _make_sample_playart(src)

    monkeypatch.setenv("CFB_ROUTE_YOLO_MODEL", str(tmp_path / "missing.pt"))

    parsed = parse_routes_from_playart(
        image_path=str(src),
        output_dir=str(tmp_path / "route_parse"),
        detector_backend="auto",
    )

    assert parsed["detector_backend_used"] == "heuristic"
    assert any(flag.startswith("yolo_detector_failed:") for flag in parsed["quality_flags"])
    assert parsed["route_candidates"]


def test_parse_routes_from_playart_uses_yolo_when_available(tmp_path: Path, monkeypatch):
    src = tmp_path / "play.jpg"
    _make_sample_playart(src)

    def _fake_yolo(**kwargs):
        return (
            [
                {
                    "color": "model",
                    "pixel_count": None,
                    "bbox": {"x0": 20, "y0": 20, "x1": 120, "y1": 180},
                    "route_type_candidate": "fade_or_go",
                    "confidence": 0.9,
                    "meta": {"detector_class": "fade_or_go"},
                }
            ],
            ["X"],
            [],
        )

    monkeypatch.setattr(route_parser, "_extract_route_candidates_with_yolo", _fake_yolo)

    parsed = parse_routes_from_playart(
        image_path=str(src),
        output_dir=str(tmp_path / "route_parse"),
        detector_backend="yolo",
        yolo_model_path=str(tmp_path / "dummy.pt"),
    )

    assert parsed["detector_backend_used"] == "yolo"
    assert parsed["assignment_labels"] == ["X"]
    assert parsed["route_candidates"][0]["route_type_candidate"] == "fade_or_go"


def test_parse_routes_from_playart_forced_yolo_requires_model(tmp_path: Path, monkeypatch):
    src = tmp_path / "play.jpg"
    _make_sample_playart(src)
    monkeypatch.delenv("CFB_ROUTE_YOLO_MODEL", raising=False)

    try:
        parse_routes_from_playart(
            image_path=str(src),
            output_dir=str(tmp_path / "route_parse"),
            detector_backend="yolo",
            yolo_model_path=None,
        )
        raise AssertionError("Expected ValueError when forcing yolo without a model path")
    except ValueError as exc:
        assert "requires yolo_model_path" in str(exc)
