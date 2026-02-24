import argparse
import json
from pathlib import Path

import requests

from scraper.cfbfan import BASE_URL, get_play_art_url


def _slug_to_name(play_slug: str) -> str:
    return play_slug.replace("_", " ").replace("-", " ").upper()


def build_manifest_records(
    *,
    team_slug: str,
    year: int = 26,
    playbooks_root: str = "data/playbooks",
    resolve_urls: bool = False,
    timeout: int = 15,
    session: requests.Session | None = None,
) -> list[dict]:
    base_dir = Path(playbooks_root) / team_slug
    if not base_dir.exists() or not base_dir.is_dir():
        raise FileNotFoundError(f"Team playbook directory not found: {base_dir}")

    records: list[dict] = []
    for image_path in sorted(base_dir.rglob("*.jpg")):
        formation_slug = image_path.parent.name
        play_slug = image_path.stem
        source_url = f"{BASE_URL}/{year}/playbooks/{team_slug}/{formation_slug}/{play_slug}"
        play_art_url = None

        if resolve_urls:
            try:
                play_art_url = get_play_art_url(source_url, session=session, timeout=timeout)
            except requests.RequestException:
                play_art_url = None

        records.append(
            {
                "play_id": f"{team_slug}:{year}:{formation_slug}:{play_slug}",
                "team_slug": team_slug,
                "year": year,
                "formation_slug": formation_slug,
                "play_slug": play_slug,
                "play_name": _slug_to_name(play_slug),
                "play_art_path": str(image_path),
                "play_art_url": play_art_url,
                "source_url": source_url,
            }
        )

    return records


def write_jsonl(records: list[dict], output_path: str) -> int:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return len(records)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cfb-film-room-manifest",
        description="Build a canonical play manifest from downloaded playbook art.",
    )
    parser.add_argument(
        "--team-slug",
        required=True,
        help="Team playbook slug, e.g. georgia-off",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=26,
        help="Game year segment in cfb.fan URLs (default: 26).",
    )
    parser.add_argument(
        "--playbooks-root",
        default="data/playbooks",
        help="Directory that contains team playbook folders.",
    )
    parser.add_argument(
        "--output",
        default="data/manifests/playbook_manifest.jsonl",
        help="Output JSONL path for manifest records.",
    )
    parser.add_argument(
        "--resolve-urls",
        action="store_true",
        help="Attempt live resolution of play_art_url values from cfb.fan.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Per-request timeout in seconds when resolving URLs.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = build_manifest_records(
        team_slug=args.team_slug,
        year=args.year,
        playbooks_root=args.playbooks_root,
        resolve_urls=args.resolve_urls,
        timeout=args.timeout,
    )
    count = write_jsonl(records, args.output)
    print(f"Wrote {count} records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
