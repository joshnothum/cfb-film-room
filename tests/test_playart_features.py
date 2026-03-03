from pathlib import Path

from PIL import Image, ImageDraw

from pipeline.playart_features import build_playart_feature_bundle, build_playart_feature_record


def _make_sample_playart(path: Path) -> None:
    img = Image.new("RGB", (640, 360), color=(20, 100, 20))
    draw = ImageDraw.Draw(img)
    draw.line([(80, 300), (220, 220), (280, 220)], fill=(255, 0, 0), width=4)
    draw.line([(120, 320), (120, 180)], fill=(255, 255, 0), width=4)
    draw.line([(180, 320), (320, 200)], fill=(0, 120, 255), width=4)
    img.save(path)


def test_build_playart_feature_record_outputs_enhanced_image(tmp_path: Path):
    src = tmp_path / "play.jpg"
    _make_sample_playart(src)

    record = build_playart_feature_record(
        image_path=str(src),
        output_dir=str(tmp_path / "features"),
        side="offense",
    )

    assert Path(record["enhanced_image_path"]).exists()
    assert set(record["color_density"].keys()) == {"red", "yellow", "blue"}


def test_build_playart_feature_bundle_returns_two_sides(tmp_path: Path):
    off = tmp_path / "off.jpg"
    deff = tmp_path / "def.jpg"
    _make_sample_playart(off)
    _make_sample_playart(deff)

    bundle = build_playart_feature_bundle(
        offensive_image_path=str(off),
        defensive_image_path=str(deff),
        output_dir=str(tmp_path / "bundle"),
    )

    assert "offense" in bundle
    assert "defense" in bundle
    assert Path(bundle["offense"]["enhanced_image_path"]).exists()
    assert Path(bundle["defense"]["enhanced_image_path"]).exists()
