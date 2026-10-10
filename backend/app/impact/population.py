"""Population estimate per KEPT polygon, from a WorldPop population-count
raster (see scripts/download_population.py). Degrades gracefully: if the
raster isn't present, population_est/population_buffer_est stay None and
the caller should say so in the UI -- never invent a number.

WorldPop pixel values are already population COUNTS per pixel (not a
density), so the estimate is a straight sum of in-range pixels -- no
area-weighting needed.
"""

from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry import mapping
from shapely.ops import transform as shapely_transform

from app import config


def population_raster_path() -> Optional[Path]:
    path = config.POPULATION_RASTER_PATH
    return path if path.exists() else None


def _read_window(raster_path: Path, bounds_4326: tuple, margin_deg: float = 0.05):
    west, south, east, north = bounds_4326
    with rasterio.open(raster_path) as ds:
        window = from_bounds(
            west - margin_deg, south - margin_deg, east + margin_deg, north + margin_deg, ds.transform
        )
        window = window.round_offsets().round_lengths()
        # Clamp to the raster's own extent -- a demo bbox near the edge of
        # the country file shouldn't ask for an out-of-bounds window.
        window = window.intersection(rasterio.windows.Window(0, 0, ds.width, ds.height))
        if window.width <= 0 or window.height <= 0:
            return None, None, None
        arr = ds.read(1, window=window)
        win_transform = ds.window_transform(window)
        nodata = ds.nodata
    return arr, win_transform, nodata


def _sum_within(geom_4326, arr: np.ndarray, win_transform, nodata: Optional[float]) -> float:
    if arr is None or arr.size == 0:
        return 0.0
    mask = geometry_mask([mapping(geom_4326)], out_shape=arr.shape, transform=win_transform, invert=True)
    vals = arr[mask].astype(np.float64)
    if nodata is not None:
        vals = vals[vals != nodata]
    vals = vals[np.isfinite(vals)]
    vals = vals[vals >= 0]
    return float(vals.sum())


_RAMP = [
    (0.0, (255, 255, 255, 0)),
    (0.15, (255, 237, 160, 90)),
    (0.45, (254, 178, 76, 140)),
    (0.75, (240, 59, 32, 170)),
    (1.0, (150, 10, 30, 190)),
]


def _colorize(norm: np.ndarray) -> np.ndarray:
    """norm: (H, W) float in [0, 1] -> (H, W, 4) uint8 RGBA, a simple
    yellow -> orange -> dark red ramp with alpha scaling by value so
    zero-population areas are fully transparent."""
    out = np.zeros((*norm.shape, 4), dtype=np.float64)
    for (lo_t, lo_c), (hi_t, hi_c) in zip(_RAMP[:-1], _RAMP[1:]):
        mask = (norm >= lo_t) & (norm <= hi_t)
        span = hi_t - lo_t or 1.0
        frac = np.clip((norm[mask] - lo_t) / span, 0, 1)[:, None]
        lo_arr = np.array(lo_c, dtype=np.float64)
        hi_arr = np.array(hi_c, dtype=np.float64)
        out[mask] = lo_arr + frac * (hi_arr - lo_arr)
    return out.astype(np.uint8)


def generate_population_overlay_png(bounds_4326: tuple, out_path: Path, target_size: int = 512) -> bool:
    """Writes an RGBA PNG covering exactly bounds_4326, colorized by
    population count, for the map's Population layer toggle. Returns
    False (no file written) if the raster isn't present."""
    raster_path = population_raster_path()
    if raster_path is None:
        return False

    west, south, east, north = bounds_4326
    with rasterio.open(raster_path) as ds:
        window = from_bounds(west, south, east, north, ds.transform)
        window = window.round_offsets().round_lengths()
        window = window.intersection(rasterio.windows.Window(0, 0, ds.width, ds.height))
        if window.width <= 0 or window.height <= 0:
            return False
        arr = ds.read(1, window=window).astype(np.float64)
        nodata = ds.nodata

    if nodata is not None:
        arr[arr == nodata] = 0.0
    arr[~np.isfinite(arr)] = 0.0
    arr[arr < 0] = 0.0

    # Upsample for a smoother overlay -- same values, just interpolated
    # onto a finer display grid (the source is ~1km/pixel).
    from scipy.ndimage import zoom

    h, w = arr.shape
    if h == 0 or w == 0:
        return False
    scale = target_size / max(h, w)
    scale = max(scale, 1.0)
    arr = zoom(arr, scale, order=1)

    cap = np.percentile(arr, 99) if arr.max() > 0 else 1.0
    cap = max(cap, 1e-6)
    norm = np.clip(arr / cap, 0, 1)

    rgba = _colorize(norm)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(out_path)
    return True


def compute_population(kept_polygons: list, bounds_4326: tuple, buffer_m: float = None) -> bool:
    """Mutates population_est / population_buffer_est on each polygon in
    place. Returns True if the population raster was available and used,
    False if it was skipped (no raster found -- fields stay None)."""
    raster_path = population_raster_path()
    if raster_path is None or not kept_polygons:
        return False

    buffer_m = buffer_m if buffer_m is not None else config.POPULATION_BUFFER_M
    arr, win_transform, nodata = _read_window(raster_path, bounds_4326)
    if arr is None:
        return False

    area_crs = kept_polygons[0].area_crs
    to_4326 = Transformer.from_crs(area_crs, "EPSG:4326", always_xy=True).transform

    for p in kept_polygons:
        geom_4326 = shapely_transform(to_4326, p.geometry)
        buffered_4326 = shapely_transform(to_4326, p.geometry.buffer(buffer_m))
        p.population_est = round(_sum_within(geom_4326, arr, win_transform, nodata), 1)
        p.population_buffer_est = round(_sum_within(buffered_4326, arr, win_transform, nodata), 1)

    return True
