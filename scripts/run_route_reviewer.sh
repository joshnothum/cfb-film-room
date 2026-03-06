#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

DATA_FILE="${1:-${ROOT_DIR}/data/qa/route_gold_seeded.jsonl}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8787}"
BACKUPS_DIR="${BACKUPS_DIR:-${ROOT_DIR}/data/qa/backups}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing python virtualenv at ${PYTHON_BIN}."
  echo "Create it with: python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt"
  exit 1
fi

if [[ ! -f "${DATA_FILE}" ]]; then
  echo "Route gold file not found: ${DATA_FILE}"
  echo "Pass a file path as the first argument, for example:"
  echo "  ./scripts/run_route_reviewer.sh data/qa/route_gold_seeded.jsonl"
  exit 1
fi

exec "${PYTHON_BIN}" "${ROOT_DIR}/scripts/review_server.py" \
  --data-file "${DATA_FILE}" \
  --schema route \
  --host "${HOST}" \
  --port "${PORT}" \
  --backups-dir "${BACKUPS_DIR}"
