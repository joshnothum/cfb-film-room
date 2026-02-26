#!/usr/bin/env bash
set -euo pipefail

# Defaults tuned for quick OCR + play-art testing.
INPUT_DEFAULT="/Users/joshnothum/dev/cfb-film-room/data/game-video/raw/game_recording_02232026.webm"
GAME_ID_DEFAULT="game_02232026"
OUT_DIR_DEFAULT="/Users/joshnothum/dev/cfb-film-room/data/plays/game_02232026"
PROGRESS_EVERY_DEFAULT="2"

INPUT_PATH="${1:-$INPUT_DEFAULT}"
GAME_ID="${2:-$GAME_ID_DEFAULT}"
OUT_DIR="${3:-$OUT_DIR_DEFAULT}"
PROGRESS_EVERY="${4:-$PROGRESS_EVERY_DEFAULT}"

cd /Users/joshnothum/dev/cfb-film-room
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

python -m pipeline.segment \
  --input "$INPUT_PATH" \
  --game-id "$GAME_ID" \
  --out-dir "$OUT_DIR" \
  --skip-clips \
  --enable-ocr \
  --enable-play-art-detection \
  --show-progress \
  --progress-every "$PROGRESS_EVERY"
