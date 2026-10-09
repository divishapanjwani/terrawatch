"""One-off: fetch a small real Sentinel-2 L2A before/after pair from
Microsoft Planetary Computer (public STAC catalog, no API key needed) to
exercise the pipeline on real georeferenced imagery. Not the full Phase 6
auto-fetch feature — just enough to prove the geo pipeline works on real
satellite data, not only the synthetic test pair.
"""
import sys
from pathlib import Path

import numpy as np
import planetary_computer
import pystac_client
import rasterio
import rasterio.warp
from rasterio.windows import from_bounds
from rasterio.enums import Resampling

# Small bbox near Pune, Maharashtra (urban growth area), ~3km x 3km.
BBOX = (73.74, 18.55, 73.78, 18.58)
BEFORE_DATE = "2019-01-01/2019-03-01"
AFTER_DATE = "2024-01-01/2024-03-01"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "real_test_pair"


def find_scene(catalog, date_range):
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=BBOX,
        datetime=date_range,
        query={"eo:cloud_cover": {"lt": 10}},
        sortby=[{"field": "eo:cloud_cover", "direction": "asc"}],
    )
    items = list(search.items())
    if not items:
        raise RuntimeError(f"No low-cloud Sentinel-2 scenes found for {date_range}")
    return items[0]


def save_clip(item, out_path: Path):
    assets = {b: planetary_computer.sign(item.assets[b]).href for b in ["B04", "B03", "B02", "B08"]}
    bands = []
    out_meta = None
    for b in ["B04", "B03", "B02", "B08"]:
        with rasterio.open(assets[b]) as src:
            window = from_bounds(*rasterio.warp.transform_bounds("EPSG:4326", src.crs, *BBOX), src.transform)
            data = src.read(1, window=window, out_dtype="uint16")
            if out_meta is None:
                out_transform = src.window_transform(window)
                out_meta = {
                    "driver": "GTiff",
                    "height": data.shape[0],
                    "width": data.shape[1],
                    "count": 4,
                    "dtype": "uint8",
                    "crs": src.crs,
                    "transform": out_transform,
                }
            bands.append(data)

    # Scale Sentinel-2 reflectance (0-10000ish) to 8-bit for display/engine use.
    stacked = np.stack(bands)
    scaled = np.clip(stacked.astype(np.float32) / 3000 * 255, 0, 255).astype(np.uint8)

    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(scaled)
    print(f"wrote {out_path}  shape={scaled.shape}  cloud_cover={item.properties.get('eo:cloud_cover')}  date={item.datetime}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )

    before_item = find_scene(catalog, BEFORE_DATE)
    after_item = find_scene(catalog, AFTER_DATE)

    save_clip(before_item, OUT_DIR / "before.tif")
    save_clip(after_item, OUT_DIR / "after.tif")


if __name__ == "__main__":
    sys.exit(main())
