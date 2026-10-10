"""Fetch a small real high-res (sub-meter) before/after pair from
OpenAerialMap: Barbuda / Codrington, before and after Hurricane Irma
(Sept 2017).

Source (verified via api.openaerialmap.org directly — NOT the first
candidate pair suggested by research, which turned out to not
geographically overlap at all; and NOT the first-choice before-tile
("10300100301E8700"), which nominally covers this area but its real pixel
data stops short of it — satellite mosaic tiles are padded to a grid and
can have large blank regions. Verified by sampling actual pixel values,
not just comparing nominal tile bboxes):
  before: WorldView-2 (DigitalGlobe), captured 2014-04-24, ~0.48 m/px,
    OAM id 59b7371a23c8440011d7b108 (title "10300100306A2100")
  after:  RescUAV/GlobalMedic drone survey, captured 2017-09-21
    (days after Irma made landfall 2017-09-06), ~0.009 m/px,
    OAM id 59c906e823c8440011d7b20e (title "Barbuda - Codrington D")

Both are public, unauthenticated COGs on S3. We read small windows via
GDAL's /vsicurl/ virtual filesystem (rasterio) rather than downloading the
full 123MB/280MB files, clipped to the after tile's small footprint (the
before tile is a much larger regional mosaic tile; the after tile is a
small town-block drone survey — their *intersection* is the after tile's
own extent).
"""

import sys
from pathlib import Path

import numpy as np
import rasterio
import rasterio.warp
from rasterio.enums import Resampling
from rasterio.windows import from_bounds

BEFORE_URL = "/vsicurl/https://oin-hotosm-temp.s3.amazonaws.com/59b7371a23c8440011d7b108/0/929ec9e6-5de3-4105-b643-c9b383bf5e47.tif"
AFTER_URL = "/vsicurl/https://oin-hotosm-temp.s3.amazonaws.com/59c906e823c8440011d7b20e/0/c8df4d28-9340-40e5-be6d-7f9c424091d2.tif"

# The after (drone) tile's own bbox in EPSG:4326 -- confirmed via the OAM
# API to fall entirely inside the before (WorldView-2) tile's footprint.
CLIP_BBOX = (-61.83103234335327, 17.625213179222584, -61.82708796631634, 17.62828278305911)
TARGET_RES_M = 0.5  # downsample the ultra-fine drone tile to roughly match the before tile's GSD

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "oam_barbuda"


def clip_before(out_path: Path):
    with rasterio.open(BEFORE_URL) as src:
        window = from_bounds(*CLIP_BBOX, src.transform)
        window = window.round_lengths().round_offsets()
        data = src.read(window=window)
        transform = src.window_transform(window)
        meta = {
            "driver": "GTiff",
            "height": data.shape[1],
            "width": data.shape[2],
            "count": data.shape[0],
            "dtype": data.dtype,
            "crs": src.crs,
            "transform": transform,
        }
    if data.max() == 0:
        # Mosaic/regional tiles are often padded to a grid with large blank
        # regions outside the actual imaged footprint -- a nominal bbox
        # overlap doesn't guarantee real pixel data there. Fail loudly
        # instead of silently writing an all-black GeoTIFF.
        raise RuntimeError(
            f"Clipped region from {BEFORE_URL} is entirely blank (all zero pixels) -- "
            "the tile's nominal bbox includes this area but its real image data doesn't. "
            "Pick a different source tile."
        )
    with rasterio.open(out_path, "w", **meta) as dst:
        dst.write(data)
    print(f"wrote {out_path}  shape={data.shape}  crs={meta['crs']}")


def clip_after(out_path: Path):
    with rasterio.open(AFTER_URL) as src:
        dst_bounds = rasterio.warp.transform_bounds("EPSG:4326", src.crs, *CLIP_BBOX)
        west, south, east, north = dst_bounds
        out_width = max(1, int((east - west) / TARGET_RES_M))
        out_height = max(1, int((north - south) / TARGET_RES_M))
        dst_transform = rasterio.transform.from_bounds(west, south, east, north, out_width, out_height)

        data = np.zeros((src.count, out_height, out_width), dtype=src.dtypes[0])
        for b in range(1, src.count + 1):
            rasterio.warp.reproject(
                source=rasterio.band(src, b),
                destination=data[b - 1],
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=dst_transform,
                dst_crs=src.crs,
                resampling=Resampling.average,
            )
        meta = {
            "driver": "GTiff",
            "height": out_height,
            "width": out_width,
            "count": src.count,
            "dtype": src.dtypes[0],
            "crs": src.crs,
            "transform": dst_transform,
        }
    with rasterio.open(out_path, "w", **meta) as dst:
        dst.write(data)
    print(f"wrote {out_path}  shape={data.shape}  crs={meta['crs']}  resampled to ~{TARGET_RES_M}m/px")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Clipping before (WorldView-2, 2014-04-24)...")
    clip_before(OUT_DIR / "before.tif")
    print("Clipping + downsampling after (drone survey, 2017-09-21, post-Irma)...")
    clip_after(OUT_DIR / "after.tif")


if __name__ == "__main__":
    sys.exit(main())
