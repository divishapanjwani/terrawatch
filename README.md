# TerraWatch

Satellite change-intelligence platform: upload two co-registered GeoTIFFs
(before/after), detect real changes, filter out false alarms, and turn the
result into attributed map polygons for disaster-response teams and urban
planners.

This README is updated at the end of each build phase. Current status:
**Phase 1 — Skeleton** (upload two GeoTIFFs, view them on a before/after
split-view map). No change detection yet — that lands in Phase 2.

## Repository structure

```
terrawatch/
  backend/          FastAPI app (Python 3.11)
    app/
      api/          API routers
      geo/          Raster I/O, reprojection, preview generation
      pipeline/ engines/ impact/ llm/ reports/ alerts/   (empty — later phases)
    data/            Runtime data: uploads, generated previews, sqlite db (gitignored)
    models/          Downloaded model weights go here (gitignored)
  frontend/          React + Vite + TypeScript + MapLibre GL
    src/
      api/           Backend API client
      map/           CompareMap (before/after swipe)
      styles/        Design tokens (tokens.css)
  .env.example       All optional integration keys
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

Run the API:

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The first run creates `backend/data/terrawatch.db` (SQLite) and the
`backend/data/uploads/` and `backend/data/analyses/` directories
automatically.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server expects the backend at
`http://127.0.0.1:8000` (see `frontend/src/api/client.ts`).

## What's implemented (Phase 1)

- `POST /api/analyses` — upload a `before` and `after` GeoTIFF (multipart),
  returns an `analysis_id`. The backend validates both files open as valid,
  georeferenced rasters, reprojects each to EPSG:4326, and renders a
  percentile-stretched RGB PNG preview with an alpha mask for the
  no-data border.
- `GET /api/analyses/{id}` — status (`pending` / `ready` / `failed`),
  error message if validation failed, and the EPSG:4326 bounds of each
  image.
- `GET /api/analyses/{id}/imagery/{before|after}` — serves the generated
  PNG preview.
- `GET /api/analyses/{id}/polygons` — stub, returns an empty GeoJSON
  `FeatureCollection` (the change-detection pipeline is Phase 2).
- Frontend: upload form (before/after file pickers + disaster/prevention
  mode toggle), polls analysis status, then renders a **before/after
  split-view map** — two synced MapLibre GL maps with a draggable swipe
  divider, each showing one image positioned at its true georeferenced
  bounds.

No change detection, polygons, severity, or exports yet — those are
Phase 2 onward per the build plan.

## How to test it

1. Start both servers (above).
2. You need two real GeoTIFFs covering the same area. If you don't have a
   pair handy yet, generate two small synthetic georeferenced test files:

   ```bash
   cd backend
   source venv/bin/activate
   python - <<'EOF'
   import numpy as np, rasterio
   from rasterio.transform import from_bounds
   width, height = 200, 200
   bounds = (76.1, 11.4, 76.15, 11.45)
   transform = from_bounds(*bounds, width, height)
   for name, seed in [("before", 1), ("after", 2)]:
       rng = np.random.default_rng(seed)
       data = rng.integers(40, 200, size=(3, height, width), dtype=np.uint8)
       with rasterio.open(f"/tmp/test_{name}.tif", "w", driver="GTiff",
                           width=width, height=height, count=3, dtype="uint8",
                           crs="EPSG:4326", transform=transform) as dst:
           dst.write(data)
   EOF
   ```

3. In the browser, choose `/tmp/test_before.tif` as "Before image" and
   `/tmp/test_after.tif` as "After image", leave mode as "Disaster", click
   **Run analysis**.
4. Wait a few seconds — the right panel becomes a split-view map with
   "Before" / "After" labels in the top corners. Drag the green divider
   left/right; the map content on each side should swap correctly. Panning
   and zooming one side moves the other in sync.

Real Sentinel-2 / high-res GeoTIFF pairs will work the same way as long as
they're georeferenced (have a CRS). Non-georeferenced imagery (e.g. raw
LEVIR-CD PNGs) is rejected with a clear error — that dataset is for model
evaluation only (see the "Data gotchas" note in the project spec).

## Next phase

**Phase 2 — Core pipeline**: spectral change detection (or a pretrained
Siamese CNN for high-res RGB), morphological filtering, contour-to-polygon
vectorization, per-polygon area/magnitude/centroid, severity tiers, map
overlay, and GeoJSON/GeoPackage export. At the end of Phase 2 all hackathon
problem-statement requirements are met.
