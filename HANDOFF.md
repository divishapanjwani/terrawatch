# Handoff — TerraWatch

You're picking this up at the start of **Phase 3**. This file is the
practical "get running and know what's real" doc. `README.md` has the
fuller technical writeup per phase; `PROJECT_BRIEF.md` is the original
spec; `terrawatch-phase-prompts.md` has the Phase 3-8 prompts to paste
into Claude Code one at a time.

## Status: Phases 1-2 done

### What works

- Upload two GeoTIFFs (drag-and-drop or click), backend aligns the after
  image onto the before image's exact pixel grid, generates matching
  preview PNGs, and runs the detection pipeline in the background with
  real progress steps (`validating → detecting → filtering → vectorizing
  → done`), polled by the frontend.
- **Engine 1 (TinyCD)** is wired in and loads correctly — a real
  pretrained Siamese CNN (`AndreaCodegoni/Tiny_model_4_CD`, trained on
  LEVIR-CD). Falls back to a spectral baseline if the weights file is
  missing.
- Full geo pipeline: morphological filtering → `rasterio.features.shapes`
  vectorization → simplify → per-polygon attributes (area in a correctly
  resolved projected CRS, change magnitude, confidence, centroid lat/lon,
  severity tier) → GeoJSON (EPSG:4326) + GeoPackage (native CRS) export.
- Split-view swipe map with severity-colored polygon layers, legend,
  click-to-select detail panel.
- 14 unit tests pass (`backend/tests/`) — area-from-geometry, centroid
  conversion, severity formula.

### What doesn't work / isn't built yet — read this before Phase 3

**TinyCD (Engine 1) is effectively blind on two of your three test
inputs**, and this is exactly why Phase 3 (Engine 2) is critical, not
optional polish:

| Input | TinyCD result | Why |
|---|---|---|
| LEVIR-CD official test split (128 real aerial photo pairs, 0.5m) | **F1 0.914** (precision 0.929, recall 0.899) | This is what it was trained on. Works great. |
| `terrawatch-test-pair/before.tif` + `after.tif` (synthetic, 1m, UTM) | **0 detections** — max probability 0.12, never crosses the 0.5 threshold | Deliberately cartoon-like synthetic imagery; out of TinyCD's training distribution. The pair's own README warns about this. |
| Real Sentinel-2 pair (10m, fetched via `scripts/fetch_real_test_pair.py`) | **0 detections** | TinyCD is trained on ~0.5m imagery. 10m/pixel is a 20x resolution gap. This is the exact problem Engine 2 (OSCD-trained U-Net, per `PROJECT_BRIEF.md` section 4) exists to solve. |

So: **the geo pipeline (alignment, preview, vectorization, area/centroid
math, severity, export, map) is solid and tested. The detection itself
only works on sub-meter RGB imagery right now.** Phase 3's Engine 2 +
auto engine-selection (by resolution/band count) is what makes the system
actually useful on Sentinel-2, which is the primary data source for the
Wayanad demo (Phase 6).

Also not built: false-alarm filtering (Phase 4 — on the synthetic test
pair, the spectral baseline currently flags all 3 planted fakes as real
changes), population/facility/priority-queue impact analysis (Phase 5),
auto-fetch UI (Phase 6 — `scripts/fetch_real_test_pair.py` is a one-off
script, not a UI feature), LLM summaries/ask-the-map (Phase 7), reports/
alerts (Phase 8).

## Setup from a fresh clone

### Prerequisites

- **Python 3.11** — not 3.13/3.14. `rasterio`, `torch`, and `geopandas`
  don't ship wheels for the newest Python yet; you'll hit build failures
  or missing-wheel errors. On macOS: `brew install python@3.11`.
- **Node.js 20+** and npm.

### Backend

```bash
cd backend
/opt/homebrew/bin/python3.11 -m venv venv   # or: python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Download Engine 1's weights (1.3 MB, direct GitHub link, no account/manual
click needed):

```bash
mkdir -p models/tinycd
curl -L -o models/tinycd/levir_best.pth \
  https://github.com/AndreaCodegoni/Tiny_model_4_CD/raw/main/pretrained_models/levir_best.pth
```

If you skip this, the pipeline still runs — it silently falls back to the
spectral baseline engine. Check `GET /api/analyses/{id}` — the `engine`
field tells you which one actually ran (`siamese_levir_cd` vs
`spectral_baseline`).

Start the API (use `--reload`, see Gotcha #4 below):

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Backend: **http://127.0.0.1:8000** — health check at `/api/health`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: **http://localhost:5173** — expects the backend at
`http://127.0.0.1:8000` (hardcoded in `frontend/src/api/client.ts`,
`API_BASE`).

### Smoke test

Upload `terrawatch-test-pair/before.tif` and `terrawatch-test-pair/after.tif`
through the UI. It should reach `status: ready` with `engine:
siamese_levir_cd` and `polygon_count: 0` (see table above — that's
expected, not broken).

## Running tests

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -v
```

14 tests, should all pass in well under a second (no model loading
involved — they test geometry/severity math directly with synthetic
fixtures).

### `check_results.py` (acceptance test against the planted answer key)

```bash
# with the backend running, upload terrawatch-test-pair/before.tif + after.tif
# via the UI, then grab the analysis_id from the response/URL:
curl "http://127.0.0.1:8000/api/analyses/<id>/export?format=geojson" -o export.geojson
python terrawatch-test-pair/check_results.py export.geojson
```

Prints precision/recall/F1, which planted changes (R1-R5) were found vs
missed with area/centroid error, and whether each planted fake (F1-F3) got
flagged. With Engine 1 as-is you'll see 0 found and 0 flagged (nothing
crosses the detection threshold at all) — to see the geo-pipeline math
actually exercised, see `README.md`'s "Acceptance test" section for how to
force the spectral baseline for comparison.

### LEVIR-CD quality eval

```bash
pip install huggingface_hub
python -c "
from huggingface_hub import hf_hub_download
hf_hub_download('satellite-image-deep-learning/LEVIR-CD', 'test.zip',
                 repo_type='dataset', local_dir='backend/data/levir_cd')
"
cd backend/data/levir_cd && unzip test.zip && cd ../../..
cd backend && source venv/bin/activate
python scripts/evaluate.py          # full 128-image test split, ~5 min on CPU
python scripts/evaluate.py --limit 10   # quick spot-check
```

## Gotchas we hit (so you don't re-discover them)

1. **Vite + maplibre-gl: "Worker failed to load" in dev mode.** MapLibre's
   web worker silently fails under Vite's dev-server dependency
   pre-bundling. Fix already in place in `frontend/vite.config.ts`:
   ```ts
   optimizeDeps: { exclude: ['maplibre-gl'] }
   ```
   If you ever see map layers (especially GeoJSON/vector ones) not
   rendering with no visible error, check the browser console for this
   first — it's silent-ish and easy to miss.

2. **Area must be computed in a projected CRS, never in degrees.**
   `app/geo/vectorize.py`'s `resolve_area_crs()` uses the native CRS if
   it's already projected (our test data and most real satellite products
   are UTM), otherwise resolves the correct UTM zone via
   `pyproj.database.query_utm_crs_info()` on the scene's bounds and
   reprojects the mask/prob/magnitude arrays onto that grid before
   vectorizing. Centroids are always converted back to EPSG:4326 lat/lon
   for display/storage — don't confuse the two CRSs when extending this.

3. **Preview color stretch must be shared, not per-image/per-band.**
   Computing a separate 2nd-98th-percentile stretch for each band and each
   image independently is what caused the original magenta/washed-out
   preview bug. `app/geo/preview.py` computes ONE stretch from both
   images' RGB pixels combined and applies it identically to both — and
   skips stretching entirely for uint8 input (already 0-255). If you touch
   preview generation, preserve this or the before/after brightness won't
   be comparable.

4. **`uvicorn` without `--reload` silently serves stale code.** We lost
   ~15 minutes to this: edited `siamese.py` to wire in real weights, hit
   the API, and it silently kept using the old placeholder (engine showed
   `spectral_baseline` with no error) because the running process had the
   old module in memory. Always run the dev server with `--reload`, or
   restart it explicitly after backend code changes.

5. **The after image is always resampled onto the before image's exact
   grid** (`app/geo/align.py`) before anything else — detection, preview
   generation, and polygon vectorization all operate on this single
   aligned grid. If before/after have different native resolution or
   slightly different footprints, this is where that gets reconciled. Push
   any new per-pixel logic through `AlignedPair`, don't reproject
   independently elsewhere.

6. **LEVIR-CD has no georeferencing — don't run it through the geo
   pipeline.** `scripts/evaluate.py` calls
   `siamese.predict_arrays(before, after, "uint8")` directly on plain
   numpy arrays loaded from PNGs, bypassing `AlignedPair`/CRS logic
   entirely. Keep that separation — it's there specifically because mixing
   LEVIR-CD (no CRS) into the geo pipeline doesn't make sense.

7. **Python 3.14 (the system default on this machine) silently has no
   wheels for rasterio/geopandas/torch** — pip install either fails outright
   or tries to build from source and breaks in confusing ways. Use the
   Python 3.11 venv; don't try to fix this by installing newer versions.

## Folder structure

```
terrawatch/
  PROJECT_BRIEF.md              Original full spec
  terrawatch-phase-prompts.md   Phase 3-8 prompts (paste one at a time)
  README.md                     Phase-by-phase technical writeup
  HANDOFF.md                    This file
  .env.example                  ANTHROPIC_API_KEY, LLM_MODEL, TELEGRAM_* (all optional, Phase 7-8)

  terrawatch-test-pair/         Synthetic UTM test pair + answer key + check_results.py
    before.tif / after.tif        4-band (R,G,B,NIR) uint8, EPSG:32643, 1m/px
    before_rgb.tif / after_rgb.tif   same scene, RGB only
    after_misaligned_3px.tif      shifted 3m — for the Phase 4 alignment-warning test
    answer_key.geojson/.json      planted change ground truth
    check_results.py              scoring script, see "Running tests" above

  backend/                      FastAPI app (Python 3.11)
    app/
      main.py                     App entrypoint, CORS
      db.py                       SQLModel engine/session, data dir paths
      models.py                   Analysis table
      config.py                   Tunable thresholds (detection, min area, severity tiers)
      api/
        analyses.py                 All /api/analyses* routes
      geo/
        align.py                    Co-register after onto before's grid -> AlignedPair
        preview.py                  AlignedPair -> matching PNG previews (shared stretch, EPSG:4326)
        morphology.py                Threshold -> opening/closing -> min-area filter
        vectorize.py                 Mask -> polygons w/ area (projected CRS) + centroid (4326)
        export.py                    GeoDataFrame -> GeoJSON/GPKG
      engines/
        common.py                    Shared spectral magnitude calc
        spectral.py                  Fallback/baseline engine (NOT primary)
        siamese.py                   Engine 1: TinyCD wrapper, tiled inference
        tinycd_src/                  Vendored TinyCD model code (change_classifier.py, layers.py)
      pipeline/
        run.py                       Orchestrates: align -> detect -> filter -> vectorize -> export
        severity.py                  sev_score formula + tier assignment
      impact/ llm/ reports/ alerts/  Empty — Phase 5, 7, 8
    scripts/
      evaluate.py                    Engine 1 vs LEVIR-CD test split
      fetch_real_test_pair.py        One-off Sentinel-2 fetch via Planetary Computer
    tests/                         pytest unit tests (geometry, severity)
    models/tinycd/levir_best.pth   Gitignored — download step above
    data/                          Gitignored except population/.gitkeep — uploads, previews,
                                    sqlite db, and any fetched datasets (levir_cd/, real_test_pair/, etc.)

  frontend/                     React + Vite + TypeScript + MapLibre GL
    src/
      App.tsx                     Top-level layout, upload form, progress, export buttons
      api/client.ts                Backend API client, all endpoint URLs/types
      map/CompareMap.tsx            Synced swipe map, polygon layers, legend
      panels/
        FileDropSlot.tsx             Drag-and-drop upload slot
        PolygonPanel.tsx              Selected-polygon detail side panel
      styles/tokens.css             Design tokens (colors, type scale, severity palette)
    vite.config.ts                 Has the maplibre-gl optimizeDeps fix — see Gotcha #1
```
