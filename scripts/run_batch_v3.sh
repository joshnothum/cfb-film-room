#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

PROVIDER="${1:-openai}"   # openai | ollama | mock
FORMAT="${2:-both}"        # json | markdown | both
OUT_DIR="${3:-data/analysis}"

if [[ "${PROVIDER}" != "openai" && "${PROVIDER}" != "ollama" && "${PROVIDER}" != "mock" ]]; then
  echo "error: provider must be one of openai|ollama|mock" >&2
  exit 1
fi

if [[ "${FORMAT}" != "json" && "${FORMAT}" != "markdown" && "${FORMAT}" != "both" ]]; then
  echo "error: format must be one of json|markdown|both" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"
FEATURE_DIR="${OUT_DIR}/playart_features"
mkdir -p "${FEATURE_DIR}"
ROUTE_DIR="${OUT_DIR}/route_parser"
mkdir -p "${ROUTE_DIR}"

EXTRA_ARGS=()
if [[ "${PROVIDER}" == "openai" ]]; then
  EXTRA_ARGS+=("--allow-external-upload")
fi

run_case() {
  local output_file="$1"
  local off_play_id="$2"
  local def_play_id="$3"
  local def_manifest="$4"

  echo "[run] ${output_file}"
  ./.venv/bin/python scripts/coach_feedback.py \
    --off-play-id "${off_play_id}" \
    --def-play-id "${def_play_id}" \
    --off-manifest data/manifests/georgia-off_manifest.jsonl \
    --def-manifest "${def_manifest}" \
    --provider "${PROVIDER}" \
    --enable-playart-features \
    --playart-features-dir "${FEATURE_DIR}" \
    --enable-route-parser \
    --route-parser-dir "${ROUTE_DIR}" \
    --route-parser-preferred \
    --out "${OUT_DIR}/${output_file}.json" \
    --format "${FORMAT}" \
    "${EXTRA_ARGS[@]}"
}

# 1) Flood vs Cover 3 Sky
run_case \
  "batch01_flood_vs_335_cover3sky_v3" \
  "georgia-off:26:gun-bunch:flood" \
  "3-3-5-tite-def:26:nickel-2-4-load-mug:cover-3-sky" \
  "data/manifests/3-3-5-tite-def_manifest.jsonl"

# 2) Mesh Spot vs Cover 2 Man
run_case \
  "batch02_mesh_vs_335_cover2man_v3" \
  "georgia-off:26:gun-bunch:mesh_spot" \
  "3-3-5-tite-def:26:nickel-2-4-load:cover-2-man" \
  "data/manifests/3-3-5-tite-def_manifest.jsonl"

# 3) Stick vs Quarters
run_case \
  "batch03_stick_vs_335_quarters_v3" \
  "georgia-off:26:singleback-y-off-trips:stick" \
  "3-3-5-tite-def:26:3-4-tite:cover-4-quarters" \
  "data/manifests/3-3-5-tite-def_manifest.jsonl"

# 4) Verticals vs Tampa 2
run_case \
  "batch04_verticals_vs_425_tampa2_v3" \
  "georgia-off:26:gun-trips-te-offset-wk:verticals" \
  "4-2-5-def:26:nickel-over:tampa-2" \
  "data/manifests/4-2-5-def_manifest.jsonl"

# 5) Inside Zone vs Edge Blitz 0
run_case \
  "batch05_insidezone_vs_425_edgeblitz0_v3" \
  "georgia-off:26:gun-spread-flex-wk:inside_zone" \
  "4-2-5-def:26:3-3-5-over-flex:edge-blitz-0" \
  "data/manifests/4-2-5-def_manifest.jsonl"

echo "done: outputs written under ${OUT_DIR}"
