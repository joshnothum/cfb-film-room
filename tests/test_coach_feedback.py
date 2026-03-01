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
