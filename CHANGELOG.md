# Changelog

Summarized by build phase (see `HANDOFF.md` for the full narrative and
`git log` for individual commits).

## Phase 1 — Skeleton

FastAPI + React app running end to end: upload two GeoTIFFs, align the
after image onto the before image's grid, render both on a synced
before/after split-view MapLibre map.

## Phase 2 — Core pipeline

Engine 1 (TinyCD) with a spectral-baseline fallback, tiled inference,
morphological opening/closing, `rasterio.features.shapes` vectorization,
per-polygon attributes (area in a resolved projected CRS, change magnitude,
confidence, centroid), the original linear severity formula, GeoJSON +
GeoPackage export. All seven hackathon problem-statement requirements met
at this point.

## Phase 3 — Engine 2 + evaluation

OSCD-trained U-Net (Engine 2) for Sentinel-2/multispectral input, automatic
engine selection by resolution + band count, `scripts/evaluate.py`, and an
Accuracy page in the UI.

## Phase 4 — Trust layer

Pre-detection quality check (cloud %, misalignment via phase correlation,
resolution, band count). False-alarm filter classifying every candidate as
`kept`/`rejected` with one of 5 reasons, computed from per-polygon spectral/
texture features rather than model probability alone. Estimated change-type
labels (6 types) for kept polygons. `--ablation` mode in `evaluate.py`
(raw → +morphology → +false-alarm filter). On Wayanad: 187 candidates → 179
kept, 8 rejected (cloud: 7, vegetation: 1) — the run this README's case
study reports.

## Phase 5 — Impact layer

Population estimates (WorldPop raster, polygon + 250 m buffer), OSM
facilities (hospitals/clinics/schools/shelters/main roads via Overpass,
disk-cached), the full priority-score formula (severity + population +
facility proximity + confidence, route_impact reserved), an editable
Settings page for the weights, and Prevention mode (click-to-draw hazard
zones, `new_construction` re-ranking). Also: a change-type rule fix for the
real Wayanad landslide polygon (bare-soil/debris was briefly misclassified
as `new_construction` before a texture-gated loose landslide path was
added), and two real UI bugs found via browser-driven testing (the
after-map's layers silently never attaching; a custom `Switch` component
unclickable due to its DOM structure).

## UI redesign

Frontend-only dark redesign (no backend/detection/filter/priority/API
changes) — `#0B1215`/`#111B1F`/`#18252A` surfaces, teal accent, Inter +
JetBrains Mono, explicit Priority queue/Change details tabs, a KPI strip,
a one-click "Load Wayanad demo" landing button, and a severity-formula fix
(`max(norm(log1p(area)), norm(log1p(magnitude)))` replacing the original
linear-average formula, which under-scored the single largest real change
in a scene whenever a smaller one had higher per-pixel magnitude).

## Submission prep (this pass)

No application behavior changed. Added: this README rewrite with every
number re-verified against live output; `docs/ARCHITECTURE.md`,
`docs/EVALUATION.md`, `docs/MODEL_CARD.md`; GitHub Actions CI (backend
tests + lint, frontend build + format check); a `Makefile`
(`setup`/`demo`/`test`/`eval`/`lint`/`format`); `sample_data/wayanad/` so a
fresh clone doesn't need live Planetary Computer access for the demo;
`LICENSE` (MIT) and `.env.example` review; black/ruff formatting across the
backend and prettier across the frontend (behavior verified unchanged:
71/71 tests, identical `check_results.py` scores, clean frontend build,
before and after).
