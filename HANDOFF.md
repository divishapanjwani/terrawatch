# Handoff — TerraWatch

## Current status & next steps (Round 3, this session, 10 Oct 2026 morning)

Session ended early (usage limit) partway through Round 3's 4-item build
list. Full log/numbers: `docs/OVERNIGHT_DEVELOPMENT.md`.

**Done and merged into `main`:**
- `docs/OVERNIGHT_DEVELOPMENT.md` + README "Overnight Development"
  section, documenting the Round 2 overnight push (dark UI, severity/
  ranking fix, KPI/accuracy fixes, 4 UI bugs, PR #4 submission package).
- **Item 1 (any place in India + Case Studies gallery):** auto-fetch by
  place name (Nominatim geocode → Planetary Computer Sentinel-2) at
  `POST /api/analyses/fetch`, shown in the UI; a 4-event Case Studies
  gallery (`GET /api/case_studies`, `POST /api/case_studies/{slug}/load`)
  with cached imagery and thumbnails — Wayanad, Sikkim GLOF, Himachal
  floods, Pune growth. Verified end-to-end via real browser testing
  (Playwright), not just curl. 71/71 backend tests pass, frontend build
  clean. **Known gap:** bbox fetch works server-side (tested via curl)
  but has no draw-a-box UI control yet — only place-name search is wired
  up in the frontend.

**Not started — items 2, 3, 4 from the build list are still open:**
2. **All-weather radar mode (Sentinel-1):** fetch VV/VH RTC/GRD
   before/after from Planetary Computer, log-ratio change detection with
   Otsu threshold + a flood-water rule, vectorize into the same polygon
   format, an Optical/Radar switch in the UI, demonstrated on a cloudy-
   optical event (the Himachal floods case study from Item 1 is the
   natural candidate — Sentinel-2 over Kullu/Manali during the actual
   July 2023 flood peak is very likely cloud-heavy; this wasn't checked
   yet). Next step: start with `pystac_client` against
   `sentinel-1-rtc` on Planetary Computer for that bbox/date, confirm
   VV/VH asset availability, then write
   `backend/app/engines/radar.py` (log-ratio + `skimage.filters.threshold_otsu`)
   parallel to the existing spectral/engine2 engines, reusing
   `app/geo/vectorize.py`'s `vectorize()` so polygons flow through the
   same false_alarm/change_type/severity/priority pipeline unchanged.
3. **Action layer:** blocked-route checker (osmnx road graph, cached,
   `route_impact`/`detour_m` columns already reserved at weight 0 in
   `app/pipeline/priority.py` — just needs wiring), PDF + mobile HTML
   field report (top 10 priority areas table), English/Hindi/Marathi
   templates (computed values only, no LLM). Not started.
4. **Filter v2 + terrain:** Copernicus DEM GLO-30 slope/hillshade per
   polygon, landslide-requires-slope / flooding-requires-flat rules, a
   terrain_shadow rejection, improved vegetation_seasonal rule. Not
   started.

**If resuming:** `git checkout overnight-v2 && git pull`, confirm
`git log --oneline -5` shows the Item 1 commits, then continue with
Item 2 in the order above. The repo's dev sqlite db
(`backend/data/terrawatch.db`) was deleted once this session to pick up
new `Analysis` model columns (gitignored, safe to delete again if the
schema changes further — it's not seed data).


You're picking this up at the start of **Phase 6** (Phase 5 is merged
into main). This file is the practical "get running and know what's
real" doc. `README.md` has the fuller technical writeup per phase;
`PROJECT_BRIEF.md` is the original spec; `terrawatch-phase-prompts.md`
has the Phase 5-8 prompts to paste into Claude Code one at a time.

## UI redesign (branch `ui-redesign`, off main after Phase 5)

Frontend-only dark redesign replacing PROJECT_BRIEF.md Section 10's
light design -- no backend/detection/filter/priority/API changes, same
components' state and handlers throughout, just restyled (plus a couple
of genuinely new, additive bits: explicit Priority queue/Change details
tabs, a KPI strip, a "Load Wayanad demo" one-click landing button, a
Settings "Reset to defaults"). See that branch's commits for the full
writeup; the short version:

- Dark palette (`#0B1215`/`#111B1F`/`#18252A` surfaces, `#2FD3C1` teal
  accent, fixed severity colors), Inter + JetBrains Mono, `lucide-react`
  icons. `frontend/src/styles/tokens.css` + `design-system.css`.
- "Load Wayanad demo" fetches `frontend/public/demo/wayanad_before.tif`
  / `wayanad_after.tif` as static files and feeds them through the
  normal upload path -- **gitignored, not committed** (same ~12 MB
  bytes as `backend/data/wayanad/`). To use the demo button on a fresh
  clone: `cp backend/data/wayanad/before.tif
  frontend/public/demo/wayanad_before.tif` (and `after.tif` likewise).
  Hidden/disabled gracefully if missing.
- Several real bugs found via Playwright click/hover/build testing, not
  just screenshots -- worth knowing about if you touch `CompareMap.tsx`
  or custom form controls again: (1) reactive layer-sync effects
  checking a hardcoded source name instead of "does this map have an
  image yet" silently broke the after-map's facilities/roads/population
  layers; (2) a custom `Switch` component rooted in `<span>` instead of
  `<label>` meant clicking the visible toggle never reached the
  visually-hidden `<input>` -- every toggle in the app was unclickable;
  (3) `tsc --noEmit` alone does not catch everything `tsc -b` (the real
  `npm run build` step) catches, e.g. a MapLibre event-type error on
  `"mouseleave"` at the map level (needs a layer id, or use `"mouseout"`
  for the whole-map case); (4) any mousemove/click handler added to one
  side of the before/after swipe map must be added to **both** `MLMap`
  instances, since the swipe divider means either one can be under the
  cursor -- this one recurred three times across the hover-glow,
  hazard-zone draw, and cursor-coordinate features.

## Status: Phases 1-5 done

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
- 69 unit tests pass (`backend/tests/`).

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

Also not built yet: auto-fetch UI (Phase 6), LLM summaries/ask-the-map
(Phase 7), reports/alerts (Phase 8).

### Phase 5 (branch `phase-5-mini`): impact layer -- population, facilities,
priority queue, prevention mode

Built in two passes (an initial scoped-down "mini" slice, then the rest
of the full Phase 5 spec), plus a round of demo-blocking bug fixes along
the way. All of it is on `phase-5-mini`; summarized as one coherent
feature set here since that's how it ships.

**1. Change-type bug fix (Phase 4 code, explicitly requested):** the real
Wayanad landslide polygon (ΔNDVI -0.13, ΔNDBI +0.085, texture_change_frac
0.47, 1.56M m²) was mislabeled `new_construction` -- bare soil/debris from
a real landslide can raise ΔNDBI the same way construction does (SWIR/NIR
ratio doesn't cleanly separate the two), and the strict landslide rule's
NDVI threshold and NDBI ceiling were both just barely missed. Added a
texture-gated loose landslide path in `app/pipeline/change_type.py`
(`LANDSLIDE_NDVI_LOOSE_THRESHOLD`, `LANDSLIDE_NDBI_LOOSE_CEILING`,
`LANDSLIDE_TEXTURE_FLOOR`, `LANDSLIDE_LARGE_AREA_M2`): large contiguous
area + high texture change is a tell a freshly built structure can't
fake. Also capped `new_construction`'s max area
(`NEW_CONSTRUCTION_MAX_AREA_M2`) so a sprawling ΔNDBI blob can't default
into it. Two new regression tests in `test_change_type.py`.

**2. Population** (`app/impact/population.py`): WorldPop India 2020 1km
population-count raster (`scripts/download_population.py`, ~18 MB,
gitignored, one country-wide file covers every demo scene). Per kept
polygon: `population_est` (sum of raster pixels inside the polygon) and
`population_buffer_est` (sum inside polygon + a configurable buffer,
default 250 m, `POPULATION_BUFFER_M`) via a windowed raster read +
per-polygon rasterized mask -- no area-weighting needed since WorldPop
pixels are already population counts. Always labeled "(estimate)" in the
UI. Skips gracefully if the raster file is missing (`population_available:
false` on the analysis, fields stay `None` -- never invented). Also
generates a colorized overlay PNG (`generate_population_overlay_png`,
yellow→red ramp, alpha scaled by density, upsampled for a smooth display)
served at `GET /api/analyses/{id}/imagery/population`.

**3. Facilities** (`app/impact/facilities.py`): extended beyond the mini
version's hospitals/clinics/schools to also fetch **main roads** (full
line geometry via Overpass `out geom;`) and **shelters**
(`amenity=shelter` / `emergency=shelter`, filtering out the much more
common "bus-stop waiting shed" tagging of `amenity=shelter` in India so
it isn't mostly noise). New `nearest_main_road_m` (point-to-line distance
in the scene's projected CRS) and `nearby_facilities_json` (nearest 5
hospitals/schools/shelters/roads within `FACILITY_LIST_MAX_DISTANCE_M`,
sorted by distance) per kept polygon. New `GET /api/analyses/{id}/
facilities` endpoint (reads the same disk cache populated during the
analysis run, so no extra fetch in the common case) feeds the map's
Facilities/Roads layers.

**4. Priority score v2** (`app/pipeline/priority.py`), matching the full
PROJECT_BRIEF formula:
```
priority = w1*sev_score + w2*norm(population_est) + w3*facility_proximity
           + w4*confidence + w5*route_impact
```
`route_impact` is reserved for Phase 7 (`w5` defaults to 0.0).
`facility_proximity` = closeness of whichever of hospital/school is
nearer (linear decay to 0 at `PRIORITY_PROXIMITY_MAX_M`, 2 km default).
Weights live in `app/settings.py`, persisted to `data/settings.json`,
editable via `GET`/`POST /api/settings/weights` and the new **Settings**
page (left nav) -- by design, editing them applies to the **next**
analysis you run, not a live recompute of whatever's already on screen
(kept deliberately simple). `priority_reason` now mentions the people
estimate, e.g. "High severity; ~420 people estimated nearby; 180 m from a
hospital."

**5. Prevention mode / hazard zones:** a lightweight click-to-draw tool
on the map (`CompareMap`'s `drawMode`/`onDrawComplete` props -- click to
add vertices, "Finish zone"/"Cancel", no external drawing library). The
zone is drawn **after** seeing the analysis results (you need to see
where `new_construction` was detected to draw around it), so it's applied
via a new `POST /api/analyses/{id}/hazard_zone` that recomputes directly
from the saved GeoJSON/GPKG columns (`recompute_hazard_zone_gdf` in
`priority.py`, pure geopandas -- no re-detection, no re-fetch of
facilities/population). `in_hazard_zone=true` on any `new_construction`
kept polygon whose centroid falls in the zone; in Prevention mode those
rank first (by `priority_score` among themselves), everything else
follows normally. Wording is exactly "New structure detected in hazard
zone — verify" (`config.HAZARD_ZONE_WORDING`), never "illegal".

**6. Frontend:**
- `PriorityPanel.tsx`: severity filter chips (All/High/Medium/Low), top
  10 rows by default with a "Show all (N)" button (still scrollable),
  people-estimate per row, two-way hover highlighting with the map (new
  `changes-hover` map layer + `hoveredId` state in `App.tsx`).
- Map layer toggles (left panel): Population (raster), Facilities
  (color-coded circles, no emoji), Roads (grey lines).
- Layout fix: the right panel (Priority queue / polygon details) is now
  a flex sibling of the map, not an absolute overlay, so the map keeps
  its own width and the After label/image are never hidden. Collapsed by
  default, with a vertical "Priority (N)" / "Close" toggle rail; the
  map's existing ResizeObserver picks up the width change automatically.
- Summary strip (bottom of map): kept/rejected counts, total estimated
  people in affected areas, count of priority areas near a facility --
  plain typographic numbers, matching the design brief.
- `SettingsPage.tsx`: edit the five weights.

**7. Two real bugs found and fixed via browser-driven testing (not just
unit tests):**
- The map's reactive layer-sync effects (geojson/facilities/population)
  checked `map.isStyleLoaded() && map.getSource("before-img")` for
  **both** maps -- but the after-map's image source is literally named
  `"after-img"`, so that check was always false there, and
  `isStyleLoaded()` itself is flaky (can read false moments after any
  source update even once the map is fully usable). Facilities/roads/
  population layers were silently never attaching to the after-map.
  Fixed with a `mapHasImage()` helper checking either source name,
  dropping the `isStyleLoaded()` gate. Caught by instrumenting a test
  script with `queryRenderedFeatures` -- a visual screenshot alone looked
  plausible enough that this could easily have shipped broken.
- After applying a hazard zone, an already-open polygon details panel
  kept showing a stale pre-update feature snapshot (`selected` state
  wasn't refreshed from the new geojson). Fixed in `App.tsx`'s
  `handleDrawComplete`.

**8. Tests:** 12 new backend unit tests (`test_priority.py` -- score
weighting/ranking/reason text, hazard-zone flagging restricted to
`new_construction`, nearest-road + nearby-facilities-list distance math;
`test_population.py` -- population sum against a synthetic raster with a
known value, graceful skip when the raster file is missing) plus the 2
change-type regression tests above. 69 tests total, all passing.

**9. End-to-end verification:**
- **Wayanad, Disaster mode, Auto engine** (resolves to Engine 2/U-Net):
  187 candidates → 179 kept, 8 rejected -- same real numbers Phase 4
  reported. Population/Facilities/Roads layers all confirmed rendering
  at their correct real-world positions. Summary strip: ~6,695 estimated
  people in affected areas, 74 priority areas near a facility.
- **Wayanad, Prevention mode, hand-drawn zone:** drew a zone (4 clicks)
  around two real `new_construction` polygons (2,700 m² and 800 m²,
  centroid ~11.492°N/76.168°E) using the browser draw tool -- both got
  flagged `in_hazard_zone: true`, re-ranked to #1 and #2, with the exact
  required banner text. **Pune 2019→2024 was tried first** (per the
  original brief's suggestion) but its detections under the current
  engine/thresholds don't include any `new_construction` (band_count is
  6 so NDBI is available, but none of its 4 kept polygons cross the
  threshold) -- Wayanad was used instead for this test, since it's the
  pair that actually has real `new_construction` detections to draw
  around. Disclosed here rather than silently substituted.
- Export (GeoJSON + GPKG) verified after a hazard-zone application:
  `population_est`, `population_buffer_est`, `nearest_main_road_m`,
  `nearby_facilities_json`, `in_hazard_zone`, `priority_score/rank/reason`
  all present and consistent on both formats.
- Screenshots in `~/Desktop/screenshots/phase5/`: `layout_fixed.png`
  (landslide label + layout fix), `disaster_map_layers.png` (population/
  facilities/roads layers), `prevention_hazard_flagged.png` (hazard zone
  applied, banner + rank #1), plus the earlier mini-version screenshots.

**Did not touch:** Phase 4's false-alarm filter or detection logic
(`app/pipeline/false_alarm.py`, the engines) -- the one Phase 4 file
touched, `change_type.py`, was an explicit bug-fix request, documented
above, not a scope change.

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

**Download the population raster** (optional — Phase 5's population_est/
population_buffer_est skip gracefully without it, `population_available:
false`):

```bash
python scripts/download_population.py   # ~18 MB, WorldPop India 2020 1km
```

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

12. **MapLibre's `isStyleLoaded()` is flaky, and each map's image source
    has a different name.** The split-view has two independent `MLMap`
    instances; the before-map's imagery source is named `"before-img"`,
    the after-map's `"after-img"`. A reactive effect that checks
    `map.getSource("before-img")` for *both* maps will silently never be
    true for the after-map. Separately, `isStyleLoaded()` can report
    `false` for a brief window after *any* source update even on an
    otherwise fully-rendered map — don't gate a "has this map finished
    its initial setup" check on it. `app/map/CompareMap.tsx`'s
    `mapHasImage()` checks both source names and nothing else. This bit
    the Population/Facilities/Roads map layers specifically (frontend/src/
    map/CompareMap.tsx) — they looked plausible in a screenshot (map
    rendered fine) but the layers had silently never attached to the
    after-map. Caught by instrumenting a test script with
    `queryRenderedFeatures`, not by eyeballing a screenshot.

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
      models.py                   Analysis table (quality_report, kept/rejected counts, summary_line,
                                   population/hazard-zone summary fields as of Phase 5)
      config.py                   ALL tunable thresholds -- detection, false-alarm, change-type, impact/priority
      settings.py                 NEW: editable priority weights, persisted to data/settings.json
      api/
        analyses.py                 All /api/analyses* routes, incl. /facilities and POST /hazard_zone
        settings.py                 NEW: GET/POST /api/settings/weights
      geo/
        align.py                    Co-register after onto before's grid -> AlignedPair
        preview.py                  AlignedPair -> matching PNG previews
        quality.py                  Cloud masks (SCL/heuristic), misalignment (phase correlation)
        features.py                 NDVI/NDWI/NDBI/brightness/texture per-pixel maps
        morphology.py                Threshold -> opening/closing (NOT min-area anymore)
        vectorize.py                 Mask -> polygons; generic extra_maps -> PolygonResult.extra;
                                      compute_bounds_4326() shared by area-CRS resolution + OSM lookup
        export.py                    GeoDataFrame -> GeoJSON/GPKG, incl. status/reject_reason/change_type
                                      and (Phase 5) population/facility/hazard-zone/priority fields
      engines/                     common.py, spectral.py, siamese.py, tinycd_src/, unet_model.py, engine2.py, select.py
      impact/                      NEW (Phase 5): social-impact computations
        facilities.py                OSM hospitals/clinics/schools/shelters/roads via Overpass, disk-cached
        population.py                WorldPop raster sum (population_est/_buffer_est) + colorized overlay PNG
      pipeline/
        run.py                       Orchestrates: align -> quality -> detect -> filter -> vectorize ->
                                      false_alarm -> change_type -> severity -> impact (Phase 5) -> export
        severity.py                  sev_score (KEPT polygons only, as of Phase 4)
        false_alarm.py               Kept/rejected classification, 5 reasons, priority order
        change_type.py               Estimated change type for kept polygons, 6 types (landslide/new_construction
                                      rule fix, Phase 5 -- see Gotcha #11/HANDOFF text above)
        priority.py                  NEW (Phase 5): priority_score (severity+population+facility+confidence),
                                      hazard-zone flagging + Prevention-mode re-ranking
        ablation.py                  raw/+morphology/+false-alarm masks for plain (non-geo) eval
      llm/ reports/ alerts/        Empty — Phase 7, 8
    scripts/
      evaluate.py                    levircd/oscd subcommands, --ablation flag -> data/eval_results.json
      oscd_data.py train_oscd_unet.py sentinel2_fetch.py
      fetch_real_test_pair.py fetch_wayanad.py fetch_oam_barbuda.py
      download_population.py         NEW: WorldPop India 2020 1km raster -> data/population/
    tests/                         geometry, severity, engine_select, false_alarm, change_type, quality,
                                    priority, population (Phase 5)
    models/                        Gitignored — tinycd/levir_best.pth, engine2/unet_oscd.pth
    data/                          Gitignored except population/.gitkeep and eval_results.json
                                    (population/*.tif, osm_cache/*.json, settings.json also gitignored)

  frontend/
    src/
      App.tsx                     Upload form, engine/mode, quality banner, layer toggles (Phase 5:
                                   Population/Facilities/Roads), hazard-zone draw control, summary strip
      api/client.ts                Types incl. QualityReport, FacilitiesData, PriorityWeights
      map/CompareMap.tsx            Kept (severity) + needs-review (dotted) + rejected (grey dashed) layers;
                                     Phase 5: facilities/roads/population layers, hazard-zone draw tool,
                                     hover highlighting -- see mapHasImage() Gotcha #12 above
      panels/
        PolygonPanel.tsx             Plain-language reject reason / estimated change type + rule;
                                      Phase 5: nearest hospital/school/road, population, hazard-zone banner
        PriorityPanel.tsx            NEW (Phase 5): ranked list, severity filter, top-10 + "Show all",
                                      people estimate, two-way hover
      pages/
        AccuracyPage.tsx             Ablation table, grouped by engine+dataset, stage rows
        SettingsPage.tsx             NEW (Phase 5): edit priority weights
      styles/tokens.css
    vite.config.ts
```
