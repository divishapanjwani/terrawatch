"""Turn an aligned before/after raster pair into matching web-displayable
PNG overlays + shared EPSG:4326 bounds.

Rules (see app/geo/align.py for the alignment step this builds on):
  - Display uses bands 1-3 (R, G, B) only — never NIR or other bands.
  - The two previews are reprojected to EPSG:4326 using ONE shared transform
    (computed from the aligned before grid), so their bounds are identical.
  - Color stretch is computed ONCE from both images' pixels combined and
    applied identically to both — never per-band, never per-image.
  - uint8 input is assumed to already be display-ready (0-255) and is used
    as-is, with no percentile stretch.
"""

from typing import Optional

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import Resampling, calculate_default_transform, reproject

from app.geo.align import AlignedPair

MAX_PREVIEW_DIM = 2048
RGB_BAND_COUNT = 3


def _compute_shared_stretch(
    before_rgb: np.ndarray,
    after_rgb: np.ndarray,
    before_mask: np.ndarray,
    after_mask: np.ndarray,
    dtype: str,
) -> Optional[tuple]:
    if dtype == "uint8":
        return None
    before_valid = before_rgb[:, before_mask]
    after_valid = after_rgb[:, after_mask]
    combined = np.concatenate([before_valid.ravel(), after_valid.ravel()])
    if combined.size == 0:
        return None
    lo, hi = np.percentile(combined, [2, 98])
    if hi <= lo:
        hi = lo + 1
    return float(lo), float(hi)


def _to_uint8_rgb(rgb: np.ndarray, mask: np.ndarray, stretch: Optional[tuple]) -> np.ndarray:
    """rgb: (3, H, W) -> uint8 (H, W, 3), same stretch applied to all 3 bands."""
    if stretch is None:
        out = np.clip(rgb, 0, 255).astype(np.uint8)
    else:
        lo, hi = stretch
        out = np.clip((rgb.astype(np.float64) - lo) / (hi - lo), 0, 1)
        out = (out * 255).astype(np.uint8)
    out = np.moveaxis(out, 0, -1)  # (H, W, 3)
    out[~mask] = 0
    return out


def generate_preview_pair(aligned: AlignedPair, before_out_path: str, after_out_path: str) -> dict:
    """Returns the shared EPSG:4326 bounds {west, south, east, north} used
    by both output PNGs."""
    band_n = min(RGB_BAND_COUNT, aligned.band_count)
    band_idx = list(range(band_n))

    # Pad to 3 bands (grayscale replicate) if the source has fewer than 3.
    def _rgb(data: np.ndarray) -> np.ndarray:
        bands = [data[i] for i in band_idx]
        while len(bands) < 3:
            bands.append(bands[-1])
        return np.stack(bands, axis=0).astype(np.float64)

    before_rgb_native = _rgb(aligned.before)
    after_rgb_native = _rgb(aligned.after)

    stretch = _compute_shared_stretch(
        before_rgb_native, after_rgb_native, aligned.before_mask, aligned.after_mask, aligned.dtype
    )

    dst_crs = "EPSG:4326"
    transform, width, height = calculate_default_transform(
        aligned.crs,
        dst_crs,
        aligned.width,
        aligned.height,
        *rasterio.transform.array_bounds(aligned.height, aligned.width, aligned.transform),
    )
    scale = min(1.0, MAX_PREVIEW_DIM / max(width, height))
    out_width = max(1, int(width * scale))
    out_height = max(1, int(height * scale))
    if scale != 1.0:
        sx = width / out_width
        sy = height / out_height
        transform = transform * transform.scale(sx, sy)

    def _reproject_to_4326(rgb_native: np.ndarray, mask_native: np.ndarray):
        dst_rgb = np.zeros((3, out_height, out_width), dtype=np.float64)
        for i in range(3):
            reproject(
                source=rgb_native[i],
                destination=dst_rgb[i],
                src_transform=aligned.transform,
                src_crs=aligned.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear,
            )
        dst_mask_u8 = np.zeros((out_height, out_width), dtype=np.uint8)
        reproject(
            source=(mask_native.astype(np.uint8) * 255),
            destination=dst_mask_u8,
            src_transform=aligned.transform,
            src_crs=aligned.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=Resampling.nearest,
        )
        return dst_rgb, dst_mask_u8 > 0

    before_4326, before_mask_4326 = _reproject_to_4326(before_rgb_native, aligned.before_mask)
    after_4326, after_mask_4326 = _reproject_to_4326(after_rgb_native, aligned.after_mask)

    before_uint8 = _to_uint8_rgb(before_4326, before_mask_4326, stretch)
    after_uint8 = _to_uint8_rgb(after_4326, after_mask_4326, stretch)

    before_alpha = (before_mask_4326 * 255).astype(np.uint8)
    after_alpha = (after_mask_4326 * 255).astype(np.uint8)

    Image.fromarray(np.dstack([before_uint8, before_alpha]), mode="RGBA").save(before_out_path)
    Image.fromarray(np.dstack([after_uint8, after_alpha]), mode="RGBA").save(after_out_path)

    west = transform.c
    north = transform.f
    east = west + transform.a * out_width
    south = north + transform.e * out_height

    return {"west": west, "south": south, "east": east, "north": north}


def read_metadata(tif_path: str) -> dict:
    with rasterio.open(tif_path) as src:
        return {
            "crs": str(src.crs) if src.crs else None,
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "bounds": list(src.bounds),
            "res": list(src.res),
            "dtype": src.dtypes[0],
        }
