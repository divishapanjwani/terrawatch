"""Put the 'after' raster onto the 'before' raster's exact pixel grid.

The before image's CRS/transform/width/height is treated as the reference
grid for the whole pipeline (previews, detection, polygon areas). The after
image is resampled onto that grid so that every downstream step — display,
model inference, morphology, vectorization — operates on two arrays that are
pixel-for-pixel co-located. Without this, independently-reprojected before
and after rasters can end up with slightly different bounds/pixel grids
(rounding in the reprojection target) and edges visibly disagree when swiping.
"""

from dataclasses import dataclass

import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.warp import Resampling, reproject


@dataclass
class AlignedPair:
    before: np.ndarray  # (bands, H, W), before's native dtype
    after: np.ndarray  # (bands, H, W), resampled onto before's grid, same dtype
    before_mask: np.ndarray  # (H, W) bool, True where before has valid data
    after_mask: np.ndarray  # (H, W) bool, True where after has valid data after resampling
    crs: CRS
    transform: Affine
    width: int
    height: int
    band_count: int
    dtype: str


def load_aligned_pair(before_path: str, after_path: str) -> AlignedPair:
    with rasterio.open(before_path) as src_before:
        before_crs = src_before.crs
        before_transform = src_before.transform
        width, height = src_before.width, src_before.height
        band_count = src_before.count
        dtype = src_before.dtypes[0]
        before_data = src_before.read()
        before_nodata = src_before.nodata

    if before_nodata is not None:
        before_mask = ~np.all(before_data == before_nodata, axis=0)
    else:
        before_mask = np.ones((height, width), dtype=bool)

    with rasterio.open(after_path) as src_after:
        after_band_count = min(band_count, src_after.count)
        after_data = np.zeros((after_band_count, height, width), dtype=dtype)
        for i in range(after_band_count):
            reproject(
                source=rasterio.band(src_after, i + 1),
                destination=after_data[i],
                src_transform=src_after.transform,
                src_crs=src_after.crs,
                dst_transform=before_transform,
                dst_crs=before_crs,
                resampling=Resampling.bilinear,
            )
        after_mask_u8 = np.zeros((height, width), dtype=np.uint8)
        reproject(
            source=np.full((src_after.height, src_after.width), 255, dtype=np.uint8),
            destination=after_mask_u8,
            src_transform=src_after.transform,
            src_crs=src_after.crs,
            dst_transform=before_transform,
            dst_crs=before_crs,
            resampling=Resampling.nearest,
        )
        after_mask = after_mask_u8 > 0

    if band_count > after_band_count:
        before_data = before_data[:after_band_count]
        band_count = after_band_count

    return AlignedPair(
        before=before_data,
        after=after_data,
        before_mask=before_mask,
        after_mask=after_mask,
        crs=before_crs,
        transform=before_transform,
        width=width,
        height=height,
        band_count=band_count,
        dtype=dtype,
    )
