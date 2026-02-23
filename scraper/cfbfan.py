import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path

BASE_URL = "https://cfb.fan"
S3_BASE = "https://s3.us-east-2.amazonaws.com/media.cfb.fan"
HEADERS = {"Referer": "https://cfb.fan/"}


def get_formations(team_slug: str, year: int = 26) -> list[dict]:
    """Fetch all formations for a given team playbook."""
    url = f"{BASE_URL}/{year}/playbooks/{team_slug}/"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    formations = []

    for link in soup.select("a.playbooks-list__link"):
        formations.append({
            "name": link.text.strip(),
            "url": BASE_URL + link["href"]
        })

    return formations


def get_plays(formation_url: str) -> list[dict]:
    """Fetch all plays for a given formation."""
    response = requests.get(formation_url, headers=HEADERS)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    plays = []

    for link in soup.select("a[href*='/playbooks/']"):
        href = link["href"]
        parts = [p for p in href.split("/") if p]
        if len(parts) == 5:
            plays.append({
                "name": link.text.strip(),
                "url": BASE_URL + href
            })

    return plays


def get_play_art_url(play_url: str) -> str | None:
    """Extract S3 image URL by parsing canonical formation name from play page."""
    response = requests.get(play_url, headers=HEADERS)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    url_parts = play_url.rstrip("/").split("/")
    formation_url_slug = url_parts[-2]
    play_slug = url_parts[-1]  # keep hyphens as-is
    year = url_parts[3]

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


def download_playbook(team_slug: str, output_dir: str = "data/playbooks", year: int = 26):
    """Download all play art images for a team's playbook."""
    base_path = Path(output_dir) / team_slug
    base_path.mkdir(parents=True, exist_ok=True)

    formations = get_formations(team_slug, year)
    print(f"Found {len(formations)} formations for {team_slug}")

    for formation in formations:
        formation_path = formation["url"].replace(BASE_URL, "").rstrip("/")
        formation_slug = formation_path.split("/")[-1]
        formation_dir = base_path / formation_slug
        formation_dir.mkdir(exist_ok=True)

        plays = get_plays(formation["url"])
        print(f"  {formation['name']} — {len(plays)} plays")

        for play in plays:
            play_url = play["url"]
            dest = formation_dir / f"{play_url.rstrip('/').split('/')[-1].replace('-', '_')}.jpg"

            if dest.exists():
                print(f"    [skip] {play['name']}")
                continue

            image_url = get_play_art_url(play_url)
            if not image_url:
                print(f"    [no url] {play['name']}")
                continue

            r = requests.get(image_url, headers=HEADERS)
            if r.status_code == 200:
                dest.write_bytes(r.content)
                print(f"    [ok] {play['name']}")
            else:
                print(f"    [fail {r.status_code}] {play['name']} -> {image_url}")


if __name__ == "__main__":
    download_playbook("georgia-off")