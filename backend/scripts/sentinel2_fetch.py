"""Shared helper: fetch a small Sentinel-2 L2A before/after pair from
Microsoft Planetary Computer's public STAC API (no API key needed) and
save it as a 6-band (R, G, B, NIR, SWIR, SCL) GeoTIFF with RAW reflectance
values for the first 5 bands (uint16, DN = reflectance * 10000) — the same
convention OSCD ships in, so Engine 2's feature computation
(app/engines/engine2.py) sees consistent units whether it's training or
doing real inference. The 6th band is Sentinel-2's own Scene
Classification Layer (SCL), used for real per-pixel cloud detection in the
quality check (app/geo/quality.py) instead of a brightness heuristic.

B11 (SWIR) and SCL are both native 20m resolution; they're resampled onto
the 10m grid of the other four bands (same approach as app/geo/align.py's
co-registration, just band-to-band within one scene instead of
before-to-after). SCL is categorical, so it's resampled with
nearest-neighbor, not bilinear, to avoid inventing fractional class codes.
"""

from pathlib import Path

import numpy as np
import planetary_computer
import pystac_client
import rasterio
import rasterio.warp
from rasterio.enums import Resampling
from rasterio.windows import from_bounds

BANDS = ["B04", "B03", "B02", "B08", "B11", "SCL"]  # R, G, B, NIR, SWIR, SCL
CATEGORICAL_BANDS = {"SCL"}
CATALOG_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def open_catalog():
    return pystac_client.Client.open(CATALOG_URL, modifier=planetary_computer.sign_inplace)


def find_scene(catalog, bbox, date_range, max_cloud=10):
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=date_range,
        query={"eo:cloud_cover": {"lt": max_cloud}},
        sortby=[{"field": "eo:cloud_cover", "direction": "asc"}],
    )
    items = list(search.items())
    if not items:
        raise RuntimeError(f"No Sentinel-2 scenes with <{max_cloud}% cloud found for {date_range}")
    return items[0]


def save_clip(item, bbox, out_path: Path) -> dict:
    """Writes a 5-band (R,G,B,NIR,SWIR) uint16 raw-reflectance GeoTIFF
    clipped to bbox. Returns scene metadata (date, cloud cover)."""
    assets = {b: planetary_computer.sign(item.assets[b]).href for b in BANDS}

    with rasterio.open(assets["B04"]) as ref_src:
        ref_crs = ref_src.crs
        window = from_bounds(*rasterio.warp.transform_bounds("EPSG:4326", ref_crs, *bbox), ref_src.transform)
        window = window.round_lengths().round_offsets()
        ref_transform = ref_src.window_transform(window)
        height, width = int(window.height), int(window.width)

    bands = []
    for b in BANDS:
        with rasterio.open(assets[b]) as src:
            if src.crs == ref_crs and abs(src.res[0] - 10.0) < 1e-6:
                w = from_bounds(*rasterio.warp.transform_bounds("EPSG:4326", src.crs, *bbox), src.transform)
                w = w.round_lengths().round_offsets()
                data = src.read(1, window=w, out_dtype="uint16")
                if data.shape != (height, width):
                    data = data[:height, :width]
            else:
                # Native resolution differs (e.g. B11/SCL at 20m) --
                # resample directly onto the reference 10m grid.
                dst = np.zeros((height, width), dtype="uint16")
                resampling = Resampling.nearest if b in CATEGORICAL_BANDS else Resampling.bilinear
                rasterio.warp.reproject(
                    source=rasterio.band(src, 1),
                    destination=dst,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=ref_transform,
                    dst_crs=ref_crs,
                    resampling=resampling,
                )
                data = dst
            bands.append(data)

    stacked = np.stack(bands)  # (5, H, W) uint16, raw DN

    out_meta = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": len(BANDS),
        "dtype": "uint16",
        "crs": ref_crs,
        "transform": ref_transform,
    }
    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(stacked)

    meta = {
        "date": str(item.datetime),
        "cloud_cover": item.properties.get("eo:cloud_cover"),
        "item_id": item.id,
    }
    print(f"wrote {out_path}  shape={stacked.shape}  cloud_cover={meta['cloud_cover']}  date={meta['date']}")
    return meta
