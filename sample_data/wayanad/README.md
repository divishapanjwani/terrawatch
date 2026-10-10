# Wayanad demo pair

`before.tif` / `after.tif` — the exact Sentinel-2 L2A GeoTIFFs used for every
Wayanad number in this repo's README and `docs/EVALUATION.md`. Committed here
(~11.8 MB total) so a fresh clone can run the demo with no network access to
Microsoft Planetary Computer required.

| | |
|---|---|
| Area | Mundakkai / Chooralmala, Wayanad district, Kerala — the 30 July 2024 landslide |
| Bounding box | `76.12, 11.44, 76.18, 11.51` (west, south, east, north) |
| Before | lowest-cloud Sentinel-2 L2A scene, Jan–Apr 2024 (pre-monsoon) |
| After | lowest-cloud Sentinel-2 L2A scene, 30 Jul–31 Dec 2024 (post-event) |
| Bands | 5 (R, G, B, NIR, SWIR) + the Scene Classification Layer for cloud masking |
| Source | [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/) STAC API, Sentinel-2 L2A collection (ESA/Copernicus data, free and open) |
| Regenerate | `cd backend && python scripts/fetch_wayanad.py` (re-fetches live from Planetary Computer; requires network, no API key) |

To wire these into the app's "Load Wayanad demo" button and the backend's own
demo path:

```bash
mkdir -p frontend/public/demo backend/data/wayanad
cp sample_data/wayanad/before.tif frontend/public/demo/wayanad_before.tif
cp sample_data/wayanad/after.tif  frontend/public/demo/wayanad_after.tif
cp sample_data/wayanad/before.tif backend/data/wayanad/before.tif
cp sample_data/wayanad/after.tif  backend/data/wayanad/after.tif
```

(`make setup` does this automatically.) Both destinations are gitignored —
they're the same bytes as this folder, just placed where the app expects them.
