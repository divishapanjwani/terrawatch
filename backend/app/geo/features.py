"""Per-pixel feature maps used by the false-alarm filter and change-type
rules (app/pipeline/false_alarm.py, app/pipeline/change_type.py). Computed
once on the native aligned grid, then reprojected+aggregated per-polygon
by app/geo/vectorize.py's `extra_maps` mechanism.

Band convention (matches engine2.py): index 0=R, 1=G, 2=B, 3=NIR, 4=SWIR.
Indices that need a band beyond what's available return None -- callers
must treat that as "unavailable", not zero.
"""

from typing import Optional

import numpy as np
from scipy.ndimage import binary_dilation, sobel

EPS = 1e-6


def _band(bands: np.ndarray, idx: int) -> Optional[np.ndarray]:
    if bands.shape[0] <= idx:
        return None
    return bands[idx].astype(np.float32)


def compute_ndvi(bands: np.ndarray) -> Optional[np.ndarray]:
    r, nir = _band(bands, 0), _band(bands, 3)
    if r is None or nir is None:
        return None
    return (nir - r) / (nir + r + EPS)


def compute_ndwi(bands: np.ndarray) -> Optional[np.ndarray]:
    g, nir = _band(bands, 1), _band(bands, 3)
    if g is None or nir is None:
        return None
    return (g - nir) / (g + nir + EPS)


def compute_ndbi(bands: np.ndarray) -> Optional[np.ndarray]:
    nir, swir = _band(bands, 3), _band(bands, 4)
    if nir is None or swir is None:
        return None
    return (swir - nir) / (swir + nir + EPS)


def compute_brightness(bands: np.ndarray) -> np.ndarray:
    n = min(3, bands.shape[0])
    return bands[:n].astype(np.float32).mean(axis=0)


def compute_texture(bands: np.ndarray) -> np.ndarray:
    """Local edge/gradient magnitude of the grayscale image -- a proxy for
    structural detail, used to tell "same structure, different lighting"
    (shadow) apart from "actually different structure" (real change)."""
    gray = compute_brightness(bands)
    gx = sobel(gray, axis=1)
    gy = sobel(gray, axis=0)
    return np.hypot(gx, gy)


def dynamic_range(values: np.ndarray, valid: np.ndarray) -> float:
    if not valid.any():
        return 1.0
    v = values[valid]
    lo, hi = np.percentile(v, [2, 98])
    return max(1.0, float(hi - lo))


def dilate_invalid(valid_mask: np.ndarray, buffer_px: int) -> np.ndarray:
    """Boolean map: True where a pixel is within buffer_px of an invalid
    (no-data / out-of-bounds) region -- used for the misalignment_edge rule."""
    invalid = ~valid_mask
    if buffer_px <= 0:
        return invalid
    return binary_dilation(invalid, iterations=buffer_px)
