import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pipeline.kb import KBConfig, retrieve_context
from pipeline.providers import OllamaProvider, OpenAIProvider

REQUIRED_TOP_LEVEL_KEYS = {
    "analysis_id",
    "offensive_play",
    "defensive_play",
    "audience",
    "grounding_mode",
    "route_roles",
    "qb_progression",
    "defense_interpretation",
    "coaching_points",
    "risk_flags",
    "uncertainties",
    "summary_text",
}

FOOTBALL_TERMS = {
    "football",
    "offense",
    "defense",
    "quarterback",
    "qb",
    "coverage",
    "route",
    "play",
    "blitz",
    "read",
    "formation",
}


class CoachFeedbackError(RuntimeError):
    pass


def load_manifest_rows(path: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    with file_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            play_id = row.get("play_id")
            if not play_id:
                raise ValueError(f"{path}:{line_no} missing play_id")
            rows[str(play_id)] = row
    return rows


def resolve_play(play_id: str, manifest_rows: dict[str, dict], side: str) -> dict:
    record = manifest_rows.get(play_id)
    if record is None:
        raise KeyError(f"{side} play_id not found in manifest: {play_id}")

    resolved = {
        "play_id": record.get("play_id"),
        "team_slug": record.get("team_slug"),
        "formation_slug": record.get("formation_slug"),
        "play_slug": record.get("play_slug"),
        "play_name": record.get("play_name"),
        "play_art_path": record.get("play_art_path"),
        "play_art_url": record.get("play_art_url"),
        "source_url": record.get("source_url"),
        "playbook_side": record.get("playbook_side") or side,
        "team_unit": record.get("team_unit") or side,
    }

    image_path = Path(str(resolved["play_art_path"]))
    if not image_path.exists():
        raise FileNotFoundError(f"Play art path does not exist: {image_path}")
    return resolved


def build_analysis_id(off_play_id: str, def_play_id: str) -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha1(f"{off_play_id}|{def_play_id}".encode("utf-8")).hexdigest()[:10]
    return f"analysis_{stamp}_{digest}"


def get_domain_soft_guard_message(user_prompt: str) -> str | None:
    prompt = (user_prompt or "").strip().lower()
    if not prompt:
        return None
    if any(term in prompt for term in FOOTBALL_TERMS):
        return None
    return (
        "Domain warning: your request appears outside football strategy. "
        "This assistant is optimized for football film and play-design analysis."
    )


def _build_system_prompt(audience: str, grounding_mode: str) -> str:
    schema_text = (
        "Return strict JSON only with keys: "
        "analysis_id, offensive_play, defensive_play, audience, grounding_mode, "
        "route_roles, qb_progression, defense_interpretation, coaching_points, "
        "risk_flags, uncertainties, summary_text."
    )
    rules_text = (
        "Evidence-first: only claim route intent supported by visual evidence. "
        "If uncertain, populate uncertainties and lower confidence. "
        "Prioritize QB read progression and defensive indicators."
    )
    return f"You are a football coach assistant for a {audience} audience. {schema_text} {rules_text} Grounding mode: {grounding_mode}."


def _build_user_prompt(
    offensive_play: dict,
    defensive_play: dict,
    *,
    user_prompt: str,
    kb_context: list[dict],
) -> str:
    prompt = {
        "task": "Analyze this offense vs defense play pair and produce coaching feedback.",
        "offensive_play": {
            "play_id": offensive_play["play_id"],
            "team_slug": offensive_play["team_slug"],
            "formation_slug": offensive_play["formation_slug"],
            "play_name": offensive_play["play_name"],
        },
        "defensive_play": {
            "play_id": defensive_play["play_id"],
            "team_slug": defensive_play["team_slug"],
            "formation_slug": defensive_play["formation_slug"],
            "play_name": defensive_play["play_name"],
        },
        "user_prompt": user_prompt or "",
        "kb_context": kb_context,
        "schema_notes": {
            "route_roles": "Array of objects with route_label, role(primary|secondary|tertiary|decoy), evidence, confidence(0-1).",
            "qb_progression": "Object with pre_snap_keys, post_snap_keys, read_order, checkdown_rule.",
            "defense_interpretation": "Object with front_shell_guess, coverage_guess, pressure_risk, confidence(0-1).",
        },
    }
    return json.dumps(prompt, ensure_ascii=False)


def validate_feedback_schema(feedback: dict) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_TOP_LEVEL_KEYS - set(feedback.keys())
    if missing:
        errors.append(f"Missing keys: {sorted(missing)}")

    if feedback.get("audience") != "qb_room":
        errors.append("audience must be 'qb_room'")

    if feedback.get("grounding_mode") != "evidence_first":
        errors.append("grounding_mode must be 'evidence_first'")

    for list_key in ("route_roles", "coaching_points", "risk_flags", "uncertainties"):
        if not isinstance(feedback.get(list_key), list):
            errors.append(f"{list_key} must be a list")

    if not isinstance(feedback.get("qb_progression"), dict):
        errors.append("qb_progression must be an object")
    else:
        qp = feedback["qb_progression"]
        for key in ("pre_snap_keys", "post_snap_keys", "read_order", "checkdown_rule"):
            if key not in qp:
                errors.append(f"qb_progression missing key: {key}")

    if not isinstance(feedback.get("defense_interpretation"), dict):
        errors.append("defense_interpretation must be an object")
    else:
        di = feedback["defense_interpretation"]
        for key in ("front_shell_guess", "coverage_guess", "pressure_risk", "confidence"):
            if key not in di:
                errors.append(f"defense_interpretation missing key: {key}")

    summary_text = feedback.get("summary_text")
    if not isinstance(summary_text, str) or not summary_text.strip():
        errors.append("summary_text must be a non-empty string")

    return errors


def normalize_feedback(
    *,
    feedback: dict,
    analysis_id: str,
    offensive_play: dict,
    defensive_play: dict,
    domain_warning: str | None,
) -> dict:
    normalized = dict(feedback)
    normalized["analysis_id"] = analysis_id
    normalized["offensive_play"] = {
        "play_id": offensive_play["play_id"],
        "team_slug": offensive_play["team_slug"],
        "formation_slug": offensive_play["formation_slug"],
        "play_name": offensive_play["play_name"],
        "play_art_path": offensive_play["play_art_path"],
    }
    normalized["defensive_play"] = {
        "play_id": defensive_play["play_id"],
        "team_slug": defensive_play["team_slug"],
        "formation_slug": defensive_play["formation_slug"],
        "play_name": defensive_play["play_name"],
        "play_art_path": defensive_play["play_art_path"],
    }
    normalized["audience"] = "qb_room"
    normalized["grounding_mode"] = "evidence_first"

    if domain_warning:
        existing = normalized.get("risk_flags")
        if not isinstance(existing, list):
            existing = []
        if "domain_mismatch_user_prompt" not in existing:
            existing.append("domain_mismatch_user_prompt")
        normalized["risk_flags"] = existing

        summary = str(normalized.get("summary_text") or "").strip()
        normalized["summary_text"] = f"{domain_warning} {summary}".strip()

    return normalized


def _provider_from_name(provider_name: str):
    normalized = provider_name.strip().lower()
    if normalized == "openai":
        return OpenAIProvider(), os.getenv("COACH_FEEDBACK_OPENAI_MODEL", "gpt-4.1")
    if normalized == "ollama":
        return OllamaProvider(), os.getenv("COACH_FEEDBACK_OLLAMA_MODEL", "llava:latest")
    if normalized == "mock":
        return None, "mock"
    raise ValueError("provider must be one of: openai, ollama, mock")


def _mock_feedback(offensive_play: dict, defensive_play: dict) -> dict:
    return {
        "analysis_id": "mock_analysis",
        "offensive_play": {
            "play_id": offensive_play["play_id"],
            "team_slug": offensive_play["team_slug"],
            "formation_slug": offensive_play["formation_slug"],
            "play_name": offensive_play["play_name"],
            "play_art_path": offensive_play["play_art_path"],
        },
        "defensive_play": {
            "play_id": defensive_play["play_id"],
            "team_slug": defensive_play["team_slug"],
            "formation_slug": defensive_play["formation_slug"],
            "play_name": defensive_play["play_name"],
            "play_art_path": defensive_play["play_art_path"],
        },
        "audience": "qb_room",
        "grounding_mode": "evidence_first",
        "route_roles": [
            {
                "route_label": "Outside go",
                "role": "decoy",
                "evidence": "Vertical stretch route on boundary receiver.",
                "confidence": 0.65,
            },
            {
                "route_label": "Slot dig",
                "role": "primary",
                "evidence": "Middle-breaking route at intermediate depth.",
                "confidence": 0.7,
            },
            {
                "route_label": "Back swing",
                "role": "tertiary",
                "evidence": "Late flat outlet path behind line.",
                "confidence": 0.72,
            },
        ],
        "qb_progression": {
            "pre_snap_keys": [
                "Identify leverage on slot defender.",
                "Confirm two-high vs one-high shell indicator.",
            ],
            "post_snap_keys": [
                "Read curl/flat conflict defender width.",
                "Reset to checkdown if middle window closes.",
            ],
            "read_order": ["slot dig", "boundary curl", "back swing"],
            "checkdown_rule": "Take swing immediately if first two windows are capped.",
        },
        "defense_interpretation": {
            "front_shell_guess": "Nickel four-down look",
            "coverage_guess": "Cover 3 match tendency",
            "pressure_risk": "Moderate simulated pressure from slot side",
            "confidence": 0.58,
        },
        "coaching_points": [
            "Hold the seam defender with eyes before driving the dig.",
            "Climb pocket on edge pressure before second read throw.",
        ],
        "risk_flags": [],
        "uncertainties": [
            "Exact defensive pressure pattern cannot be confirmed from still play art alone."
        ],
        "summary_text": (
            f"{offensive_play['play_name']} can stress intermediate zones against "
            f"{defensive_play['play_name']} if the QB confirms shell leverage and "
            "moves quickly through dig-to-outlet progression."
        ),
    }


def generate_coach_feedback(
    *,
    off_play_id: str,
    def_play_id: str,
    off_manifest_path: str,
    def_manifest_path: str,
    provider_name: str = "openai",
    model: str | None = None,
    audience: str = "qb_room",
    grounding_mode: str = "evidence_first",
    user_prompt: str = "",
    kb_config: KBConfig | None = None,
) -> dict:
    off_rows = load_manifest_rows(off_manifest_path)
    def_rows = load_manifest_rows(def_manifest_path)
    offensive_play = resolve_play(off_play_id, off_rows, "offense")
    defensive_play = resolve_play(def_play_id, def_rows, "defense")

    analysis_id = build_analysis_id(off_play_id, def_play_id)
    domain_warning = get_domain_soft_guard_message(user_prompt)

    kb_query = f"{offensive_play['play_name']} vs {defensive_play['play_name']}"
    kb_context = retrieve_context(kb_query, top_k=3, config=kb_config)

    provider, default_model = _provider_from_name(provider_name)
    selected_model = model or default_model

    if provider_name.lower() == "mock":
        feedback = _mock_feedback(offensive_play, defensive_play)
    else:
        system_prompt = _build_system_prompt(audience=audience, grounding_mode=grounding_mode)
        user_prompt_payload = _build_user_prompt(
            offensive_play,
            defensive_play,
            user_prompt=user_prompt,
            kb_context=kb_context,
        )
        feedback = provider.generate_feedback(
            system_prompt=system_prompt,
            user_prompt=user_prompt_payload,
            offensive_image_path=offensive_play["play_art_path"],
            defensive_image_path=defensive_play["play_art_path"],
            model=selected_model,
        )

    normalized = normalize_feedback(
        feedback=feedback,
        analysis_id=analysis_id,
        offensive_play=offensive_play,
        defensive_play=defensive_play,
        domain_warning=domain_warning,
    )
    errors = validate_feedback_schema(normalized)
    if errors:
        raise CoachFeedbackError("; ".join(errors))

    return normalized
