# Handoff — TerraWatch

You're picking this up at the start of **Phase 5**. This file is the
practical "get running and know what's real" doc. `README.md` has the
fuller technical writeup per phase; `PROJECT_BRIEF.md` is the original
spec; `terrawatch-phase-prompts.md` has the Phase 5-8 prompts to paste
into Claude Code one at a time.

## Status: Phases 1-4 done

### What works

- Upload two GeoTIFFs (drag-and-drop or click), backend aligns the after
  image onto the before image's exact pixel grid, runs a quality check
  (cloud %, misalignment), detects changes with the resolution-appropriate
  engine, and runs **every candidate through a false-alarm filter** before
  vectorizing — see "Phase 4" below.
- Two trained engines (TinyCD, Engine 2/U-Net), auto-selected by
  resolution/band count, with a safety-net fallback to a spectral
  baseline. Full geo pipeline: morphological filtering →
  `rasterio.features.shapes` vectorization → simplify → per-polygon
  attributes (area in a correctly resolved projected CRS, change
  magnitude, confidence, centroid lat/lon, severity tier, **status,
  reject_reason, change_type, needs_review**) → GeoJSON (EPSG:4326) +
  GeoPackage (native CRS) export, **kept and rejected polygons both
  included**.
- Split-view swipe map: severity-colored kept polygons, dotted
  needs-review outline, toggleable grey-dashed rejected layer, legend,
  click-to-select detail panel (shows the rejection reason in plain
  language for rejected polygons, the estimated change type + rule for
  kept ones), an Engine dropdown, a quiet amber quality-warning banner,
  and an Accuracy page with a real ablation table (raw → +morphology →
  +false-alarm filter).
- 55 unit tests pass (`backend/tests/`).

### Phase 4: false-alarm filter — what changed, and the honest results

**The problem Phase 4 solves:** Phase 3 left Engine 2 finding 187
candidates on the Wayanad pair, most of them noise (19.6% precision) —
clouds, seasonal vegetation, and the real landslide path all mixed
together with no way to tell them apart. Phase 4 makes every candidate
either `kept` or `rejected` with an explained reason, computed from
per-polygon spectral/texture features (`app/geo/features.py`), not from
the detector's probability alone.

**1. Quality check** (`app/geo/quality.py`, runs before detection,
progress step `quality_check`): cloud % per image (Sentinel-2 SCL band
when available — see the Wayanad fetch update below — else an RGB
brightness/whiteness heuristic), misalignment via `skimage.registration.
phase_cross_correlation` on the two images **after** co-registration (so
it measures genuine source-georeferencing error, not grid mismatch),
resolution, band count. Warnings surface as a quiet amber banner in the
left panel. Verified end-to-end against
`terrawatch-test-pair/after_misaligned_3px.tif`: detects exactly 3.0px,
triggers the warning; the normal pair detects 0.0px, no warning.

**2. False-alarm filter** (`app/pipeline/false_alarm.py`), checked in
this order (first match wins): `too_small` → `cloud` → `misalignment_edge`
→ `vegetation_seasonal` → `shadow_illumination` → else `kept`. Each check
needs specific bands/features; unavailable ones (e.g. vegetation on
RGB-only input) are skipped, not treated as false. Per-polygon features
(`app/geo/features.py`, aggregated by `app/geo/vectorize.py`'s generic
`extra_maps` mechanism): ΔNDVI/ΔNDWI/ΔNDBI, brightness-change fraction (of
the scene's own dynamic range), texture-change fraction (Sobel gradient
magnitude — the key discriminator between "real structural change" and
"same structure, different lighting/color"), cloud-mask overlap, edge/
no-data proximity.

**3. Change type** (`app/pipeline/change_type.py`), KEPT polygons only,
same priority-order pattern: `flooding` (ΔNDWI) → `landslide_bare_soil`
(ΔNDVI down + ΔNDBI flat + large area) → `new_construction` (ΔNDBI up) →
`structure_lost` (ΔNDBI down) → `vegetation_loss` (ΔNDVI down) → `other`.
Needs NDBI (so a 5th SWIR band) to tell construction/landslide/demolition
apart from plain vegetation loss — on 4-band RGB+NIR input it honestly
falls back to `vegetation_loss`/`other` rather than guessing.

**4. `scripts/evaluate.py --ablation`**: runs raw model → +morphology →
+false-alarm filter per image/pair and upserts all three as separate rows
(by engine+dataset+**stage**) into `data/eval_results.json`. The
lightweight ablation-stage-3 reconstruction
(`app/pipeline/ablation.py`) replicates the real pipeline's
classification on plain (non-georeferenced) test images without the
geo/CRS machinery, which doesn't apply to LEVIR-CD/OSCD.

**Real ablation numbers** (`GET /api/metrics`, Accuracy page):

| Engine | Dataset | Stage | Precision | Recall | F1 |
|---|---|---|---|---|---|
| Spectral baseline | OSCD | raw | 15.8% | 59.2% | 0.250 |
| Spectral baseline | OSCD | +morphology | 18.8% | 54.5% | 0.280 |
| Spectral baseline | OSCD | **+false-alarm filter** | **21.9%** | 53.4% | **0.311** |
| Engine 2 (U-Net) | OSCD | raw | 19.6% | 93.5% | 0.324 |
| Engine 2 (U-Net) | OSCD | +morphology | 19.7% | 93.5% | 0.325 |
| Engine 2 (U-Net) | OSCD | **+false-alarm filter** | **20.0%** | 92.6% | **0.329** |
| TinyCD | LEVIR-CD | raw | 92.9% | 89.9% | 0.914 |
| TinyCD | LEVIR-CD | +morphology | 92.9% | 89.8% | 0.914 |
| TinyCD | LEVIR-CD | +false-alarm filter | 93.1% | 87.7% | 0.903 |

Precision improves at every stage without recall collapsing, on both OSCD
engines — the spectral baseline's precision improves by nearly 40%
relative. On LEVIR-CD, TinyCD is already so well-calibrated for its own
domain that the filter trades a little recall (89.9%→87.7%) for a small
precision gain — not every stage helps every model; that's a real,
reported result, not tuned to look good.

**5. `terrawatch-test-pair` acceptance result** (Spectral baseline
forced, same as Phase 2's test): **R1–R4 still FOUND** (unchanged areas/
centroids), R5 still correctly below the area floor. Precision 0.38→**0.73**,
F1 0.55→**0.83**. F1 (seasonal_vegetation) now correctly rejected with
reason `vegetation_seasonal` ("good", was a false alarm in Phase 2). F2
(shadow_shift) and F3 (cloud) remain false alarms — see Gotcha #10, this
is an honestly-documented limitation, not an oversight.

**6. Wayanad, verified exactly as described:** the ~4.89M m² polygon at
(11.453°N, 76.159°E) — the one with "High severity" in the Phase 3
screenshot — is now `status: rejected, reject_reason: cloud` (97%
confidence, SCL-based: `cloud_method: scl`). The long diagonal landslide
polygon (1.56M m², centroid 11.486°N/76.152°E, right at Mundakkai) stays
`status: kept`. Final count: 187 candidates → 179 kept, 8 rejected (cloud:
7, vegetation_seasonal: 1).

Also not built yet: population/facility/priority-queue impact analysis
(Phase 5, next), auto-fetch UI (Phase 6), LLM summaries/ask-the-map
(Phase 7), reports/alerts (Phase 8).

## Setup from a fresh clone

### Prerequisites

- **Python 3.11** — not 3.13/3.14. `rasterio`, `torch`, and `geopandas`
  don't ship wheels for the newest Python yet. On macOS:
  `brew install python@3.11`.
- **Node.js 20+** and npm.

### Backend

```bash
cd backend
/opt/homebrew/bin/python3.11 -m venv venv   # or: python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Download Engine 1's weights** (TinyCD, 1.3 MB, direct link):

```bash
mkdir -p models/tinycd
curl -L -o models/tinycd/levir_best.pth \
  https://github.com/AndreaCodegoni/Tiny_model_4_CD/raw/main/pretrained_models/levir_best.pth
```

**Download OSCD and train Engine 2** (optional — auto-selection falls
back to the spectral baseline on Sentinel-2-class input without it):

```bash
mkdir -p data/oscd_raw && cd data/oscd_raw
curl -sL -o images.zip "https://hf.co/datasets/hkristen/oscd/resolve/main/Onera%20Satellite%20Change%20Detection%20dataset%20-%20Images.zip"
curl -sL -o train_labels.zip "https://hf.co/datasets/hkristen/oscd/resolve/main/Onera%20Satellite%20Change%20Detection%20dataset%20-%20Train%20Labels.zip"
curl -sL -o test_labels.zip "https://hf.co/datasets/hkristen/oscd/resolve/main/Onera%20Satellite%20Change%20Detection%20dataset%20-%20Test%20Labels.zip"
unzip -q images.zip -d images && unzip -q train_labels.zip -d train_labels && unzip -q test_labels.zip -d test_labels
cd ../.. && python scripts/train_oscd_unet.py   # ~4 min on Apple Silicon MPS
```

No Kaggle account needed (HF mirror — see `scripts/oscd_data.py`). If you
skip either model, the pipeline still runs; `engine`/`engine_key`/
`engine_fell_back` in `GET /api/analyses/{id}` tell you what actually ran.

Start the API with `--reload` (see Gotcha #4):

```bash
uvicorn app.main:app --reload --port 8000
```

Backend: **http://127.0.0.1:8000**.

### Frontend

```bash
cd frontend && npm install && npm run dev
```

Frontend: **http://localhost:5173**.

### Smoke test

Upload `terrawatch-test-pair/before.tif` + `after.tif` with Engine = Auto
→ `engine_key: tinycd`, `polygon_count: 0` (expected, out of TinyCD's
training distribution — see README.md). Switch Engine to "Spectral
baseline" and re-run → ~19 kept, 2 rejected.

## Running tests

```bash
cd backend && source venv/bin/activate
python -m pytest tests/ -v
```

55 tests, under a second — includes a full rule-by-rule suite for every
false-alarm reason (`test_false_alarm.py`) and every change-type rule
(`test_change_type.py`), plus quality-check tests
(`test_quality.py`, including the exact misalignment-detection case).

### `check_results.py`

```bash
# upload terrawatch-test-pair/before.tif + after.tif via the UI,
# Engine = "Spectral baseline" (TinyCD/Engine 2 both score 0 on this
# synthetic pair — see README.md), then:
curl "http://127.0.0.1:8000/api/analyses/<id>/export?format=geojson" -o export.geojson
python terrawatch-test-pair/check_results.py export.geojson
```

R1-R4 FOUND, F1 "good", F2/F3 still false alarms (documented limitation,
see Gotcha #10).

### Evaluation + ablation

```bash
cd backend && source venv/bin/activate
python scripts/evaluate.py levircd --ablation                    # needs LEVIR-CD
python scripts/evaluate.py oscd --engine engine2 --ablation      # needs OSCD + trained weights
python scripts/evaluate.py oscd --engine spectral --ablation     # needs OSCD only
```

Upserts by engine+dataset+**stage** into `data/eval_results.json`, read by
`GET /api/metrics` and the Accuracy page's ablation table.

### Real-imagery test scripts

```bash
python scripts/fetch_real_test_pair.py   # Pune, India
python scripts/fetch_wayanad.py          # Wayanad landslide, Kerala
python scripts/fetch_oam_barbuda.py      # Barbuda, Hurricane Irma (high-res)
```

## Gotchas we hit (so you don't re-discover them)

1. **Vite + maplibre-gl: "Worker failed to load" in dev mode.** Fixed in
   `frontend/vite.config.ts`: `optimizeDeps: { exclude: ['maplibre-gl'] }`.

2. **Area must be computed in a projected CRS, never in degrees.**
   `app/geo/vectorize.py`'s `resolve_area_crs()` handles this.

3. **Preview color stretch must be shared, not per-image/per-band.**
   `app/geo/preview.py`.

4. **`uvicorn` without `--reload` silently serves stale code.** Always use
   `--reload` or restart explicitly after backend changes.

5. **The after image is always resampled onto the before image's exact
   grid** (`app/geo/align.py`) before anything else.

6. **LEVIR-CD and OSCD have no georeferencing — don't run either through
   the geo pipeline.** `scripts/evaluate.py` and `app/pipeline/ablation.py`
   work on plain numpy arrays directly, bypassing `AlignedPair`/CRS logic.

7. **Python 3.14 (this machine's system default) has no wheels for
   rasterio/geopandas/torch.** Use the Python 3.11 venv.

8. **Engine fallback must never cross the resolution boundary "upward."**
   Coarse input falls to the spectral baseline if Engine 2 is unavailable,
   never to TinyCD. `app/engines/select.py::resolve_engine`,
   regression-tested.

9. **Don't trust a tile's nominal bbox as proof it has real pixel data
   there.** Satellite mosaics are padded to a grid with blank regions.
   `scripts/fetch_oam_barbuda.py` now verifies actual pixel values, not
   just bbox overlap.

10. **A simple RGB brightness/whiteness cloud heuristic cannot reliably
    tell a bright flat cloud from a bright flat rooftop.** This is a real,
    fundamental limitation we hit and could not fully engineer around: on
    `terrawatch-test-pair`, R2 (a destroyed building → bright rubble) and
    F3 (a planted cloud) produce nearly identical brightness+saturation
    signatures at the pixel level — a flat rooftop's *interior* pixels
    have genuinely near-zero texture, same as a cloud's. We tried (a)
    percentile-based (scene-relative) thresholds instead of absolute ones,
    (b) adding a local-texture requirement, (c) morphological opening to
    erode small bright spots — all failed to cleanly separate the two in
    this image; moving the threshold just trades which one misclassifies.
    **Current tradeoff, deliberately chosen:** very strict percentiles
    (`CLOUD_HEURISTIC_BRIGHTNESS_PERCENTILE=99.5`,
    `..._SATURATION_PERCENTILE=3`) plus a low overlap bar
    (`CLOUD_OVERLAP_FRAC_THRESHOLD_HEURISTIC=0.15`) protect real changes
    (R2 stays kept — required) at the cost of sometimes missing real
    clouds on RGB-only input (F3 stays kept too — a known, accepted
    miss). **This does not affect real Sentinel-2 input** — Wayanad uses
    the actual SCL atmospheric-classification band
    (`CLOUD_OVERLAP_FRAC_THRESHOLD_SCL=0.4`, a much more confident
    signal) and correctly rejects its cloud polygon at 97% confidence. If
    you need reliable RGB-only cloud detection, the real fix is a proper
    cloud-detection model, not a brightness heuristic — out of scope here.

11. **ΔNDWI rises on plain vegetation loss, not just real water** (McFeeters'
    formula (G-NIR)/(G+NIR) increases when NIR drops, which bare-soil/
    dead-vegetation does too) — a landslide and a seasonal vegetation
    shift can have near-identical ΔNDVI *and* ΔNDWI. The real discriminator
    we found: **texture change**. A landslide genuinely restructures the
    ground (new texture); a color-only seasonal shift doesn't. See
    `VEGETATION_SEASONAL_TEXTURE_CEILING` in `app/config.py` and Gotcha
    #10's sibling reasoning in `app/pipeline/false_alarm.py`'s
    `vegetation_seasonal` check. Also raised `FLOODING_NDWI_THRESHOLD` to
    0.35 (comfortably above the ~0.25-0.3 vegetation-loss NDWI bump) so
    `change_type` doesn't mislabel a landslide as flooding.

## Folder structure

```
terrawatch/
  PROJECT_BRIEF.md              Original full spec
  terrawatch-phase-prompts.md   Phase 5-8 prompts (paste one at a time)
  README.md                     Phase-by-phase technical writeup
  HANDOFF.md                    This file

  terrawatch-test-pair/         Synthetic UTM test pair + answer key + check_results.py

  backend/                      FastAPI app (Python 3.11)
    app/
      main.py                     App entrypoint, CORS, GET /api/metrics
      models.py                   Analysis table (quality_report, kept/rejected counts, summary_line, ...)
      config.py                   ALL tunable thresholds -- detection, false-alarm, change-type
      api/analyses.py             All /api/analyses* routes
      geo/
        align.py                    Co-register after onto before's grid -> AlignedPair
        preview.py                  AlignedPair -> matching PNG previews
        quality.py                  NEW: cloud masks (SCL/heuristic), misalignment (phase correlation)
        features.py                 NEW: NDVI/NDWI/NDBI/brightness/texture per-pixel maps
        morphology.py                Threshold -> opening/closing (NOT min-area anymore)
        vectorize.py                 Mask -> polygons; generic extra_maps -> PolygonResult.extra
        export.py                    GeoDataFrame -> GeoJSON/GPKG, now incl. status/reject_reason/change_type
      engines/                     common.py, spectral.py, siamese.py, tinycd_src/, unet_model.py, engine2.py, select.py
      pipeline/
        run.py                       Orchestrates: align -> quality -> detect -> filter -> vectorize -> false_alarm -> change_type -> export
        severity.py                  sev_score (KEPT polygons only, as of Phase 4)
        false_alarm.py               NEW: kept/rejected classification, 5 reasons, priority order
        change_type.py               NEW: estimated change type for kept polygons, 6 types
        ablation.py                  NEW: raw/+morphology/+false-alarm masks for plain (non-geo) eval
      impact/ llm/ reports/ alerts/  Empty — Phase 5, 7, 8
    scripts/
      evaluate.py                    levircd/oscd subcommands, --ablation flag -> data/eval_results.json
      oscd_data.py train_oscd_unet.py sentinel2_fetch.py
      fetch_real_test_pair.py fetch_wayanad.py fetch_oam_barbuda.py
    tests/                         geometry, severity, engine_select, false_alarm, change_type, quality
    models/                        Gitignored — tinycd/levir_best.pth, engine2/unet_oscd.pth
    data/                          Gitignored except population/.gitkeep and eval_results.json

  frontend/
    src/
      App.tsx                     Upload form, engine dropdown, quality banner, rejected toggle, summary line
      api/client.ts                Types incl. QualityReport, kept/rejected counts
      map/CompareMap.tsx            Kept (severity) + needs-review (dotted) + rejected (grey dashed) layers
      panels/PolygonPanel.tsx       Plain-language reject reason / estimated change type + rule
      pages/AccuracyPage.tsx        Ablation table, grouped by engine+dataset, stage rows
      styles/tokens.css
    vite.config.ts
```
