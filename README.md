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

## Segment game film (MVP scaffold)

Generate per-play clips and metadata stubs from a full game recording:

```bash
python -m pipeline.segment \
  --input /path/to/game_recording.mp4 \
  --game-id uga_vs_bama_2026wk01 \
  --out-dir data/plays
```

Metadata-only mode (no clip export):

```bash
python -m pipeline.segment \
  --input /path/to/game_recording.mp4 \
  --game-id uga_vs_bama_2026wk01 \
  --out-dir data/plays \
  --skip-clips
```

Shortcut command (uses your current default test settings):

```bash
./scripts/run_default_segment.sh
```

Optional overrides:

```bash
./scripts/run_default_segment.sh \
  /path/to/input.webm \
  custom_game_id \
  /path/to/output_dir \
  2
```

Show progress in terminal:

```bash
python -m pipeline.segment \
  --input /path/to/game_recording.mp4 \
  --game-id uga_vs_bama_2026wk01 \
  --out-dir data/plays \
  --show-progress \
  --progress-every 5
```

Segmentation now defaults to scene-change boundary detection (`--segmentation-mode scene`) and can fall back to fixed windows (`--segmentation-mode fixed`).

Scene mode tuning:

- `--scene-threshold` (default `0.25`)
- `--pre-snap-padding` (default `2.0`)
- `--post-whistle-padding` (default `3.0`)
- `--min-play-seconds` (default `3.0`)
- `--max-play-seconds` (default `25.0`)

OCR enrichment (optional):

```bash
python -m pipeline.segment \
  --input /path/to/game_recording.mp4 \
  --game-id uga_vs_bama_2026wk01 \
  --out-dir data/plays \
  --skip-clips \
  --enable-ocr \
  --ocr-engine tesseract \
  --ocr-sample-frame mid \
  --ocr-min-confidence 0.75
```

When enabled, OCR attempts to populate:

- `quarter`, `clock`, `down`, `distance`, `field_position`
- `home_score`, `away_score`
- per-field confidence keys (for example `clock_confidence`)
- `ocr_raw_text`, `ocr_sample_time_sec`

`quality_flag` is set to `ok` only when critical fields (`quarter`, `clock`, `down`, `distance`) are present and meet the confidence threshold; otherwise it is `needs_review`.
Score values are extracted from dedicated left/right scorebug crops across multiple sample timestamps and crop presets, then the best read is selected. Missing scores can be carried forward from the prior play when needed.

Play-art visibility detection (optional):

```bash
python -m pipeline.segment \
  --input /path/to/game_recording.mp4 \
  --game-id uga_vs_bama_2026wk01 \
  --out-dir data/plays \
  --skip-clips \
  --enable-play-art-detection \
  --play-art-min-confidence 0.55
```

When enabled, each play row includes:

- `play_art_visible` (`true` / `false` / `null`)
- `play_art_confidence`
- `play_art_sample_time_sec`

This is a first-pass heuristic detector to identify likely route-art overlays, not a play matcher.

Outputs:

- `data/plays/plays.jsonl`: canonical play rows for downstream OCR/tactical enrichment
- `data/plays/plays_preview.csv`: quick QA table for reviewing segment quality
- `data/plays/clips/play_XXXX.mp4`: exported clips unless `--skip-clips` is set

## Running tests

```bash
./.venv/bin/pytest -q
```

## OCR evaluation against a gold set

Use this after creating a labeled JSONL with `play_id` + expected OCR fields:

```bash
./.venv/bin/python scripts/eval_ocr.py \
  --gold data/qa/ocr_gold.jsonl \
  --pred data/plays/game_02232026/plays.jsonl \
  --min-pass-rate 0.60
```

Add `--json` for machine-readable output.

### Scaffold a starter OCR gold file

There is a tracked example format at `examples/ocr_gold.template.jsonl`.

Generate a label-ready file from current model output:

```bash
./.venv/bin/python scripts/scaffold_ocr_gold.py \
  --plays data/plays/game_02232026/plays.jsonl \
  --out data/qa/ocr_gold.jsonl
```

Focus on the weakest rows first:

```bash
./.venv/bin/python scripts/scaffold_ocr_gold.py \
  --plays data/plays/game_02232026/plays.jsonl \
  --only-needs-review \
  --limit 120 \
  --out data/qa/ocr_gold.jsonl
```

Add `--seed-with-predictions` if you want to correct existing values instead of filling from blank.

### VS Code labeling shortcuts

With a gold JSONL file open in VS Code:

- `Cmd/Ctrl+Shift+B`: runs `Backup + Format + Strict Validate Current JSONL`
- `Tasks: Run Task` includes:
  - `OCR Gold: Next Unlabeled`
  - `OCR Gold: Progress`
  - `OCR Gold: Evaluate Current Gold`
  - `OCR Gold: Open Clip For Current Row (macOS)`

### Recommended labeling loop (fast path)

1. Run `Tasks: Run Task` -> `OCR Gold: Open Clip For Current Row (macOS)`.
2. Fill fields on that JSONL line (`quarter`, `clock`, `down`, `distance`, scores, `quality_flag`).
3. Press `Cmd/Ctrl+Shift+B` to backup + format + strict validate.
4. Run `Tasks: Run Task` -> `OCR Gold: Next Unlabeled`.
5. Repeat until complete, then run `OCR Gold: Progress` and `OCR Gold: Evaluate Current Gold`.

## Local browser review app

Run a local UI for reviewing and editing OCR gold rows with inline clip playback:

```bash
./.venv/bin/python scripts/review_server.py \
  --data-file data/qa/ocr_gold_batch_20260227.jsonl \
  --host 127.0.0.1 \
  --port 8787
```

Then open [http://127.0.0.1:8787](http://127.0.0.1:8787).

UI behavior:
- Left: play list + filter.
- Middle: all row fields with proper input types (`text`, `number`, `checkbox`).
- Right: clip player sourced from `clip_path`.
- Buttons:
  - `Edit`: enables field editing
  - `Save`: writes changes back to the JSONL row
  - `Reset`: discards unsaved changes for the selected row

Every save automatically creates a timestamped backup in `data/qa/backups/`.

Recommended `review_disposition` usage:
- `keep`: normal reviewed clip, include in metrics/training.
- `skip_unusable`: reviewed but unusable (animation/no readable scorebug); excluded from evaluator metrics.
- `delete_candidate`: reviewed and likely safe to remove later; excluded from evaluator metrics.

`review_state` controls review progress in the UI:
- `pending`: not fully reviewed yet
- `reviewed`: completed a review pass for that play

The browser reviewer auto-sets `review_state=reviewed` on successful save.

Evaluator defaults now exclude `skip_unusable` and `delete_candidate` rows.
Use `--include-all-dispositions` with `scripts/eval_ocr.py` if you want raw metrics over every row.

List/delete workflow for deletion candidates:

```bash
./.venv/bin/python scripts/manage_delete_candidates.py data/qa/ocr_gold_batch_20260227.jsonl
./.venv/bin/python scripts/manage_delete_candidates.py data/qa/ocr_gold_batch_20260227.jsonl --delete --confirm
```

## Notes

- Network access to `cfb.fan` and its backing S3 bucket is required for scraping.
- Tests are unit-style and do not require live network access.
- `ffprobe` and `ffmpeg` are required for `pipeline.segment` runtime clip processing.
- `tesseract` is required if `--enable-ocr` is used.
- `Pillow` is required for `--enable-play-art-detection` (included in `requirements.txt`).
