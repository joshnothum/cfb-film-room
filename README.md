# CFB Film Room Scraper

Python scraper for downloading offensive play art images from [cfb.fan](https://cfb.fan) into a local, structured dataset.

## What it does

- Crawls team playbook formations
- Crawls plays within each formation
- Reconstructs canonical S3 image URLs for play art
- Downloads image assets to disk with skip-if-exists behavior

Output structure:

`data/playbooks/{team_slug}/{formation_slug}/{play_slug}.jpg`

## Quick start

### 1) Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Run the scraper

```bash
python -m scraper --team-slug georgia-off
```

Common options:

```bash
python -m scraper \
  --team-slug georgia-off \
  --year 26 \
  --output-dir data/playbooks \
  --timeout 15
```

## CLI reference

```bash
python -m scraper --help
```

Arguments:

- `--team-slug` (required): cfb.fan team playbook slug (example: `georgia-off`)
- `--year` (default: `26`): URL year segment in cfb.fan paths
- `--output-dir` (default: `data/playbooks`): base output directory
- `--timeout` (default: `15`): per-request timeout in seconds

## Build canonical play manifest

Generate a JSONL manifest from downloaded play art:

```bash
python -m scraper.manifest --team-slug georgia-off
```

Write to a custom path:

```bash
python -m scraper.manifest \
  --team-slug georgia-off \
  --output data/manifests/georgia_playbook_manifest.jsonl
```

Optionally resolve live `play_art_url` values from cfb.fan:

```bash
python -m scraper.manifest --team-slug georgia-off --resolve-urls
```

Manifest schema per record:

- `play_id`: stable id (`{team_slug}:{year}:{formation_slug}:{play_slug}`)
- `team_slug`: source team slug
- `year`: game year segment used in URLs
- `formation_slug`: formation folder/URL slug
- `play_slug`: play folder/URL slug
- `play_name`: normalized display form from slug
- `play_art_path`: local absolute/relative path to image file
- `play_art_url`: resolved S3 image URL (`null` unless `--resolve-urls`)
- `source_url`: canonical cfb.fan play page URL

## Running tests

```bash
./.venv/bin/pytest -q
```

## Notes

- Network access to `cfb.fan` and its backing S3 bucket is required for scraping.
- Tests are unit-style and do not require live network access.
