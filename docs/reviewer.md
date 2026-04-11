# Reviewer App Guide

This guide covers day-to-day usage of the local browser reviewer for OCR and route gold labeling.

## Launch

```bash
./.venv/bin/python scripts/review_server.py \
  --data-file data/qa/ocr_gold_batch_20260227.jsonl \
  --host 127.0.0.1 \
  --port 8787
```

Open: [http://127.0.0.1:8787](http://127.0.0.1:8787)

Route mode (schema-aware validation + play-art image preview):

```bash
./.venv/bin/python scripts/review_server.py \
  --data-file data/qa/route_gold_seeded.jsonl \
  --schema route \
  --host 127.0.0.1 \
  --port 8787
```

## Layout

- Left: game-grouped play list, status badge, game progress donut.
- Left controls now include text search plus quick filters for `pending/reviewed` and `play_type`.
- Middle: row fields editor.
- Right: media panel (clip video and/or play-art image depending on row fields).
- Route files include `play_type` (`run`, `pass`, `kick`, `rpo`) to speed filtering/triage.

## Core Workflow

1. Click a play.
2. Watch the clip.
3. Click `Edit`.
4. Fill/update fields.
5. Click `Save`.

`Save` writes to JSONL and auto-creates a timestamped backup in `data/qa/backups/`.

## Field Semantics

- `review_state`:
  - `pending`: not finished reviewing.
  - `reviewed`: completed review pass.
  - The app auto-sets this to `reviewed` on successful save.

- `quality_flag`:
  - `ok`: core OCR fields are confidently correct.
  - `needs_review`: uncertain, missing, or not trustworthy.

- `review_disposition`:
  - `keep`: normal row for metrics/training.
  - `skip_unusable`: reviewed but not labelable/useful (animation, no scorebug, unreadable).
  - `delete_candidate`: safe to consider for cleanup later.

## Recommended Decisions

- Normal playable clip with clear scorebug:
  - fill fields
  - `quality_flag=ok`
  - `review_disposition=keep`

- Unusable animation/no useful data:
  - leave core fields `null`
  - `quality_flag=needs_review`
  - `review_disposition=skip_unusable`

## Validation Rules (enforced on save)

- `clock`: `MM:SS` only (`00:00` to `59:59`).
- `quarter`: integer `1-5`.
- `down`: integer `1-4`.
- `distance`: integer `0-99`.
- `home_score` / `away_score`: integer `0-999`.
- `quality_flag`: `ok`, `needs_review`, or `null`.
- `review_disposition`: `keep`, `skip_unusable`, `delete_candidate`, or `null`.
- `review_state`: `pending`, `reviewed`, or `null`.
- `quality_flag=ok` requires all core fields present.

## Read-only Fields

The reviewer locks these fields from editing:

- `play_id`
- `game_id`
- `clip_path`
- `source_video`
- `start_sec`
- `end_sec`
- `label_priority`
- `selection_reason`

## Status Badges

- `Pending`: not reviewed yet.
- `Reviewed`: reviewed and retained.
- `Skip`: reviewed and marked unusable.
- `Delete?`: reviewed and marked as cleanup candidate.

## Cleanup Candidates

List rows marked `delete_candidate`:

```bash
./.venv/bin/python scripts/manage_delete_candidates.py data/qa/ocr_gold_batch_20260227.jsonl
```

Delete candidate clip files only when explicit:

```bash
./.venv/bin/python scripts/manage_delete_candidates.py data/qa/ocr_gold_batch_20260227.jsonl --delete --confirm
```
