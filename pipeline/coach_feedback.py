import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pipeline.kb import KBConfig, retrieve_context
from pipeline.playart_features import build_playart_feature_bundle
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
RUN_KEYWORDS = {
    "inside_zone",
    "outside_zone",
    "zone_split",
    "power",
    "counter",
    "draw",
    "sweep",
    "dive",
    "read_option",
    "jet",
    "trap",
}
ROLE_ORDER = ("primary", "secondary", "tertiary", "decoy")
ROLE_SET = set(ROLE_ORDER)


class CoachFeedbackError(RuntimeError):
    pass


def _clamp_confidence(value, *, max_value: float = 0.85) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.5
    if numeric < 0:
        return 0.0
    if numeric > max_value:
        return max_value
    return round(numeric, 2)


def _normalize_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [text]


def _normalize_read_order(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []

    parts: list[str] = []
    for chunk in text.replace("\n", " ").split("."):
        for subchunk in chunk.split(","):
            token = subchunk.strip(" -")
            if token:
                parts.append(token)
    if not parts:
        return [text]
    return parts


def _normalize_role(value: str) -> str:
    role = str(value or "").strip().lower()
    if role in ROLE_SET:
        return role
    return "tertiary"


def infer_play_type(*, play_slug: str, play_name: str) -> str:
    text = f"{play_slug} {play_name}".lower()
    for keyword in RUN_KEYWORDS:
        if keyword in text:
            return "run"
    return "pass"


def _normalize_route_roles(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    normalized: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        route_label = str(item.get("route_label") or "unnamed route").strip()
        evidence = str(item.get("evidence") or "No supporting evidence provided.").strip()
        normalized.append(
            {
                "route_label": route_label,
                "role": _normalize_role(item.get("role")),
                "evidence": evidence,
                "confidence": _clamp_confidence(item.get("confidence")),
            }
        )
    return normalized


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


def _build_system_prompt(audience: str, grounding_mode: str, play_type: str) -> str:
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
    pass_rules = (
        "For pass concepts: list route roles with assignment hints (X/Y/A/B/RB) when visible, "
        "and avoid inventing unseen routes."
    )
    run_rules = (
        "For run concepts: focus on front identification, fit leverage, aiming point, and cutback/press decisions. "
        "Do not force pass-style checkdown language."
    )
    return (
        f"You are a football coach assistant for a {audience} audience. "
        f"{schema_text} {rules_text} {pass_rules} {run_rules} "
        f"Grounding mode: {grounding_mode}. Play type hint: {play_type}."
    )


def _build_user_prompt(
    offensive_play: dict,
    defensive_play: dict,
    *,
    user_prompt: str,
    kb_context: list[dict],
    play_type: str,
    playart_features: dict | None,
) -> str:
    prompt = {
        "task": "Analyze this offense vs defense play pair and produce coaching feedback.",
        "offensive_play": {
            "play_id": offensive_play["play_id"],
            "team_slug": offensive_play["team_slug"],
            "formation_slug": offensive_play["formation_slug"],
            "play_name": offensive_play["play_name"],
            "play_slug": offensive_play["play_slug"],
        },
        "defensive_play": {
            "play_id": defensive_play["play_id"],
            "team_slug": defensive_play["team_slug"],
            "formation_slug": defensive_play["formation_slug"],
            "play_name": defensive_play["play_name"],
        },
        "user_prompt": user_prompt or "",
        "kb_context": kb_context,
        "play_type_hint": play_type,
        "playart_feature_hints": playart_features or {},
        "schema_notes": {
            "route_roles": "Array of objects with route_label, role(primary|secondary|tertiary|decoy), evidence, confidence(0-1).",
            "qb_progression": "Object with pre_snap_keys, post_snap_keys, read_order, checkdown_rule.",
            "defense_interpretation": "Object with front_shell_guess, coverage_guess, pressure_risk, confidence(0-1).",
            "run_concepts": "For run concepts, read_order should describe run decision flow (front ID -> fit key -> aiming point -> cutback).",
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
    play_type = infer_play_type(
        play_slug=str(offensive_play.get("play_slug") or ""),
        play_name=str(offensive_play.get("play_name") or ""),
    )
    normalized["play_type_hint"] = play_type
    normalized["route_roles"] = _normalize_route_roles(normalized.get("route_roles"))
    normalized["coaching_points"] = _normalize_list(normalized.get("coaching_points"))
    normalized["risk_flags"] = _normalize_list(normalized.get("risk_flags"))
    normalized["uncertainties"] = _normalize_list(normalized.get("uncertainties"))

    qb_progression = normalized.get("qb_progression")
    if not isinstance(qb_progression, dict):
        qb_progression = {}
    normalized["qb_progression"] = {
        "pre_snap_keys": _normalize_list(qb_progression.get("pre_snap_keys")),
        "post_snap_keys": _normalize_list(qb_progression.get("post_snap_keys")),
        "read_order": _normalize_read_order(qb_progression.get("read_order")),
        "checkdown_rule": str(qb_progression.get("checkdown_rule") or "").strip(),
    }

    defense_interp = normalized.get("defense_interpretation")
    if not isinstance(defense_interp, dict):
        defense_interp = {}
    normalized["defense_interpretation"] = {
        "front_shell_guess": str(defense_interp.get("front_shell_guess") or "").strip(),
        "coverage_guess": str(defense_interp.get("coverage_guess") or "").strip(),
        "pressure_risk": str(defense_interp.get("pressure_risk") or "").strip(),
        "confidence": _clamp_confidence(defense_interp.get("confidence")),
    }

    if play_type == "run":
        normalized["risk_flags"] = _normalize_list(normalized.get("risk_flags"))
        if "run_concept_mode" not in normalized["risk_flags"]:
            normalized["risk_flags"].append("run_concept_mode")

        read_order = normalized["qb_progression"]["read_order"]
        filtered = [
            step
            for step in read_order
            if "route" not in step.lower() and "checkdown" not in step.lower()
        ]
        if filtered:
            normalized["qb_progression"]["read_order"] = filtered
        else:
            normalized["qb_progression"]["read_order"] = [
                "Identify box count and front structure.",
                "Confirm first fit key at snap.",
                "Press aiming point then cut based on leverage.",
            ]

        checkdown_rule = normalized["qb_progression"]["checkdown_rule"].lower()
        if not checkdown_rule or "checkdown" in checkdown_rule:
            normalized["qb_progression"]["checkdown_rule"] = (
                "Not a pass checkdown concept; prioritize run fit key and cutback lane."
            )

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
    enable_playart_features: bool = False,
    playart_features_dir: str | None = None,
) -> dict:
    off_rows = load_manifest_rows(off_manifest_path)
    def_rows = load_manifest_rows(def_manifest_path)
    offensive_play = resolve_play(off_play_id, off_rows, "offense")
    defensive_play = resolve_play(def_play_id, def_rows, "defense")

    analysis_id = build_analysis_id(off_play_id, def_play_id)
    domain_warning = get_domain_soft_guard_message(user_prompt)

    kb_query = f"{offensive_play['play_name']} vs {defensive_play['play_name']}"
    kb_context = retrieve_context(kb_query, top_k=3, config=kb_config)
    play_type = infer_play_type(
        play_slug=str(offensive_play.get("play_slug") or ""),
        play_name=str(offensive_play.get("play_name") or ""),
    )
    playart_features: dict | None = None
    offensive_input_image_path = offensive_play["play_art_path"]
    defensive_input_image_path = defensive_play["play_art_path"]
    if enable_playart_features:
        playart_features = build_playart_feature_bundle(
            offensive_image_path=offensive_play["play_art_path"],
            defensive_image_path=defensive_play["play_art_path"],
            output_dir=playart_features_dir,
        )
        offensive_input_image_path = playart_features["offense"]["enhanced_image_path"]
        defensive_input_image_path = playart_features["defense"]["enhanced_image_path"]

    provider, default_model = _provider_from_name(provider_name)
    selected_model = model or default_model

    if provider_name.lower() == "mock":
        feedback = _mock_feedback(offensive_play, defensive_play)
    else:
        system_prompt = _build_system_prompt(
            audience=audience,
            grounding_mode=grounding_mode,
            play_type=play_type,
        )
        user_prompt_payload = _build_user_prompt(
            offensive_play,
            defensive_play,
            user_prompt=user_prompt,
            kb_context=kb_context,
            play_type=play_type,
            playart_features=playart_features,
        )
        feedback = provider.generate_feedback(
            system_prompt=system_prompt,
            user_prompt=user_prompt_payload,
            offensive_image_path=offensive_input_image_path,
            defensive_image_path=defensive_input_image_path,
            model=selected_model,
        )

    normalized = normalize_feedback(
        feedback=feedback,
        analysis_id=analysis_id,
        offensive_play=offensive_play,
        defensive_play=defensive_play,
        domain_warning=domain_warning,
    )
    if playart_features:
        normalized["playart_features"] = playart_features
    errors = validate_feedback_schema(normalized)
    if errors:
        raise CoachFeedbackError("; ".join(errors))

    return normalized
