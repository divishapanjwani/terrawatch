# Build Prompt: TerraWatch AI — Satellite Change Intelligence for Disaster Response

> Paste this whole file into Claude Code (or save it as `PROJECT_BRIEF.md` in an empty repo and tell Claude Code: "Read PROJECT_BRIEF.md and build this project phase by phase.")

---

## 0. How to work on this project

- Build in the **phases listed in Section 9**, in order. At the end of each phase, run it, confirm it works end to end, and tell me what was built and how to test it before moving on.
- Get a **simple working version first**, then improve. A finished basic system beats an unfinished fancy one.
- If something is blocked (missing model weights, a dataset needs manual download, an API key is needed), **stop and tell me exactly what I need to do**. Don't silently fake it.
- **Never invent numbers.** Every metric, count, area, population figure or accuracy score shown in the UI must come from real computation. Use placeholders clearly marked as such only during development.
- Write a clear `README.md` with setup steps, how to run, how to download data, and the demo flow.

---

## 1. What we are building

A web platform that takes **two satellite images of the same place (before and after)**, automatically finds **real changes** (new/destroyed buildings, floods, landslides), **filters out fake changes** (seasonal vegetation, shadows, clouds), and turns them into **map polygons with size, severity, confidence and priority** so disaster-response teams and urban planners know **where to look first and who may be affected**.

**Pitch:** "Satellites capture imagery within hours. Responders can't inspect all of it. We tell them which changes are real, why the rest aren't, and where people are likely to be affected — and the same engine flags risky construction before the next disaster."

### Hackathon problem statement requirements (must ALL be met)
1. Input: two co-registered, orthorectified GeoTIFF tiles covering the same bounding box.
2. AI: pixel-wise/feature-wise difference mapping using a Siamese CNN, ViT feature difference, or spectral change index + lightweight U-Net.
3. Morphological filtering to remove noise.
4. Contour-to-polygon vectorization using Rasterio.
5. Attributed polygons: **area (m²), change magnitude, centroid coordinate**.
6. Output: GIS-ready **GeoJSON and GeoPackage**, categorized into **severity tiers**.
7. Interactive **split-view (before/after) web map**.

---

## 2. Tech stack

**Backend (Python 3.11)**
- FastAPI + Uvicorn
- PyTorch (inference + small training job)
- rasterio, numpy, scikit-image / OpenCV (morphology), shapely, geopandas, pyproj
- pystac-client + planetary-computer (auto-fetch Sentinel-2 L2A)
- osmnx + networkx (OSM hospitals/schools/roads + routing)
- WeasyPrint or ReportLab (PDF reports)
- SQLite (via SQLModel or plain sqlite3) for analysis runs and field feedback
- Anthropic Python SDK for AI summaries and map chat (model from env var `LLM_MODEL`, default `claude-sonnet-5-5`; key from `ANTHROPIC_API_KEY`)
- Background jobs: FastAPI BackgroundTasks or a simple job queue; frontend polls job status

**Frontend**
- React + Vite + TypeScript
- MapLibre GL JS + a before/after compare control (e.g. `@maplibre/maplibre-gl-compare` or a custom swipe implementation)
- Serve imagery to the map as tiles or Cloud-Optimized GeoTIFF previews (backend can generate PNG overlays with bounds, or use `rio-tiler`/TiTiler for XYZ tiles)
- Lightweight charts (Observable Plot or Recharts), styled minimally
- Plain CSS modules or Tailwind with a custom token config — no default UI-kit look

**Config:** `.env.example` with all keys (ANTHROPIC_API_KEY, LLM_MODEL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID). Every optional integration must degrade gracefully if its key is missing.

---

## 3. Data — important gotchas

- **LEVIR-CD** (https://justchenhao.github.io/LEVIR/): 0.5 m RGB building-change pairs, **PNG with no georeferencing**. Use it **only for model evaluation and the accuracy table**, never for m²/coordinates/map demo.
- **OSCD** (Kaggle: soumikrakshit/onera-satellite-change-detection-dataset): Sentinel-2 multispectral (13 bands, 10–60 m) with change labels. Use it to **train/evaluate the Sentinel-2 engine**.
- **Resolution gap:** a model trained on LEVIR-CD (0.5 m) will NOT work well on Sentinel-2 (10 m). So build **two engines** (Section 4) and auto-select based on input resolution and band count.
- **Demo imagery (georeferenced):**
  - Sentinel-2 L2A via Microsoft Planetary Computer (free, has NIR/SWIR + SCL cloud mask).
  - High-res disaster imagery from OpenAerialMap / Maxar Open Data where available.
- **Main demo scenario: Wayanad landslides, Kerala (30 July 2024)** — Mundakkai / Chooralmala area. Verify exact coordinates and bounding box yourself. Kerala monsoon is very cloudy around June–August, so search for the **lowest-cloud Sentinel-2 scenes** before and after the event (the "before" may need to be from earlier in 2024). The seasonal difference between scenes is useful: it showcases our vegetation false-alarm filter.
- **Population:** WorldPop (or GHSL) population grid GeoTIFF for India — document the manual download in README and place it in `data/population/`.
- **Infrastructure:** OpenStreetMap via osmnx/Overpass (hospitals, clinics, schools, main roads, shelters if tagged). Cache results to disk.
- **Prevention-mode zones:** a GeoJSON of hazard zones (flood-prone / landslide-prone areas). If official data isn't available, allow the user to upload or draw a zone polygon on the map. Label clearly as user-provided.

---

## 4. AI change-detection pipeline

### Engine 1 — High-resolution RGB (≤ ~2 m/pixel, 3 bands)
- Use a **pretrained Siamese change-detection model on LEVIR-CD**. Check, in this order, for available pretrained weights: TinyCD (Tiny_model_4_CD), BIT (BIT_CD), ChangeFormer. Use the first that works.
- Run tiled inference (e.g. 256×256 with overlap) on large GeoTIFFs and stitch the probability map.

### Engine 2 — Sentinel-2 multispectral (10 m, multiband)
- Compute spectral change indices: ΔNDVI, ΔNDWI (water), ΔNDBI (built-up), brightness change.
- Train a **lightweight U-Net** on OSCD (input: stacked before/after bands + index differences; output: change probability). Keep it small so training finishes in reasonable time on a laptop GPU/CPU. Save weights to `models/`.
- If training isn't feasible, fall back to a thresholded spectral-index baseline and say so.

### Common steps (both engines)
1. **Input validation & quality check:**
   - Same CRS, bounds, size, resolution (reproject/resample after-image to before-image grid if needed, and warn).
   - Cloud coverage (Sentinel-2 SCL band; for RGB, a simple brightness/whiteness heuristic). Warn if > threshold.
   - Misalignment check (e.g. phase correlation shift estimate). Warn if shift > 1 pixel.
2. **Change probability map** from the selected engine.
3. **Threshold** to a binary mask.
4. **Morphological filtering:** opening/closing, remove objects below a minimum area (configurable, default in m²).
5. **Vectorize** with `rasterio.features.shapes` → shapely polygons → simplify.
6. **Attributes** per polygon (see Section 6).

---

## 5. Feature list

### Core (problem-statement requirements)
1. **Upload two GeoTIFFs** (before/after) with validation and clear error messages.
2. **Change detection** using the correct engine.
3. **Noise cleanup** via morphological filtering.
4. **Polygons** for every change area.
5. **Per-polygon details:** area (m²), change magnitude, centroid (lat/lon).
6. **Severity tiers** High / Medium / Low (rule in Section 6).
7. **Before/after split-view map** with swipe slider.
8. **Export** results as GeoJSON and GeoPackage.

### Trust & accuracy
9. **False-alarm filter with reasons.** Each candidate polygon is classified as *kept* or *rejected*. Rejection reasons: `vegetation_seasonal` (ΔNDVI dominant, no built-up change), `shadow_illumination` (brightness-only change, low texture change), `cloud` (overlaps cloud mask), `too_small`, `misalignment_edge`. For RGB-only input, use the rules that are possible and mark the others as unavailable.
10. **"Rejected changes" map layer** — toggleable, grey dashed outlines, click shows the reason.
11. **Accuracy page:** precision, recall, F1, false-positive rate on the LEVIR-CD test split (Engine 1) and OSCD test split (Engine 2), as an ablation table: raw model → + morphology → + false-alarm filter. Generated by a script (`scripts/evaluate.py`), results saved to JSON and read by the UI.
12. **Confidence per polygon** (mean model probability inside the polygon). Below a threshold → flagged "Needs human review".

### Understanding the change
13. **Change type label** per kept polygon: `new_construction`, `structure_lost`, `flooding`, `landslide_bare_soil`, `vegetation_loss`, `other`. Rule-based using index differences + model output; show the rule that fired. Mark as "estimated type".
14. **Cloud & quality report** shown before results (cloud %, alignment shift, resolution, engine used).

### Social impact
15. **People-affected estimate** per polygon and total, from the population grid (sum of population within polygon, plus within a buffer, e.g. 250 m). Always labeled "estimate".
16. **Nearby critical facilities:** hospitals, schools, main roads within a configurable distance, with distances.
17. **Blocked-route checker:** if a polygon intersects a road, compute whether nearby settlements can still reach the nearest hospital on the OSM road graph with that road segment removed; show the detour distance or "no alternative route found". Label as "possible blockage — verify on ground".
18. **Priority queue:** ranked list with a transparent score and a plain-language reason for each item (Section 6).
19. **Two modes:**
    - **Disaster mode:** priority based on severity, people affected, facilities, route impact.
    - **Prevention mode:** highlight `new_construction` polygons inside user-provided hazard zones. Wording: "New structure detected in hazard zone — verify", never "illegal".

### Usability & wow features
20. **Auto-fetch imagery:** user enters a place name (geocode via Nominatim) or draws a box, picks two date ranges and a max cloud %; backend finds the best Sentinel-2 L2A scenes on Planetary Computer, clips them to the bbox, and saves them as co-registered GeoTIFFs. Show which scenes were chosen (date, cloud %).
21. **AI situation summary** in **English, Hindi or Marathi** (language toggle). The LLM receives ONLY computed facts (counts, areas, top priorities, population estimates) as JSON and must not add facts. Show a note: "AI-generated summary from computed results — verify before official use."
22. **Ask the map:** chat box where the user types e.g. "show high-severity changes near schools" or "changes bigger than 1000 m²". The LLM converts the question into a structured filter (JSON schema you define: severity, change_type, min_area, max_distance_to_facility_type, mode, etc.), the frontend applies it to the map and list. The LLM never answers with made-up data.
23. **Field feedback:** on each polygon, buttons "Confirmed" / "False alarm" / "Unsure" with optional note. Stored in SQLite. Accuracy page shows field-verified precision. Feedback can be used to tune thresholds (document how).
24. **Alerts:** when an analysis finds High-priority items, send a Telegram message (location link, area, reason). Skip gracefully if no bot token.
25. **Speed counter:** show area analysed (km²) and processing time. Optional comparison to manual inspection only with a clearly stated assumption (e.g. "assuming X km²/hour for a trained analyst"), editable in config.
26. **Field report:** one-click PDF + a mobile-friendly shareable HTML page: summary, map snapshot, table of priority polygons (rank, Google Maps link, area, type, confidence, people estimate, nearby facilities, reason). Must be light enough to share on WhatsApp.

---

## 6. Data model and scoring rules

### Polygon attributes (GeoJSON properties / GeoPackage columns)
`id, status (kept|rejected), reject_reason, change_type, change_type_rule, area_m2, change_magnitude, confidence, needs_review, severity, centroid_lat, centroid_lon, population_est, population_buffer_est, nearest_hospital_m, nearest_school_m, nearest_main_road_m, route_impact (none|detour|no_alternative|unknown), detour_m, priority_score, priority_rank, priority_reason, in_hazard_zone, field_status, engine, analysis_id`

### Severity tier (document in UI tooltip)
Severity = change strength, not damage. Combine normalized area and change magnitude, weighted by confidence:
`sev_score = 0.5·norm(area_m2) + 0.5·norm(change_magnitude)`, then High ≥ 0.66, Medium ≥ 0.33, else Low. Thresholds configurable. Show the formula in the UI.

### Priority score (Disaster mode, transparent)
`priority = w1·sev_score + w2·norm(population_est) + w3·facility_proximity + w4·route_impact + w5·confidence`
Default weights in config, editable in a settings panel. `priority_reason` is a generated sentence listing the top 2–3 contributing factors, e.g. "High severity; ~420 people estimated nearby; 180 m from district hospital."

---

## 7. API (suggested)

- `POST /api/analyses` (multipart: before.tif, after.tif, mode, options) → `analysis_id`
- `POST /api/analyses/fetch` (place/bbox, date ranges, max_cloud, mode) → `analysis_id`
- `GET /api/analyses/{id}` → status, progress steps, quality report
- `GET /api/analyses/{id}/polygons` → GeoJSON (kept + rejected)
- `GET /api/analyses/{id}/imagery/{before|after}` → tiles or overlay PNG + bounds
- `GET /api/analyses/{id}/export?format=geojson|gpkg`
- `GET /api/analyses/{id}/report?format=pdf|html`
- `POST /api/analyses/{id}/summary` (language) → text
- `POST /api/analyses/{id}/query` (question) → structured filter JSON
- `POST /api/polygons/{id}/feedback`
- `GET /api/metrics` → evaluation results

---

## 8. Repo structure (suggested)

```
terrawatch/
  backend/
    app/ (api, pipeline/, engines/, geo/, impact/, llm/, reports/, alerts/)
    scripts/ (download_data.py, train_oscd_unet.py, evaluate.py, fetch_demo_wayanad.py)
    models/  data/  tests/
  frontend/
    src/ (map/, panels/, pages/, api/, styles/tokens.css)
  README.md  .env.example  docker-compose.yml (optional)
```

---

## 9. Build phases

1. **Skeleton:** FastAPI + React app running, upload two GeoTIFFs, show both on a split-view map.
2. **Core pipeline:** Engine 1 or a spectral baseline → mask → morphology → polygons with area/magnitude/centroid → severity → map overlay → GeoJSON/GPKG export. *(At this point all PS requirements are met — confirm with me.)*
3. **Engine 2 + evaluation:** OSCD U-Net, engine auto-selection, `evaluate.py`, accuracy page with ablation table.
4. **Trust layer:** quality check, false-alarm filter with reasons, rejected layer, confidence/needs-review, change type labels.
5. **Impact layer:** population estimate, OSM facilities, priority queue, disaster/prevention modes.
6. **Auto-fetch + Wayanad demo:** STAC fetch, demo script that prepares the Wayanad pair.
7. **Routes, AI summary (EN/HI/MR), ask-the-map, field feedback.**
8. **Reports, alerts, speed counter, polish, README, demo script.**

Write basic tests for geometry/area calculations and the scoring functions.

---

## 10. Frontend design brief

Design a minimal, precise, professional interface for a satellite change-intelligence platform used by disaster-response teams and urban planners. It should feel like real GIS software built by a careful engineering team, not a generic AI-generated dashboard. The satellite imagery and the analysis results are the product; the interface should stay out of their way.

**Visual style**
- Calm, credible, understated. Reference points: QGIS/ArcGIS Pro (function), Linear and Mapbox Studio (restraint).
- Flat surfaces, 1px hairline borders, small radii (2–4px), almost no shadows.
- Avoid: gradients, glassmorphism, glows, emoji, AI illustrations, stock hero sections, oversized headings, rows of identical stat cards, decorative animation.

**Colour (define as CSS tokens)**
- UI: warm off-white background (~#F7F6F2), white panels, charcoal text (~#1F2328), muted slate secondary text and borders.
- Accent: restrained forest green (~#2F5D46) for **UI only** — primary buttons, selected states, focus rings.
- **Map overlays use a separate palette** so they never clash with green vegetation in imagery: severity High = red (#C0392B), Medium = orange (#E67E22), Low = yellow (#F1C40F); rejected = grey dashed outline; needs-review = hatched or dotted outline. Overlays use a crisp 1.5–2px outline + 25–35% fill so they stay readable on dark and bright imagery.
- Severity must also be distinguishable without colour (labels/icons/patterns) for colour-blind users.
- Red/amber in the UI chrome only for real alerts and warnings.

**Typography**
- Inter or IBM Plex Sans for UI; IBM Plex Mono / JetBrains Mono for coordinates, IDs and numbers.
- Tabular numerals for all metrics. Small, consistent type scale (12/13/14/16/20). Headings are modest.

**Layout (desktop-first, 1440px reference)**
- Slim left navigation rail: **New Analysis, Map & Results, Priority Queue, Reports, Accuracy, Settings**.
- Main view = full-height map. Left panel (~320px): analysis inputs (upload / auto-fetch, dates, mode toggle Disaster/Prevention, engine and quality report). Map-layer toggles live **in this panel**, not as a separate page: Before, After, Kept changes, Rejected changes, Population, Facilities, Roads, Hazard zones.
- Right panel (~360px, collapsible): either the **priority queue** or the **selected-polygon detail** (all attributes, reason text, nearby facilities, route impact, confidence, field feedback buttons, "Open in Google Maps").
- Top bar of map: before/after swipe toggle, date labels on each side, legend, scale bar, coordinate readout under cursor.
- Bottom strip or collapsible drawer: compact summary — area analysed, kept vs rejected count, area changed, people estimate, processing time — as plain typographic numbers, not cards. One small severity distribution bar.
- "Ask the map" input sits unobtrusively at the top or bottom of the map; results show as active filter chips that can be cleared.
- AI summary panel with language toggle (EN / हिंदी / मराठी) and the verification note.

**States (must be designed, not left default)**
- Processing: step-by-step progress (Validating → Quality check → Detecting → Filtering → Vectorizing → Impact analysis) with real progress from the backend.
- Warnings: cloud cover, misalignment, resolution mismatch shown as a quiet amber banner with details.
- Empty state: a short explanation plus "Load Wayanad demo" button.
- Errors: plain-language message and what to do next.

**Interactions**
- Smooth swipe slider, hover highlight on polygons and matching list rows (two-way linking), click to zoom and open details, keyboard-accessible controls, clear focus states.
- Animation limited to short (150–200ms) transitions for panels and hover.

**Field report page** must be mobile-friendly (single column, readable at 375px width, light page weight).

---

## 11. Honesty rules (show these in the product too)
- Change detection ≠ damage assessment. Severity measures change strength.
- People-affected numbers are estimates from population grids.
- Route blockages and hazard-zone construction are "flagged for verification", never confirmed or labeled illegal.
- AI summaries only restate computed results.

## 12. Demo flow to support
1. Open app → empty state → "Load Wayanad demo" (or auto-fetch by place + dates).
2. Quality report appears (cloud %, alignment, engine).
3. Results: swipe before/after; toggle rejected layer to show filtered fake changes and their reasons.
4. Priority queue: click the #1 item → details, people estimate, nearest hospital, route impact.
5. Ask the map: "high severity near schools".
6. Generate Marathi/Hindi summary.
7. Export GeoPackage + PDF field report; show the mobile report page.
8. Switch to Prevention mode on an urban pair → new construction inside a hazard zone.
9. Accuracy page: ablation table.
