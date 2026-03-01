import json
from pathlib import Path

import pytest

from scraper import manifest


def _create_sample_playbook(root: Path) -> Path:
    team_dir = root / "playbooks" / "georgia-off"
    formation_dir = team_dir / "gun-bunch"
    formation_dir.mkdir(parents=True)
    (formation_dir / "post-curl.jpg").write_bytes(b"fake-image-bytes")
    return team_dir


def test_build_manifest_records_required_fields(tmp_path: Path):
    _create_sample_playbook(tmp_path)
    records = manifest.build_manifest_records(
        team_slug="georgia-off",
        year=26,
        playbooks_root=str(tmp_path / "playbooks"),
    )

    assert len(records) == 1
    record = records[0]
    expected_keys = {
        "play_id",
        "team_slug",
        "year",
        "formation_slug",
        "play_slug",
        "play_name",
        "playbook_side",
        "team_unit",
        "play_art_path",
        "play_art_url",
        "source_url",
    }

    assert set(record.keys()) == expected_keys
    assert record["team_slug"] == "georgia-off"
    assert record["year"] == 26
    assert record["formation_slug"] == "gun-bunch"
    assert record["play_slug"] == "post-curl"
    assert record["play_name"] == "POST CURL"
    assert record["playbook_side"] == "offense"
    assert record["team_unit"] == "offense"
    assert record["play_art_url"] is None
    assert record["source_url"] == "https://cfb.fan/26/playbooks/georgia-off/gun-bunch/post-curl"
    assert record["play_art_path"].endswith("playbooks/georgia-off/gun-bunch/post-curl.jpg")


def test_build_manifest_records_missing_team_dir_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        manifest.build_manifest_records(
            team_slug="georgia-off",
            playbooks_root=str(tmp_path / "playbooks"),
        )


def test_build_manifest_records_infers_defense_side(tmp_path: Path):
    team_dir = tmp_path / "playbooks" / "georgia-def"
    formation_dir = team_dir / "nickel-over"
    formation_dir.mkdir(parents=True)
    (formation_dir / "cover-3-sky.jpg").write_bytes(b"fake-image-bytes")

    records = manifest.build_manifest_records(
        team_slug="georgia-def",
        year=26,
        playbooks_root=str(tmp_path / "playbooks"),
    )

    assert records[0]["playbook_side"] == "defense"
    assert records[0]["team_unit"] == "defense"


def test_write_jsonl_writes_one_object_per_line(tmp_path: Path):
    records = [
        {"play_id": "a"},
        {"play_id": "b"},
    ]
    out = tmp_path / "manifests" / "playbook_manifest.jsonl"
    count = manifest.write_jsonl(records, str(out))

    assert count == 2
    assert out.exists()

    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"play_id": "a"}
    assert json.loads(lines[1]) == {"play_id": "b"}
