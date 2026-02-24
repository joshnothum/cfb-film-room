import argparse
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://cfb.fan"
S3_BASE = "https://s3.us-east-2.amazonaws.com/media.cfb.fan"
HEADERS = {"Referer": "https://cfb.fan/"}
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3


def _require_non_empty(value: str, field_name: str) -> str:
    cleaned = value.strip() if isinstance(value, str) else ""
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _normalize_url(url_or_path: str) -> str:
    if url_or_path.startswith(("http://", "https://")):
        return url_or_path.rstrip("/")
    if url_or_path.startswith("/"):
        return f"{BASE_URL}{url_or_path}".rstrip("/")
    return f"{BASE_URL}/{url_or_path.lstrip('/')}".rstrip("/")


def _get_with_retry(
    url: str,
    *,
    session: requests.Session | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> requests.Response:
    client = session or requests
    last_exc: requests.RequestException | None = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response else None
            # Retry transient classes only.
            if status not in (None, 429) and status < 500:
                raise
            last_exc = exc
        except requests.RequestException as exc:
            last_exc = exc

        if attempt == MAX_RETRIES - 1 and last_exc:
            raise last_exc

    raise RuntimeError("Retry loop exited unexpectedly")


def get_formations(
    team_slug: str,
    year: int = 26,
    *,
    session: requests.Session | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict]:
    """Fetch all formations for a given team playbook."""
    team_slug = _require_non_empty(team_slug, "team_slug")
    url = f"{BASE_URL}/{year}/playbooks/{team_slug}/"
    response = _get_with_retry(url, session=session, timeout=timeout)

    soup = BeautifulSoup(response.text, "html.parser")
    formations = []

    for link in soup.select("a.playbooks-list__link"):
        formations.append({
            "name": link.text.strip(),
            "url": _normalize_url(link["href"])
        })

    return formations


def get_plays(
    formation_url: str,
    *,
    session: requests.Session | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict]:
    """Fetch all plays for a given formation."""
    formation_url = _require_non_empty(formation_url, "formation_url")
    response = _get_with_retry(
        _normalize_url(formation_url),
        session=session,
        timeout=timeout,
    )

    soup = BeautifulSoup(response.text, "html.parser")
    plays = []

    for link in soup.select("a[href*='/playbooks/']"):
        href = link["href"]
        parts = [p for p in href.split("/") if p]
        if len(parts) == 5:
            plays.append({
                "name": link.text.strip(),
                "url": _normalize_url(href)
            })

    return plays


def get_play_art_url(
    play_url: str,
    *,
    session: requests.Session | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str | None:
    """Extract S3 image URL by parsing canonical formation name from play page."""
    play_url = _require_non_empty(play_url, "play_url")
    normalized_play_url = _normalize_url(play_url)
    response = _get_with_retry(normalized_play_url, session=session, timeout=timeout)

    soup = BeautifulSoup(response.text, "html.parser")

    path_parts = [p for p in urlparse(normalized_play_url).path.split("/") if p]
    year = path_parts[0] if path_parts else "26"
    formation_url_slug = path_parts[-2] if len(path_parts) >= 2 else ""
    play_slug = path_parts[-1] if path_parts else ""

    # Get canonical formation name from h1
    formation_div = soup.select_one("h1 div.text-lightest-gray")
    if not formation_div:
        return None

    formation_name = formation_div.text.strip()
    formation_name_slug = formation_name.lower().replace(" ", "_")

    # Try breadcrumb link first (handles multi-word groups like "Goal Line Normal")
    formation_group = None
    for crumb in soup.select("li.breadcrumbs__item a.breadcrumbs__link"):
        parts = [p for p in crumb["href"].split("/") if p]
        if len(parts) == 4:
            group_name = crumb.text.strip().replace(formation_name, "").strip()
            formation_group = group_name.lower().replace(" ", "_")
            break

    # Fallback: derive group from URL slug by removing formation name suffix
    if not formation_group:
        formation_name_in_url = formation_name.lower().replace(" ", "-")
        idx = formation_url_slug.rfind(f"-{formation_name_in_url}")
        if idx != -1:
            formation_group = formation_url_slug[:idx].replace("-", "_")
        else:
            formation_group = formation_url_slug.replace("-", "_")

    return f"{S3_BASE}/{year}/playbookdb/offense/{formation_group}/{formation_name_slug}/{play_slug}.jpg"


def download_playbook(
    team_slug: str,
    output_dir: str = "data/playbooks",
    year: int = 26,
    *,
    session: requests.Session | None = None,
    timeout: int = DEFAULT_TIMEOUT,
):
    """Download all play art images for a team's playbook."""
    team_slug = _require_non_empty(team_slug, "team_slug")
    base_path = Path(output_dir) / team_slug
    base_path.mkdir(parents=True, exist_ok=True)

    formations = get_formations(team_slug, year, session=session, timeout=timeout)
    print(f"Found {len(formations)} formations for {team_slug}")

    for formation in formations:
        formation_path = formation["url"].replace(BASE_URL, "").rstrip("/")
        formation_slug = formation_path.split("/")[-1]
        formation_dir = base_path / formation_slug
        formation_dir.mkdir(exist_ok=True)

        plays = get_plays(formation["url"], session=session, timeout=timeout)
        print(f"  {formation['name']} — {len(plays)} plays")

        for play in plays:
            play_url = play["url"]
            play_slug = play_url.rstrip("/").split("/")[-1]
            dest = formation_dir / f"{play_slug}.jpg"

            if dest.exists():
                print(f"    [skip] {play['name']}")
                continue

            image_url = get_play_art_url(play_url, session=session, timeout=timeout)
            if not image_url:
                print(f"    [no url] {play['name']}")
                continue

            try:
                r = _get_with_retry(image_url, session=session, timeout=timeout)
                dest.write_bytes(r.content)
                print(f"    [ok] {play['name']}")
            except requests.RequestException as exc:
                print(f"    [fail] {play['name']} -> {image_url} ({exc})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cfb-film-room-scraper",
        description="Download cfb.fan playbook art for a team.",
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
        "--output-dir",
        default="data/playbooks",
        help="Directory where playbook images are stored.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Per-request timeout in seconds.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    download_playbook(
        args.team_slug,
        output_dir=args.output_dir,
        year=args.year,
        timeout=args.timeout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
