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

Scenes processed under Sentinel-2 processing baseline 04.00+ (25 Jan 2022
onward) carry a +1000 DN "BOA add offset" the earlier baseline doesn't --
see needs_boa_offset_correction() below. save_clip() undoes it on the 5
spectral bands (never SCL) so a before/after pair straddling that date is
radiometrically comparable, not just visually "the 2024 image looks
brighter."
"""

from datetime import datetime, timezone
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

# Sentinel-2 L2A processing baseline 04.00 (effective 25 Jan 2022) added a
# +1000 DN "BOA add offset" to the spectral bands so reflectance can't go
# negative after other corrections -- scenes processed under 04.00+ are NOT
# radiometrically comparable to older (pre-offset) scenes unless this is
# undone. See https://sentinels.copernicus.eu/web/sentinel/-/copernicus-sentinel-2-major-products-upgrade-upcoming
# Detected from the item's own s2:processing_baseline property; falls back
# to the acquisition date if that property is ever missing.
BOA_OFFSET_BASELINE_THRESHOLD = 4.0
BOA_OFFSET_CUTOVER_DATE = datetime(2022, 1, 25, tzinfo=timezone.utc)
BOA_OFFSET_VALUE = 1000


def needs_boa_offset_correction(item) -> bool:
    baseline = item.properties.get("s2:processing_baseline")
    if baseline is not None:
        try:
            return float(baseline) >= BOA_OFFSET_BASELINE_THRESHOLD
        except ValueError:
            pass
    return item.datetime >= BOA_OFFSET_CUTOVER_DATE


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

    stacked = np.stack(bands)  # (6, H, W) uint16, raw DN

    boa_corrected = needs_boa_offset_correction(item)
    if boa_corrected:
        # Subtract the +1000 BOA add-offset from the 5 spectral bands only
        # (never SCL, the last band -- it's a categorical class code, not
        # reflectance) so pre- and post-baseline-04.00 scenes are
        # comparable DN-for-DN. Clip at 0, not wrap, on underflow.
        spectral = stacked[:-1].astype(np.int32) - BOA_OFFSET_VALUE
        stacked[:-1] = np.clip(spectral, 0, None).astype("uint16")

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
        "processing_baseline": item.properties.get("s2:processing_baseline"),
        "boa_offset_corrected": boa_corrected,
    }
    print(
        f"wrote {out_path}  shape={stacked.shape}  cloud_cover={meta['cloud_cover']}  "
        f"date={meta['date']}  boa_offset_corrected={boa_corrected}"
    )
    return meta
