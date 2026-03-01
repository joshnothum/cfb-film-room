#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.coach_feedback import generate_coach_feedback
from pipeline.kb import KBConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coach-feedback",
        description="Generate QB-room coach feedback from offense/defense play art pairs.",
    )
    parser.add_argument("--off-play-id", required=True, help="Offensive play_id from offense manifest.")
    parser.add_argument("--def-play-id", required=True, help="Defensive play_id from defense manifest.")
    parser.add_argument("--off-manifest", required=True, help="Offense manifest JSONL path.")
    parser.add_argument("--def-manifest", required=True, help="Defense manifest JSONL path.")

    parser.add_argument(
        "--provider",
        choices=("openai", "ollama", "mock"),
        default="openai",
        help="LLM provider used for analysis.",
    )
    parser.add_argument("--model", default=None, help="Optional model override.")
    parser.add_argument("--user-prompt", default="", help="Optional extra analyst guidance.")

    parser.add_argument("--out", required=True, help="Output JSON path.")
    parser.add_argument(
        "--format",
        choices=("json", "markdown", "both"),
        default="both",
        help="Output format for persisted files.",
    )

    parser.add_argument(
        "--kb-enabled",
        action="store_true",
        help="Enable football strategy KB retrieval (design stub returns empty for now).",
    )
    parser.add_argument("--kb-docs-dir", default="data/kb/football", help="KB docs root path placeholder.")
    parser.add_argument("--kb-index-dir", default="data/kb/index", help="KB index path placeholder.")
    return parser


def _to_markdown(result: dict) -> str:
    lines = [
        f"# Coach Feedback: {result['analysis_id']}",
        "",
        "## Play Pair",
        f"- Offense: {result['offensive_play']['play_id']} ({result['offensive_play']['play_name']})",
        f"- Defense: {result['defensive_play']['play_id']} ({result['defensive_play']['play_name']})",
        "",
        "## Summary",
        result["summary_text"],
        "",
        "## QB Progression",
        "- Pre-snap keys:",
    ]
    for item in result["qb_progression"]["pre_snap_keys"]:
        lines.append(f"  - {item}")

    lines.append("- Post-snap keys:")
    for item in result["qb_progression"]["post_snap_keys"]:
        lines.append(f"  - {item}")

    lines.append(f"- Read order: {', '.join(result['qb_progression']['read_order'])}")
    lines.append(f"- Checkdown rule: {result['qb_progression']['checkdown_rule']}")
    lines.append("")
    lines.append("## Route Roles")

    for route in result["route_roles"]:
        lines.append(
            f"- {route['route_label']} -> {route['role']} (conf: {route['confidence']}): {route['evidence']}"
        )

    lines.append("")
    lines.append("## Risk Flags")
    for flag in result["risk_flags"]:
        lines.append(f"- {flag}")

    lines.append("")
    lines.append("## Uncertainties")
    for item in result["uncertainties"]:
        lines.append(f"- {item}")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    kb_config = KBConfig(
        enabled=args.kb_enabled,
        docs_dir=args.kb_docs_dir,
        index_dir=args.kb_index_dir,
    )

    result = generate_coach_feedback(
        off_play_id=args.off_play_id,
        def_play_id=args.def_play_id,
        off_manifest_path=args.off_manifest,
        def_manifest_path=args.def_manifest,
        provider_name=args.provider,
        model=args.model,
        user_prompt=args.user_prompt,
        kb_config=kb_config,
    )

    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format in {"json", "both"}:
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    if args.format in {"markdown", "both"}:
        md_path = output_path.with_suffix(".md")
        md_path.write_text(_to_markdown(result), encoding="utf-8")

    print(f"Wrote analysis to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
