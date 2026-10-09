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
        window = from_bounds(west - margin_deg, south - margin_deg, east + margin_deg, north + margin_deg, ds.transform)
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
