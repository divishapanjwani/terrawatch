"""Mask -> polygons with attributes, following the pipeline order the
problem statement specifies: morphological-filtered mask -> contour-to-
polygon vectorization (rasterio.features.shapes) -> simplify -> attributes.

Area is always computed in a projected (meters) CRS: the native CRS if it's
already projected, otherwise the correct UTM zone for the scene (resolved
via pyproj). Centroids are always stored as EPSG:4326 lat/lon.
"""

import uuid
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.features import shapes as rio_shapes
from rasterio.warp import Resampling, calculate_default_transform, reproject
from shapely.geometry import shape
from skimage.measure import label as cc_label

from app.geo.align import AlignedPair


@dataclass
class PolygonResult:
    id: str
    geometry: object  # shapely geometry, in area_crs (projected, meters)
    area_crs: CRS
    area_m2: float
    change_magnitude: float
    confidence: float
    centroid_lat: float
    centroid_lon: float
    engine: str
    status: str = "kept"
    severity: Optional[str] = None
    sev_score: Optional[float] = None
    # Per-polygon mean of each extra feature map passed into vectorize()
    # (e.g. ndvi_delta, cloud_overlap_frac) -- see app/geo/features.py and
    # app/pipeline/false_alarm.py. Empty unless the caller asked for extras.
    extra: dict = field(default_factory=dict)
    reject_reason: Optional[str] = None
    change_type: Optional[str] = None
    change_type_rule: Optional[str] = None
    needs_review: bool = False
    # Impact/priority (app/pipeline/priority.py), KEPT polygons only.
    nearest_hospital_m: Optional[float] = None
    nearest_hospital_name: Optional[str] = None
    nearest_school_m: Optional[float] = None
    nearest_school_name: Optional[str] = None
    nearest_main_road_m: Optional[float] = None
    nearby_facilities_json: Optional[str] = None
    population_est: Optional[float] = None
    population_buffer_est: Optional[float] = None
    in_hazard_zone: bool = False
    priority_score: Optional[float] = None
    priority_rank: Optional[int] = None
    priority_reason: Optional[str] = None
    # Blocked-route checker (app/impact/routes.py), KEPT polygons intersecting
    # an OSM road only. None for everything else (not applicable, not "none").
    route_impact: Optional[str] = None  # none | detour | no_alternative | unknown
    detour_m: Optional[float] = None


def native_pixel_area_m2(aligned: AlignedPair) -> float:
    """Pixel area in m^2 on the native grid, used for the min-area filter
    (which runs before vectorization, on the native pixel grid)."""
    if aligned.crs.is_projected:
        return abs(aligned.transform.a * aligned.transform.e)
    import math

    bounds = rasterio.transform.array_bounds(aligned.height, aligned.width, aligned.transform)
    west, south, east, north = bounds
    center_lat = (south + north) / 2
    m_per_deg_lat = 110540.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(center_lat))
    px_w_m = abs(aligned.transform.a) * m_per_deg_lon
    px_h_m = abs(aligned.transform.e) * m_per_deg_lat
    return px_w_m * px_h_m


def compute_bounds_4326(aligned: AlignedPair) -> tuple:
    """(west, south, east, north) of the aligned scene in EPSG:4326 --
    used both for area-CRS resolution below and for the OSM facility
    lookup in app/impact/facilities.py."""
    return rasterio.warp.transform_bounds(
        aligned.crs,
        "EPSG:4326",
        *rasterio.transform.array_bounds(aligned.height, aligned.width, aligned.transform),
    )


def resolve_area_crs(crs: CRS, bounds) -> CRS:
    if crs.is_projected:
        return crs
    from pyproj.aoi import AreaOfInterest
    from pyproj.database import query_utm_crs_info

    west, south, east, north = bounds
    utm_list = query_utm_crs_info(
        datum_name="WGS 84",
        area_of_interest=AreaOfInterest(
            west_lon_degree=west,
            south_lat_degree=south,
            east_lon_degree=east,
            north_lat_degree=north,
        ),
    )
    if not utm_list:
        raise ValueError("Could not resolve a UTM zone for this scene's bounds")
    return CRS.from_epsg(int(utm_list[0].code))


def _to_area_grid(array: np.ndarray, native_crs, native_transform, w, h, area_crs, resampling):
    if area_crs == native_crs:
        return array, native_transform, w, h
    bounds = rasterio.transform.array_bounds(h, w, native_transform)
    dst_transform, dst_w, dst_h = calculate_default_transform(native_crs, area_crs, w, h, *bounds)
    dst = np.zeros((dst_h, dst_w), dtype=array.dtype)
    reproject(
        source=array,
        destination=dst,
        src_transform=native_transform,
        src_crs=native_crs,
        dst_transform=dst_transform,
        dst_crs=area_crs,
        resampling=resampling,
    )
    return dst, dst_transform, dst_w, dst_h


def vectorize(
    binary_mask: np.ndarray,
    prob_map: np.ndarray,
    magnitude_map: np.ndarray,
    aligned: AlignedPair,
    simplify_tolerance_m: float,
    engine: str,
    extra_maps: Optional[dict] = None,
) -> list[PolygonResult]:
    """extra_maps: optional {name: (array (H,W) on the native grid, Resampling)}.
    Each is reprojected onto the same area-CRS grid as everything else and
    reduced to a per-polygon mean, stored in PolygonResult.extra[name].
    Used by the false-alarm filter / change-type rules for things like
    ndvi_delta, cloud_overlap_frac, texture_change_frac -- see
    app/geo/features.py and app/pipeline/false_alarm.py."""
    extra_maps = extra_maps or {}
    native_bounds_4326 = compute_bounds_4326(aligned)
    area_crs = resolve_area_crs(aligned.crs, native_bounds_4326)

    mask_area, transform_area, w_area, h_area = _to_area_grid(
        binary_mask.astype(np.uint8),
        aligned.crs,
        aligned.transform,
        aligned.width,
        aligned.height,
        area_crs,
        Resampling.nearest,
    )
    mask_area = mask_area.astype(bool)
    prob_area, _, _, _ = _to_area_grid(
        prob_map.astype(np.float32),
        aligned.crs,
        aligned.transform,
        aligned.width,
        aligned.height,
        area_crs,
        Resampling.bilinear,
    )
    magnitude_area, _, _, _ = _to_area_grid(
        magnitude_map.astype(np.float32),
        aligned.crs,
        aligned.transform,
        aligned.width,
        aligned.height,
        area_crs,
        Resampling.bilinear,
    )

    extra_area = {}
    for name, (arr, resampling) in extra_maps.items():
        extra_area[name], _, _, _ = _to_area_grid(
            arr.astype(np.float32),
            aligned.crs,
            aligned.transform,
            aligned.width,
            aligned.height,
            area_crs,
            resampling,
        )

    labels = cc_label(mask_area, connectivity=1)
    to_4326 = Transformer.from_crs(area_crs, "EPSG:4326", always_xy=True)

    results: list[PolygonResult] = []
    for geom, val in rio_shapes(labels.astype(np.int32), mask=mask_area, transform=transform_area):
        val = int(val)
        if val == 0:
            continue
        poly = shape(geom)
        if simplify_tolerance_m > 0:
            poly = poly.simplify(simplify_tolerance_m, preserve_topology=True)
        if poly.is_empty or poly.area <= 0:
            continue

        comp_mask = labels == val
        confidence = float(prob_area[comp_mask].mean())
        magnitude = float(magnitude_area[comp_mask].mean())
        extra_values = {name: float(arr[comp_mask].mean()) for name, arr in extra_area.items()}

        centroid = poly.centroid
        lon, lat = to_4326.transform(centroid.x, centroid.y)

        results.append(
            PolygonResult(
                id=uuid.uuid4().hex[:10],
                geometry=poly,
                area_crs=area_crs,
                area_m2=float(poly.area),
                change_magnitude=magnitude,
                confidence=confidence,
                centroid_lat=float(lat),
                centroid_lon=float(lon),
                engine=engine,
                extra=extra_values,
            )
        )
    return results
