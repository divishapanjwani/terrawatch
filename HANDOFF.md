# Handoff — TerraWatch

You're picking this up at the start of **Phase 4**. This file is the
practical "get running and know what's real" doc. `README.md` has the
fuller technical writeup per phase; `PROJECT_BRIEF.md` is the original
spec; `terrawatch-phase-prompts.md` has the Phase 4-8 prompts to paste
into Claude Code one at a time.

## Status: Phases 1-3 done

### What works

- Upload two GeoTIFFs (drag-and-drop or click), backend aligns the after
  image onto the before image's exact pixel grid, generates matching
  preview PNGs, and runs the detection pipeline in the background with
  real progress steps, polled by the frontend.
- **Two trained engines, auto-selected by resolution/band count, with a
  safety-net fallback — see "Phase 3" below.** Full geo pipeline:
  morphological filtering → `rasterio.features.shapes` vectorization →
  simplify → per-polygon attributes (area in a correctly resolved
  projected CRS, change magnitude, confidence, centroid lat/lon, severity
  tier) → GeoJSON (EPSG:4326) + GeoPackage (native CRS) export.
- Split-view swipe map with severity-colored polygon layers, legend,
  click-to-select detail panel, an Engine dropdown (Auto/TinyCD/Engine
  2/Spectral baseline), and a real-numbers Accuracy page.
- 22 unit tests pass (`backend/tests/`) — area-from-geometry, centroid
  conversion, severity formula, engine auto-selection rules (including a
  regression test for a real bug — see below).

### Phase 3: what changed, and the honest state of each engine

**The core problem:** TinyCD (Engine 1) is trained on 0.5m LEVIR-CD photos
and was finding 0 changes on both the synthetic test pair and real
Sentinel-2 — the map was empty on our actual demo data. Phase 3 built
Engine 2 (a small U-Net trained on OSCD) and the auto-selection logic that
routes each input to whichever engine actually fits its resolution.

**1. Safety net + auto-selection** (`app/engines/select.py`): resolution
≤2m AND <5 bands → TinyCD; everything coarser or truly multispectral →
Engine 2, falling back to the spectral baseline if Engine 2 is
unavailable. **This fallback never crosses the other direction** — coarse
input never falls back to TinyCD, even if TinyCD is available and Engine
2 isn't. We hit this exact bug during development (see Gotcha #8) and
there's a regression test for it (`tests/test_engine_select.py`).

**2. Engine 2 (`app/engines/engine2.py` + `app/engines/unet_model.py`)**
is a real trained model, not a stub: a ~1.9M-param U-Net, input = stacked
before/after 5-band (R,G,B,NIR,SWIR) reflectance + ΔNDVI/ΔNDWI/ΔNDBI/Δ
brightness (14 channels total), trained on OSCD's 14-city train split
(`scripts/train_oscd_unet.py`, ~4 min on this Mac's MPS GPU for 4000
steps). Weights at `models/engine2/unet_oscd.pth` (gitignored, retrain
with the script below).

**3. Real evaluation numbers** (`scripts/evaluate.py`, written to
`data/eval_results.json`, served at `GET /api/metrics`, shown on the
Accuracy page):

| Engine | Dataset | N | Precision | Recall | F1 | Accuracy | FPR |
|---|---|---|---|---|---|---|---|
| TinyCD (Engine 1) | LEVIR-CD test split | 128 | 92.9% | 89.9% | **0.914** | 99.1% | 0.4% |
| Engine 2 (U-Net) | OSCD test split | 10 | 19.6% | 93.5% | **0.324** | 79.8% | 20.9% |
| Spectral baseline | OSCD test split | 10 | 15.8% | 59.2% | **0.250** | 81.6% | 17.1% |

**Be honest about Engine 2 with your teammate/demo audience:** F1 0.324 is
real and it does genuinely beat the spectral baseline it's meant to
replace, but it's a quick ~4-minute training run on a small (24-scene)
dataset — high recall, low precision (lots of false positives). It is
good enough to light up real structure on real imagery (see the Wayanad
result below) but is not "done." More steps, data augmentation, or a
larger architecture would likely help if you want to push on it; that
wasn't the Phase 3 goal (the goal was "make the map not empty on
Sentinel-2," which is achieved).

**4. Real-world tests, not just benchmarks** (scripts + their outputs are
reproducible but the imagery itself is gitignored — see Setup below):

- **Pune, India, 2019 vs 2024** (`scripts/fetch_real_test_pair.py`,
  updated in Phase 3 to pull 5 bands incl. SWIR and keep raw reflectance
  instead of rescaling to uint8): Auto correctly selects Engine 2 (10m
  pixel size), finds 4 polygons outlining real new construction visible in
  the imagery.
- **Wayanad landslide, Kerala (30 July 2024), Mundakkai/Chooralmala**
  (`scripts/fetch_wayanad.py`): before = 2024-01-31 (0.99% cloud), after =
  2024-12-16 (0.01% cloud) — both essentially cloud-free. Auto selects
  Engine 2. **The landslide debris path is genuinely detected** — multiple
  polygons cluster tightly around the known headscarp coordinates
  (11.465°N, 76.135°E, from a peer-reviewed post-event survey) and trace
  the flow path toward Mundakkai village; visually, the outlined polygon
  follows the bare-soil scar almost exactly. 187 polygons total, most of
  which are smaller false positives scattered across vegetation (expected
  given Engine 2's 19.6% precision) — the landslide itself is the obvious,
  large, high/medium-severity cluster, not hidden among noise.
- **Barbuda, Hurricane Irma (high-res, OpenAerialMap)**
  (`scripts/fetch_oam_barbuda.py`): WorldView-2 2014-04-24 (~0.48m/px) vs
  a RescUAV drone survey 2017-09-21 (~days after Irma made landfall).
  Source verified directly via `api.openaerialmap.org`, not trusted from
  secondhand research — the first candidate "before" tile the research
  turned up doesn't actually overlap the after tile at all (looked right
  from its nominal bbox, was wrong), and the second candidate's nominal
  bbox overlaps but its *real pixel data* doesn't fully cover it (satellite
  mosaic tiles are padded to a grid with large blank regions) — see
  Gotcha #9. Auto correctly selects TinyCD (0.49m/px); finds 6
  building-scale polygons (48-104 m², confidence 0.72-0.88).

Also not built yet: false-alarm filtering (next up — Phase 4; on the
synthetic test pair, the spectral baseline currently flags all 3 planted
fakes as real changes), population/facility/priority-queue impact analysis
(Phase 5), auto-fetch UI (Phase 6 — the fetch scripts here are one-offs,
not a UI feature), LLM summaries/ask-the-map (Phase 7), reports/alerts
(Phase 8).

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

**Download Engine 1's weights** (TinyCD, 1.3 MB, direct GitHub link, no
account/manual click needed):

```bash
mkdir -p models/tinycd
curl -L -o models/tinycd/levir_best.pth \
  https://github.com/AndreaCodegoni/Tiny_model_4_CD/raw/main/pretrained_models/levir_best.pth
```

**Download OSCD and train Engine 2** (optional — the app works without
this, auto-selection just falls back to the spectral baseline on
Sentinel-2-class input):

```bash
mkdir -p data/oscd_raw
cd data/oscd_raw
curl -sL -o images.zip "https://hf.co/datasets/hkristen/oscd/resolve/main/Onera%20Satellite%20Change%20Detection%20dataset%20-%20Images.zip"
curl -sL -o train_labels.zip "https://hf.co/datasets/hkristen/oscd/resolve/main/Onera%20Satellite%20Change%20Detection%20dataset%20-%20Train%20Labels.zip"
curl -sL -o test_labels.zip "https://hf.co/datasets/hkristen/oscd/resolve/main/Onera%20Satellite%20Change%20Detection%20dataset%20-%20Test%20Labels.zip"
unzip -q images.zip -d images && unzip -q train_labels.zip -d train_labels && unzip -q test_labels.zip -d test_labels
cd ../..
python scripts/train_oscd_unet.py          # ~4 min on Apple Silicon MPS, longer on CPU
```

No Kaggle account needed — this is a Hugging Face mirror of the original
OSCD release that torchgeo's own dataset loader uses, found by checking
torchgeo's source rather than trusting the Kaggle link in `PROJECT_BRIEF.md`
section 3 at face value.

If you skip either model, the pipeline still runs — it silently falls back
per the auto-selection rule. Check `GET /api/analyses/{id}` — `engine`,
`engine_key`, and `engine_fell_back` tell you exactly what ran and whether
it was a fallback.

Start the API (use `--reload`, see Gotcha #4):

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
through the UI with Engine = Auto. It should reach `status: ready` with
`engine: siamese_levir_cd`, `engine_key: tinycd`, and `polygon_count: 0`
(expected — see the Phase 2 note in README.md; this synthetic pair is
genuinely out of TinyCD's training distribution).

## Running tests

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -v
```

22 tests, run in under a second (no model loading — pure geometry/severity/
engine-selection logic against synthetic fixtures).

### `check_results.py` (acceptance test against the planted answer key)

```bash
# with the backend running, upload terrawatch-test-pair/before.tif + after.tif
# via the UI with Engine = "Spectral baseline" (TinyCD/Engine 2 both score
# 0 on this synthetic pair — see README.md), then:
curl "http://127.0.0.1:8000/api/analyses/<id>/export?format=geojson" -o export.geojson
python terrawatch-test-pair/check_results.py export.geojson
```

With the spectral baseline forced: R1-R4 found (areas within ±33%,
centroids within 5m), R5 (16 m² shed) missed (expected, below the min-area
filter), all 3 planted fakes (F1-F3) flagged as false alarms (expected —
the false-alarm filter is Phase 4, next up).

### Evaluation (`scripts/evaluate.py`)

```bash
cd backend && source venv/bin/activate
python scripts/evaluate.py levircd                       # TinyCD vs LEVIR-CD (needs LEVIR-CD, see README.md)
python scripts/evaluate.py oscd --engine engine2          # Engine 2 vs OSCD (needs OSCD + trained weights)
python scripts/evaluate.py oscd --engine spectral         # spectral baseline vs OSCD, for comparison
```

Each upserts into `data/eval_results.json` (by engine+dataset), which
`GET /api/metrics` and the frontend Accuracy page read directly.

### Real-imagery test scripts

```bash
python scripts/fetch_real_test_pair.py   # Pune, India — 5-band Sentinel-2, 2019 vs 2024
python scripts/fetch_wayanad.py          # Wayanad landslide, Kerala — Sentinel-2, Jan vs Dec 2024
python scripts/fetch_oam_barbuda.py      # Barbuda, Hurricane Irma — high-res OpenAerialMap, 2014 vs 2017
```

All three need network access (Planetary Computer STAC API / OpenAerialMap
S3, both public/no-auth) and write into `data/` (gitignored). Upload the
resulting `before.tif`/`after.tif` pairs through the UI same as any other
pair.

## Gotchas we hit (so you don't re-discover them)

1. **Vite + maplibre-gl: "Worker failed to load" in dev mode.** MapLibre's
   web worker silently fails under Vite's dev-server dependency
   pre-bundling. Fix already in place in `frontend/vite.config.ts`:
   ```ts
   optimizeDeps: { exclude: ['maplibre-gl'] }
   ```

2. **Area must be computed in a projected CRS, never in degrees.**
   `app/geo/vectorize.py`'s `resolve_area_crs()` uses the native CRS if
   it's already projected, otherwise resolves the correct UTM zone via
   `pyproj.database.query_utm_crs_info()`. Centroids are always converted
   back to EPSG:4326 lat/lon for display/storage.

3. **Preview color stretch must be shared, not per-image/per-band.**
   `app/geo/preview.py` computes ONE stretch from both images' RGB pixels
   combined and applies it identically to both; uint8 input is used as-is
   with no stretch.

4. **`uvicorn` without `--reload` silently serves stale code.** Always run
   the dev server with `--reload`, or restart it explicitly after backend
   code changes — we lost real time to this twice across two phases now.

5. **The after image is always resampled onto the before image's exact
   grid** (`app/geo/align.py`) before anything else. Push any new
   per-pixel logic through `AlignedPair`, don't reproject independently
   elsewhere.

6. **LEVIR-CD and OSCD have no georeferencing — don't run either through
   the geo pipeline.** `scripts/evaluate.py` calls `*.predict_arrays(...)`
   directly on plain numpy arrays, bypassing `AlignedPair`/CRS logic
   entirely (`scripts/oscd_data.py` documents OSCD's on-disk layout). Keep
   that separation.

7. **Python 3.14 (the system default on this machine) silently has no
   wheels for rasterio/geopandas/torch.** Use the Python 3.11 venv.

8. **Engine fallback must never cross the resolution boundary "upward."**
   A real bug during Phase 3: the auto-selection fallback chain, when
   Engine 2 was unavailable, fell back to TinyCD on 10m Sentinel-2 input
   — exactly what "never run TinyCD on Sentinel-2" forbids. Root cause:
   a generic "try the other trained engine" fallback didn't distinguish
   direction. Fixed in `app/engines/select.py::resolve_engine` — coarse
   input falls straight to the spectral baseline if Engine 2 is
   unavailable, never to TinyCD. Covered by
   `tests/test_engine_select.py::test_auto_never_falls_back_to_tinycd_on_coarse_input_when_engine2_unavailable`.
   If you touch the fallback logic, keep that test passing.

9. **Don't trust a tile's nominal bbox as proof it has real pixel data
   there, and don't trust secondhand research on specific dataset URLs
   without verifying overlap yourself.** Satellite image mosaics (OAM,
   Maxar Open Data, etc.) are often padded to a regular tile grid with
   large blank regions outside the actual imaged footprint. We hit this
   building the Barbuda test pair: a "before" tile whose nominal bbox
   fully contained the target area turned out to be all-zero pixels there
   (`scripts/fetch_oam_barbuda.py` now samples a few bands and raises
   loudly instead of writing a silent all-black GeoTIFF if this happens
   again). Separately, the very first before/after tile pair identified by
   research didn't geographically overlap at all despite being described
   as a matching pair — always verify footprint intersection directly
   (`rasterio.warp.transform_bounds` + a manual overlap check) before
   building anything on top of a "found" imagery pair.

## Folder structure

```
terrawatch/
  PROJECT_BRIEF.md              Original full spec
  terrawatch-phase-prompts.md   Phase 3-8 prompts (paste one at a time)
  README.md                     Phase-by-phase technical writeup
  HANDOFF.md                    This file
  .env.example                  ANTHROPIC_API_KEY, LLM_MODEL, TELEGRAM_* (all optional, Phase 7-8)

  terrawatch-test-pair/         Synthetic UTM test pair + answer key + check_results.py

  backend/                      FastAPI app (Python 3.11)
    app/
      main.py                     App entrypoint, CORS, GET /api/metrics
      db.py                       SQLModel engine/session, data dir paths
      models.py                   Analysis table (incl. engine_choice/engine_key/engine_fell_back/pixel_size_m)
      config.py                   Tunable thresholds (detection, min area, severity tiers)
      api/
        analyses.py                 All /api/analyses* routes (engine form field on upload)
      geo/
        align.py                    Co-register after onto before's grid -> AlignedPair
        preview.py                  AlignedPair -> matching PNG previews (shared stretch, EPSG:4326)
        morphology.py                Threshold -> opening/closing -> min-area filter
        vectorize.py                 Mask -> polygons w/ area (projected CRS) + centroid (4326)
        export.py                    GeoDataFrame -> GeoJSON/GPKG
      engines/
        common.py                    Shared spectral magnitude calc
        spectral.py                  Fallback/baseline engine (predict + predict_arrays)
        siamese.py                   Engine 1: TinyCD wrapper, tiled inference
        tinycd_src/                  Vendored TinyCD model code
        unet_model.py                SmallUNet architecture (Engine 2)
        engine2.py                   Engine 2: feature computation (indices) + inference
        select.py                    Auto-selection + fallback chain (THE safety net — see Gotcha #8)
      pipeline/
        run.py                       Orchestrates: align -> select engine -> detect -> filter -> vectorize -> export
        severity.py                  sev_score formula + tier assignment
      impact/ llm/ reports/ alerts/  Empty — Phase 5, 7, 8
    scripts/
      evaluate.py                    levircd/oscd subcommands -> data/eval_results.json
      oscd_data.py                   OSCD on-disk layout loader (train+test)
      train_oscd_unet.py             Trains Engine 2, ~4 min on MPS
      sentinel2_fetch.py             Shared Planetary Computer fetch/clip helper (5-band, raw reflectance)
      fetch_real_test_pair.py        Pune, India
      fetch_wayanad.py               Wayanad landslide, Kerala
      fetch_oam_barbuda.py           Barbuda, Hurricane Irma (high-res, OpenAerialMap)
    tests/                         pytest unit tests (geometry, severity, engine selection)
    models/                        Gitignored — tinycd/levir_best.pth, engine2/unet_oscd.pth
    data/                          Gitignored except population/.gitkeep and eval_results.json —
                                    uploads, previews, sqlite db, oscd_raw/, levir_cd/, real_test_pair/,
                                    wayanad/, oam_barbuda/

  frontend/                     React + Vite + TypeScript + MapLibre GL
    src/
      App.tsx                     Top-level layout, upload form, engine dropdown, progress, export buttons, nav
      api/client.ts                Backend API client, all endpoint URLs/types
      map/CompareMap.tsx            Synced swipe map, polygon layers, legend
      panels/
        FileDropSlot.tsx             Drag-and-drop upload slot
        PolygonPanel.tsx              Selected-polygon detail side panel
      pages/
        AccuracyPage.tsx              Reads GET /api/metrics, renders the real-numbers table
      styles/tokens.css             Design tokens (colors, type scale, severity palette)
    vite.config.ts                 Has the maplibre-gl optimizeDeps fix — see Gotcha #1
```
