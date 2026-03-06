# Route Recognition MVP

This plan improves pre-AI route extraction in progressive layers. It keeps the current heuristic parser as a baseline, then upgrades localization with a detector model once labeled data is available.

## Model choice

- Use a detection model (YOLO family) for route/label localization.
- Keep OCR-specific models for text reading.
- Do not use LLaMA as the core OCR/vision detector in this stage.

## Pipeline shape

1. Preprocess play art: crop UI regions, autocontrast, denoise, sharpen.
2. Detect route regions and assignment-label regions:
   - Phase 1 baseline: current heuristic parser (`pipeline/route_parser.py`)
   - Phase 2 upgrade: YOLO route/label detector
3. OCR text on detected label boxes (Tesseract or OCR model swap later).
4. Canonicalize outputs using football route families:
   - `fade_or_go`
   - `flat_or_hitch`
   - `cross_or_over`
   - `in_or_out_break`
5. Feed normalized route evidence to downstream AI feedback.

## Dataset loop

1. Build route gold scaffold from manifest:

```bash
./.venv/bin/python scripts/scaffold_route_gold.py \
  --manifest data/manifests/georgia-off_manifest.jsonl \
  --offense-only \
  --limit 200 \
  --out data/qa/route_gold.jsonl
```

2. Optional: seed labels from current parser (faster review):

```bash
./.venv/bin/python scripts/scaffold_route_gold.py \
  --manifest data/manifests/georgia-off_manifest.jsonl \
  --offense-only \
  --limit 200 \
  --seed-with-predictions \
  --route-detector-backend yolo \
  --route-yolo-model models/routes_yolo.pt \
  --route-parser-dir data/qa/route_parser_debug \
  --out data/qa/route_gold_seeded.jsonl
```

3. Human review and correction in JSONL.

4. Evaluate parser against route gold:

```bash
./.venv/bin/python scripts/eval_route_parser.py \
  --gold data/qa/route_gold_seeded.jsonl \
  --route-detector-backend yolo \
  --route-yolo-model models/routes_yolo.pt \
  --route-parser-dir data/qa/route_parser_eval \
  --min-pass-rate 0.55
```

## Metrics

- Primary metric: `play_pass_rate` across `primary_route_family` + `secondary_route_family`
- Field metrics: coverage and accuracy per route field
- Error buckets: confusion map (for example `cross_or_over->in_or_out_break`)

## Two-week execution target

- Days 1-3: label 200 offense plays, establish baseline metrics.
- Days 4-7: tune preprocessing and heuristics, relabel edge cases.
- Days 8-10: train first YOLO detector for route/label boxes.
- Days 11-14: integrate YOLO detections into parser path and compare against baseline.

## Integration notes

- Keep evaluator/gold format stable while swapping detector backends.
- Add model-assisted predictions only when they improve both:
  - coverage (fewer `missing`)
  - accuracy (fewer family confusions)
