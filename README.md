# TerraWatch

Satellite change-intelligence platform: upload two co-registered GeoTIFFs
(before/after), detect real changes, filter out false alarms, and turn the
result into attributed map polygons for disaster-response teams and urban
planners.

This README is updated at the end of each build phase. Current status:
**Phase 2 — Core pipeline** complete. All hackathon problem-statement
requirements are met (see the checklist at the bottom). No false-alarm
filtering, impact analysis, or auto-fetch yet — those are Phase 3 onward.

## Repository structure

```
terrawatch/
  backend/          FastAPI app (Python 3.11)
    app/
      api/           API routers
      geo/           align.py (co-register), preview.py, morphology.py, vectorize.py, export.py
      engines/        siamese.py (Engine 1 / TinyCD), spectral.py (baseline), common.py
      pipeline/        run.py (orchestration), severity.py
      impact/ llm/ reports/ alerts/   (empty — later phases)
    scripts/          evaluate.py, fetch_real_test_pair.py
    data/              Runtime data + downloaded eval datasets (gitignored)
    models/            Downloaded model weights go here (gitignored)
    tests/             pytest unit tests
  frontend/          React + Vite + TypeScript + MapLibre GL
    src/
      api/            Backend API client
      map/            CompareMap (before/after swipe, polygon layers, legend)
      panels/         FileDropSlot, PolygonPanel
      styles/         Design tokens (tokens.css)
  .env.example        All optional integration keys
```

## Prerequisites

- **Python 3.11** (not 3.13/3.14 — `rasterio`/`torch`/`geopandas` don't yet
  ship wheels for the newest Python). On macOS: `brew install python@3.11`.
- **Node.js 20+** and npm.

## Setup

### Backend

```bash
cd backend
/opt/homebrew/bin/python3.11 -m venv venv   # or just `python3.11 -m venv venv`
source venv/bin/activate
pip install -r requirements.txt
```

**Download Engine 1's pretrained weights** (TinyCD, trained on LEVIR-CD —
1.3 MB, direct download, no account needed):

```bash
mkdir -p models/tinycd
curl -L -o models/tinycd/levir_best.pth \
  https://github.com/AndreaCodegoni/Tiny_model_4_CD/raw/main/pretrained_models/levir_best.pth
```

If this file is missing, the pipeline automatically falls back to the
spectral baseline engine and still works end to end — it just won't be
using the primary detector.

Run the API:

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The first run creates `backend/data/terrawatch.db` (SQLite) and the
`backend/data/uploads/` / `backend/data/analyses/` directories automatically.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server expects the backend at
`http://127.0.0.1:8000` (see `frontend/src/api/client.ts`).

## What's implemented (Phase 1 + 2)

### Upload & display (Phase 1)

- `POST /api/analyses` — upload a `before` and `after` GeoTIFF (multipart,
  drag-and-drop or click-to-choose, `.tif`/`.tiff`), returns an `analysis_id`
  and kicks off background processing.
- The **after** raster is resampled onto the **before** raster's exact grid
  (`app/geo/align.py`) before anything else, so detection, previews, and
  polygon areas are all computed on one shared, pixel-aligned grid.
- Preview PNGs use bands 1-3 (R, G, B) only — never NIR — with one shared
  color stretch computed from both images combined (uint8 input is used
  as-is, no stretch). Both previews are reprojected to EPSG:4326 from the
  same target transform, so they have identical bounds.
- Frontend renders a **before/after split-view map**: two synced MapLibre GL
  maps with a draggable swipe divider.

### Change-detection pipeline (Phase 2)

- **Engine 1 (primary): TinyCD**, a pretrained Siamese CNN trained on
  LEVIR-CD (`AndreaCodegoni/Tiny_model_4_CD`). Tiled 256x256 inference with
  32px overlap, stitched by averaging. Falls back to a spectral baseline
  (`app/engines/spectral.py`, normalized band-difference magnitude) if the
  weights aren't present — this baseline is intentionally simple and is
  **not** the main detector, just a fallback/comparison.
- Detection runs on the **native aligned grid** (not the EPSG:4326 preview
  reprojection).
- Morphological opening + closing, then drop objects below a configurable
  minimum area (`app/config.py: MIN_AREA_M2`, default 30 m²).
- Contour-to-polygon vectorization via `rasterio.features.shapes`, then
  simplified.
- **Area is computed in a projected (meters) CRS** — the native CRS if
  already projected, otherwise the correct UTM zone resolved via pyproj.
  Centroids are stored as EPSG:4326 lat/lon.
- Per-polygon attributes: `id, area_m2, change_magnitude, confidence,
  centroid_lat, centroid_lon, severity, sev_score, engine, status`.
- Severity: `sev_score = 0.5·norm(area_m2) + 0.5·norm(change_magnitude)`,
  High ≥ 0.66, Medium ≥ 0.33, else Low (norm = min-max over this analysis's
  polygons). Shown in the UI as a legend tooltip and in the polygon detail
  panel.
- Map: severity-colored polygon layers (High #C0392B, Medium #E67E22, Low
  #F1C40F; ~30% fill + 1.8px outline) on both before/after maps, a legend,
  click-to-select with a highlight outline and a detail side panel.
- `GET /api/analyses/{id}/export?format=geojson|gpkg` — GeoJSON is always
  EPSG:4326; GeoPackage is in the native/area-projected CRS. Both have
  download buttons in the UI.
- Real step-by-step progress (`validating → detecting → filtering →
  vectorizing → done`), shown in the left panel while processing.

## Testing

### Unit tests

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -v
```

Covers area-from-geometry calculation against a known rectangle, centroid
lat/lon conversion against an independent pyproj calculation, confidence/
magnitude aggregation, and the severity scoring formula (normalization,
tier boundaries, equal area/magnitude weighting).

### Acceptance test against a planted-change answer key

A synthetic UTM-projected test pair with known changes and a scoring
script (`terrawatch-test-pair/` in the repo root) is the fastest way to
sanity-check the whole geo pipeline (areas, centroids, severity, export).
Point `check_results.py` at an exported GeoJSON:

```bash
# upload terrawatch-test-pair/before.tif + after.tif via the UI, then:
curl "http://127.0.0.1:8000/api/analyses/<id>/export?format=geojson" -o export.geojson
python terrawatch-test-pair/check_results.py export.geojson
```

**Honest result on this synthetic pair:** TinyCD (Engine 1) finds **nothing**
on it (max probability 0.12, all below the 0.5 threshold) — it's trained on
real LEVIR-CD aerial photos and this pair is deliberately cartoon-like, which
the test pair's own README anticipates. The spectral baseline, run
separately for comparison, finds R1-R4 correctly (precision 0.38, recall
0.96 — matches the reference naive-subtract baseline almost exactly) with
areas within ±33% and centroids within 5m, but also flags all three planted
fakes (expected — the false-alarm filter is Phase 4). Nothing was tuned to
this specific pair.

### Model quality: Engine 1 on the real LEVIR-CD test split

```bash
# download LEVIR-CD's official test split (496 MB, from a HF mirror,
# scriptable — no manual click needed):
pip install huggingface_hub
python -c "
from huggingface_hub import hf_hub_download
hf_hub_download('satellite-image-deep-learning/LEVIR-CD', 'test.zip',
                 repo_type='dataset', local_dir='backend/data/levir_cd')
"
cd backend/data/levir_cd && unzip test.zip && cd ../../..

cd backend && source venv/bin/activate
python scripts/evaluate.py
```

Evaluates as plain images (LEVIR-CD has no georeferencing — this does NOT
go through the geo pipeline). **Result on the full 128-image test split:
precision 0.929, recall 0.899, F1 0.914, accuracy 0.991** — consistent with
TinyCD's published numbers, and the stark contrast with the synthetic-pair
result above confirms the earlier near-zero score is a real-vs-synthetic
domain gap, not a bug. Results are written to
`backend/data/levir_cd/eval_results.json`.

### Real georeferenced pair

`scripts/fetch_real_test_pair.py` pulls two low-cloud Sentinel-2 L2A scenes
(Feb 2019 vs Feb 2024, near Pune) from Microsoft Planetary Computer's public
STAC API — no API key needed:

```bash
cd backend && source venv/bin/activate
python scripts/fetch_real_test_pair.py
# uploads data/real_test_pair/{before,after}.tif via the UI
```

This pair shows dramatic real urban growth (bare land → dense new
development) and the full geo pipeline (fetch → align → reproject → color
→ swipe map) renders it correctly. **Engine 1 finds 0 polygons here** —
expected: TinyCD is trained on ~0.5m imagery and Sentinel-2 is 10m/pixel,
exactly the resolution gap the project spec calls for Engine 2 (an
OSCD-trained U-Net for Sentinel-2) to cover, in Phase 3.

## Hackathon problem-statement checklist

| # | Requirement | Status |
|---|---|---|
| 1 | Two co-registered, orthorectified GeoTIFF inputs | ✅ Upload accepts any two GeoTIFFs; `app/geo/align.py` resamples the after image onto the before image's exact grid regardless of input alignment |
| 2 | AI difference mapping (Siamese CNN / ViT / spectral+U-Net) | ✅ Engine 1 = TinyCD, a pretrained Siamese CNN (LEVIR-CD). Spectral-index baseline present as fallback/comparison, not primary |
| 3 | Morphological filtering | ✅ `app/geo/morphology.py` — opening + closing, then minimum-area filter (configurable, m²) |
| 4 | Rasterio contour-to-polygon vectorization | ✅ `app/geo/vectorize.py` — `rasterio.features.shapes` on the cleaned mask, then simplified |
| 5 | Polygons with area (m²), change magnitude, centroid | ✅ Area computed in a projected CRS (native if projected, else resolved UTM zone); centroid stored as EPSG:4326 lat/lon |
| 6 | GeoJSON + GeoPackage export, severity tiers | ✅ `GET /api/analyses/{id}/export?format=geojson\|gpkg` + download buttons; severity formula shown in UI |
| 7 | Interactive split-view before/after web map | ✅ MapLibre GL, synced swipe compare, severity-colored polygon layers, legend, click-to-select detail panel |

## Known limitations going into Phase 3+

- No false-alarm filter yet (vegetation/shadow/cloud rejection) — Phase 4.
- No Engine 2 (OSCD-trained U-Net for Sentinel-2/multispectral) — Phase 3.
  Engine 1 is RGB-only and tuned for sub-meter imagery; it will under-detect
  on 10m multispectral data until Engine 2 exists.
- No population/facility/priority-queue impact analysis yet — Phase 5.
- No auto-fetch UI (the Sentinel-2 fetch above is a one-off script) — Phase 6.
