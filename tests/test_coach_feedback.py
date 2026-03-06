import json
import subprocess
import sys
from pathlib import Path

from pipeline import coach_feedback


def _write_manifest(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _sample_feedback() -> dict:
    return {
        "analysis_id": "a",
        "offensive_play": {"play_id": "off"},
        "defensive_play": {"play_id": "def"},
        "audience": "qb_room",
        "grounding_mode": "evidence_first",
        "route_roles": [],
        "qb_progression": {
            "pre_snap_keys": [],
            "post_snap_keys": [],
            "read_order": [],
            "checkdown_rule": "",
        },
        "defense_interpretation": {
            "front_shell_guess": "",
            "coverage_guess": "",
            "pressure_risk": "",
            "confidence": 0.0,
        },
        "coaching_points": [],
        "risk_flags": [],
        "uncertainties": [],
        "summary_text": "ok",
    }


def test_validate_feedback_schema_success():
    errors = coach_feedback.validate_feedback_schema(_sample_feedback())
    assert errors == []


def test_validate_feedback_schema_missing_key_fails():
    payload = _sample_feedback()
    del payload["summary_text"]
    errors = coach_feedback.validate_feedback_schema(payload)
    assert errors
    assert any("Missing keys" in err for err in errors)


def test_domain_soft_guard_warns_for_off_domain_text():
    warning = coach_feedback.get_domain_soft_guard_message("Can you explain my golf swing?")
    assert warning is not None


def test_domain_soft_guard_allows_football_text():
    warning = coach_feedback.get_domain_soft_guard_message("What should QB read pre-snap?")
    assert warning is None


def test_coach_feedback_cli_mock_end_to_end(tmp_path: Path):
    off_image = tmp_path / "off.jpg"
    def_image = tmp_path / "def.jpg"
    off_image.write_bytes(b"\xff\xd8\xff\xd9")
    def_image.write_bytes(b"\xff\xd8\xff\xd9")

    off_manifest = tmp_path / "off_manifest.jsonl"
    def_manifest = tmp_path / "def_manifest.jsonl"

    off_play_id = "georgia-off:26:gun-bunch:flood"
    def_play_id = "georgia-def:26:nickel-over:cover-3-sky"

    _write_manifest(
        off_manifest,
        [
            {
                "play_id": off_play_id,
                "team_slug": "georgia-off",
                "formation_slug": "gun-bunch",
                "play_slug": "flood",
                "play_name": "FLOOD",
                "playbook_side": "offense",
                "team_unit": "offense",
                "play_art_path": str(off_image),
                "play_art_url": None,
                "source_url": "https://cfb.fan/26/playbooks/georgia-off/gun-bunch/flood",
            }
        ],
    )
    _write_manifest(
        def_manifest,
        [
            {
                "play_id": def_play_id,
                "team_slug": "georgia-def",
                "formation_slug": "nickel-over",
                "play_slug": "cover-3-sky",
                "play_name": "COVER 3 SKY",
                "playbook_side": "defense",
                "team_unit": "defense",
                "play_art_path": str(def_image),
                "play_art_url": None,
                "source_url": "https://cfb.fan/26/playbooks/georgia-def/nickel-over/cover-3-sky",
            }
        ],
    )

    out = tmp_path / "analysis.json"

    cmd = [
        sys.executable,
        "scripts/coach_feedback.py",
        "--off-play-id",
        off_play_id,
        "--def-play-id",
        def_play_id,
        "--off-manifest",
        str(off_manifest),
        "--def-manifest",
        str(def_manifest),
        "--provider",
        "mock",
        "--out",
        str(out),
        "--format",
        "both",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr

    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["audience"] == "qb_room"
    assert result["grounding_mode"] == "evidence_first"
    assert result["route_roles"]
    assert result["qb_progression"]["read_order"]
    assert out.with_suffix(".md").exists()


def test_normalize_feedback_clamps_confidence_and_normalizes_read_order():
    offensive_play = {
        "play_id": "off",
        "team_slug": "georgia-off",
        "formation_slug": "gun-bunch",
        "play_name": "FLOOD",
        "play_art_path": "/tmp/off.jpg",
    }
    defensive_play = {
        "play_id": "def",
        "team_slug": "4-2-5-def",
        "formation_slug": "nickel-over",
        "play_name": "COVER 3 SKY",
        "play_art_path": "/tmp/def.jpg",
    }
    raw = {
        "analysis_id": "raw",
        "offensive_play": {},
        "defensive_play": {},
        "audience": "qb_room",
        "grounding_mode": "evidence_first",
        "route_roles": [
            {
                "route_label": "X out",
                "role": "primary",
                "evidence": "sideline stress",
                "confidence": 1.0,
            }
        ],
        "qb_progression": {
            "pre_snap_keys": "Confirm shell",
            "post_snap_keys": ["Read curl/flat"],
            "read_order": "Out route, Flat route. Vertical alert",
            "checkdown_rule": "Take crosser",
        },
        "defense_interpretation": {
            "front_shell_guess": "Nickel",
            "coverage_guess": "Cover 3",
            "pressure_risk": "Low",
            "confidence": 0.99,
        },
        "coaching_points": "Keep eyes disciplined",
        "risk_flags": "sideline trap",
        "uncertainties": [],
        "summary_text": "summary",
    }

    normalized = coach_feedback.normalize_feedback(
        feedback=raw,
        analysis_id="analysis_test",
        offensive_play=offensive_play,
        defensive_play=defensive_play,
        domain_warning=None,
    )

    assert normalized["route_roles"][0]["confidence"] == 0.85
    assert normalized["defense_interpretation"]["confidence"] == 0.85
    assert normalized["qb_progression"]["read_order"] == [
        "Out route",
        "Flat route",
        "Vertical alert",
    ]
    assert normalized["coaching_points"] == ["Keep eyes disciplined"]


def test_coach_feedback_cli_team_scheme_resolution(tmp_path: Path):
    off_image = tmp_path / "off.jpg"
    def_image = tmp_path / "def.jpg"
    off_image.write_bytes(b"\xff\xd8\xff\xd9")
    def_image.write_bytes(b"\xff\xd8\xff\xd9")

    manifests_dir = tmp_path / "manifests"
    off_manifest = manifests_dir / "georgia-off_manifest.jsonl"
    def_manifest = manifests_dir / "3-3-5-tite-def_manifest.jsonl"
    scheme_map = tmp_path / "team_defense_map.json"
    scheme_map.write_text(
        json.dumps({"season": 26, "teams": {"georgia": "3-3-5-tite-def"}}),
        encoding="utf-8",
    )

    _write_manifest(
        off_manifest,
        [
            {
                "play_id": "georgia-off:26:gun-bunch:flood",
                "team_slug": "georgia-off",
                "formation_slug": "gun-bunch",
                "play_slug": "flood",
                "play_name": "FLOOD",
                "playbook_side": "offense",
                "team_unit": "offense",
                "play_art_path": str(off_image),
                "play_art_url": None,
                "source_url": "https://cfb.fan/26/playbooks/georgia-off/gun-bunch/flood",
            }
        ],
    )
    _write_manifest(
        def_manifest,
        [
            {
                "play_id": "3-3-5-tite-def:26:nickel-2-4-load-mug:cover-3-sky",
                "team_slug": "3-3-5-tite-def",
                "formation_slug": "nickel-2-4-load-mug",
                "play_slug": "cover-3-sky",
                "play_name": "COVER 3 SKY",
                "playbook_side": "defense",
                "team_unit": "defense",
                "play_art_path": str(def_image),
                "play_art_url": None,
                "source_url": "https://cfb.fan/26/playbooks/3-3-5-tite-def/nickel-2-4-load-mug/cover-3-sky",
            }
        ],
    )

    out = tmp_path / "analysis_team_resolve.json"
    cmd = [
        sys.executable,
        "scripts/coach_feedback.py",
        "--off-play-id",
        "georgia-off:26:gun-bunch:flood",
        "--def-play-id",
        "georgia:26:nickel-2-4-load-mug:cover-3-sky",
        "--def-team",
        "georgia",
        "--def-scheme-map",
        str(scheme_map),
        "--manifests-dir",
        str(manifests_dir),
        "--off-manifest",
        str(off_manifest),
        "--provider",
        "mock",
        "--out",
        str(out),
        "--format",
        "json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["defensive_play"]["play_id"].startswith("3-3-5-tite-def:")


def test_infer_play_type_run_detection():
    assert coach_feedback.infer_play_type(play_slug="inside_zone", play_name="INSIDE ZONE") == "run"
    assert coach_feedback.infer_play_type(play_slug="mesh_spot", play_name="MESH SPOT") == "pass"


def test_run_play_normalization_uses_run_readout():
    offensive_play = {
        "play_id": "off",
        "team_slug": "georgia-off",
        "formation_slug": "gun-spread-flex-wk",
        "play_slug": "inside_zone",
        "play_name": "INSIDE ZONE",
        "play_art_path": "/tmp/off.jpg",
    }
    defensive_play = {
        "play_id": "def",
        "team_slug": "4-2-5-def",
        "formation_slug": "3-3-5-over-flex",
        "play_slug": "edge-blitz-0",
        "play_name": "EDGE BLITZ 0",
        "play_art_path": "/tmp/def.jpg",
    }
    raw = _sample_feedback()
    raw["qb_progression"]["read_order"] = [
        "Out route first",
        "Flat route second",
    ]
    raw["qb_progression"]["checkdown_rule"] = "Take checkdown vs pressure"

    normalized = coach_feedback.normalize_feedback(
        feedback=raw,
        analysis_id="analysis_test_run",
        offensive_play=offensive_play,
        defensive_play=defensive_play,
        domain_warning=None,
    )

    assert normalized["play_type_hint"] == "run"
    assert "run_concept_mode" in normalized["risk_flags"]
    assert all("route" not in item.lower() for item in normalized["qb_progression"]["read_order"])
    assert "Not a pass checkdown concept" in normalized["qb_progression"]["checkdown_rule"]


def test_generate_coach_feedback_mock_with_playart_features(tmp_path: Path):
    from PIL import Image

    off_image = tmp_path / "off.jpg"
    def_image = tmp_path / "def.jpg"
    Image.new("RGB", (320, 180), color=(20, 100, 20)).save(off_image)
    Image.new("RGB", (320, 180), color=(20, 100, 20)).save(def_image)

    off_manifest = tmp_path / "off_manifest.jsonl"
    def_manifest = tmp_path / "def_manifest.jsonl"
    off_play_id = "georgia-off:26:gun-bunch:flood"
    def_play_id = "3-3-5-tite-def:26:nickel-2-4-load-mug:cover-3-sky"

    _write_manifest(
        off_manifest,
        [
            {
                "play_id": off_play_id,
                "team_slug": "georgia-off",
                "formation_slug": "gun-bunch",
                "play_slug": "flood",
                "play_name": "FLOOD",
                "playbook_side": "offense",
                "team_unit": "offense",
                "play_art_path": str(off_image),
                "play_art_url": None,
                "source_url": "https://cfb.fan/26/playbooks/georgia-off/gun-bunch/flood",
            }
        ],
    )
    _write_manifest(
        def_manifest,
        [
            {
                "play_id": def_play_id,
                "team_slug": "3-3-5-tite-def",
                "formation_slug": "nickel-2-4-load-mug",
                "play_slug": "cover-3-sky",
                "play_name": "COVER 3 SKY",
                "playbook_side": "defense",
                "team_unit": "defense",
                "play_art_path": str(def_image),
                "play_art_url": None,
                "source_url": "https://cfb.fan/26/playbooks/3-3-5-tite-def/nickel-2-4-load-mug/cover-3-sky",
            }
        ],
    )

    result = coach_feedback.generate_coach_feedback(
        off_play_id=off_play_id,
        def_play_id=def_play_id,
        off_manifest_path=str(off_manifest),
        def_manifest_path=str(def_manifest),
        provider_name="mock",
        enable_playart_features=True,
        playart_features_dir=str(tmp_path / "features"),
    )

    assert "playart_features" in result
    assert "offense" in result["playart_features"]


def test_route_lock_overrides_route_roles(tmp_path: Path):
    off_image = tmp_path / "off.jpg"
    def_image = tmp_path / "def.jpg"
    off_image.write_bytes(b"\xff\xd8\xff\xd9")
    def_image.write_bytes(b"\xff\xd8\xff\xd9")

    off_manifest = tmp_path / "off_manifest.jsonl"
    def_manifest = tmp_path / "def_manifest.jsonl"
    off_play_id = "georgia-off:26:gun-bunch:flood"
    def_play_id = "3-3-5-tite-def:26:nickel-2-4-load-mug:cover-3-sky"

    _write_manifest(
        off_manifest,
        [
            {
                "play_id": off_play_id,
                "team_slug": "georgia-off",
                "formation_slug": "gun-bunch",
                "play_slug": "flood",
                "play_name": "FLOOD",
                "playbook_side": "offense",
                "team_unit": "offense",
                "play_art_path": str(off_image),
                "play_art_url": None,
                "source_url": "https://cfb.fan/26/playbooks/georgia-off/gun-bunch/flood",
            }
        ],
    )
    _write_manifest(
        def_manifest,
        [
            {
                "play_id": def_play_id,
                "team_slug": "3-3-5-tite-def",
                "formation_slug": "nickel-2-4-load-mug",
                "play_slug": "cover-3-sky",
                "play_name": "COVER 3 SKY",
                "playbook_side": "defense",
                "team_unit": "defense",
                "play_art_path": str(def_image),
                "play_art_url": None,
                "source_url": "https://cfb.fan/26/playbooks/3-3-5-tite-def/nickel-2-4-load-mug/cover-3-sky",
            }
        ],
    )
    route_locks = tmp_path / "route_locks.json"
    route_locks.write_text(
        json.dumps(
            {
                "plays": {
                    off_play_id: {
                        "route_roles": [
                            {
                                "route_label": "X 10-yard in",
                                "role": "primary",
                                "evidence": "Coach-locked",
                                "confidence": 0.85,
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = coach_feedback.generate_coach_feedback(
        off_play_id=off_play_id,
        def_play_id=def_play_id,
        off_manifest_path=str(off_manifest),
        def_manifest_path=str(def_manifest),
        provider_name="mock",
        route_locks_path=str(route_locks),
    )

    assert result["route_roles_source"] == "coach_locked"
    assert result["route_roles"][0]["route_label"] == "X 10-yard in"


def test_generate_coach_feedback_mock_with_route_parser(tmp_path: Path):
    from PIL import Image, ImageDraw

    off_image = tmp_path / "off.jpg"
    def_image = tmp_path / "def.jpg"

    off_canvas = Image.new("RGB", (640, 360), color=(20, 100, 20))
    draw = ImageDraw.Draw(off_canvas)
    draw.line([(80, 300), (220, 220), (280, 220)], fill=(255, 0, 0), width=5)
    draw.line([(120, 320), (120, 180)], fill=(255, 255, 0), width=5)
    draw.line([(180, 320), (320, 200)], fill=(0, 120, 255), width=5)
    off_canvas.save(off_image)

    Image.new("RGB", (320, 180), color=(20, 100, 20)).save(def_image)

    off_manifest = tmp_path / "off_manifest.jsonl"
    def_manifest = tmp_path / "def_manifest.jsonl"
    off_play_id = "georgia-off:26:gun-bunch:flood"
    def_play_id = "3-3-5-tite-def:26:nickel-2-4-load-mug:cover-3-sky"

    _write_manifest(
        off_manifest,
        [
            {
                "play_id": off_play_id,
                "team_slug": "georgia-off",
                "formation_slug": "gun-bunch",
                "play_slug": "flood",
                "play_name": "FLOOD",
                "playbook_side": "offense",
                "team_unit": "offense",
                "play_art_path": str(off_image),
                "play_art_url": None,
                "source_url": "https://cfb.fan/26/playbooks/georgia-off/gun-bunch/flood",
            }
        ],
    )
    _write_manifest(
        def_manifest,
        [
            {
                "play_id": def_play_id,
                "team_slug": "3-3-5-tite-def",
                "formation_slug": "nickel-2-4-load-mug",
                "play_slug": "cover-3-sky",
                "play_name": "COVER 3 SKY",
                "playbook_side": "defense",
                "team_unit": "defense",
                "play_art_path": str(def_image),
                "play_art_url": None,
                "source_url": "https://cfb.fan/26/playbooks/3-3-5-tite-def/nickel-2-4-load-mug/cover-3-sky",
            }
        ],
    )

    result = coach_feedback.generate_coach_feedback(
        off_play_id=off_play_id,
        def_play_id=def_play_id,
        off_manifest_path=str(off_manifest),
        def_manifest_path=str(def_manifest),
        provider_name="mock",
        enable_route_parser=True,
        route_parser_dir=str(tmp_path / "route_parser"),
    )

    assert "route_parse_hints" in result
    assert result["route_parse_hints"]["route_candidates"]


def test_route_parser_preferred_adds_metadata(tmp_path: Path):
    from PIL import Image, ImageDraw

    off_image = tmp_path / "off.jpg"
    def_image = tmp_path / "def.jpg"

    off_canvas = Image.new("RGB", (640, 360), color=(20, 100, 20))
    draw = ImageDraw.Draw(off_canvas)
    draw.line([(80, 300), (220, 220), (280, 220)], fill=(255, 0, 0), width=5)
    draw.line([(120, 320), (120, 180)], fill=(255, 255, 0), width=5)
    draw.line([(180, 320), (320, 200)], fill=(0, 120, 255), width=5)
    off_canvas.save(off_image)

    Image.new("RGB", (320, 180), color=(20, 100, 20)).save(def_image)

    off_manifest = tmp_path / "off_manifest.jsonl"
    def_manifest = tmp_path / "def_manifest.jsonl"
    off_play_id = "georgia-off:26:gun-bunch:flood"
    def_play_id = "3-3-5-tite-def:26:nickel-2-4-load-mug:cover-3-sky"

    _write_manifest(
        off_manifest,
        [
            {
                "play_id": off_play_id,
                "team_slug": "georgia-off",
                "formation_slug": "gun-bunch",
                "play_slug": "flood",
                "play_name": "FLOOD",
                "playbook_side": "offense",
                "team_unit": "offense",
                "play_art_path": str(off_image),
                "play_art_url": None,
                "source_url": "https://cfb.fan/26/playbooks/georgia-off/gun-bunch/flood",
            }
        ],
    )
    _write_manifest(
        def_manifest,
        [
            {
                "play_id": def_play_id,
                "team_slug": "3-3-5-tite-def",
                "formation_slug": "nickel-2-4-load-mug",
                "play_slug": "cover-3-sky",
                "play_name": "COVER 3 SKY",
                "playbook_side": "defense",
                "team_unit": "defense",
                "play_art_path": str(def_image),
                "play_art_url": None,
                "source_url": "https://cfb.fan/26/playbooks/3-3-5-tite-def/nickel-2-4-load-mug/cover-3-sky",
            }
        ],
    )

    result = coach_feedback.generate_coach_feedback(
        off_play_id=off_play_id,
        def_play_id=def_play_id,
        off_manifest_path=str(off_manifest),
        def_manifest_path=str(def_manifest),
        provider_name="mock",
        enable_route_parser=True,
        route_parser_preferred=True,
        route_parser_dir=str(tmp_path / "route_parser"),
    )

    assert result["route_parser_preferred"] is True
    assert "route_roles_parser_basis" in result
    assert "route_parser_preferred_mode" in result["risk_flags"]
