"""Priority score (KEPT polygons only).

Disaster mode:
  priority = w1*sev_score + w2*norm(population_est) + w3*facility_proximity
             + w4*confidence + w5*route_impact
  route_impact is reserved for Phase 7 (w5 defaults to 0.0).
  facility_proximity = closeness() of whichever of hospital/school is
  nearer (see _closeness below). Weights come from app/settings.py
  (editable in the Settings page, applied to new analyses).

Prevention mode:
  new_construction polygons with in_hazard_zone=True are ranked first
  (by priority_score among themselves), everything else follows ranked
  by priority_score as usual.

priority_reason is a plain-language sentence citing the top factors:
severity, people estimate (if population data was available), and
whichever of hospital/school is nearer.
"""
import json

from pyproj import Transformer
from shapely.ops import transform as shapely_transform

from app import config


def _normalize(values: list) -> list:
    vals = [v for v in values if v is not None]
    if not vals:
        return [0.0 for _ in values]
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return [0.5 if v is not None else 0.0 for v in values]
    return [(v - lo) / (hi - lo) if v is not None else 0.0 for v in values]


def _closeness(distance_m) -> float:
    if distance_m is None:
        return 0.0
    return max(0.0, 1.0 - distance_m / config.PRIORITY_PROXIMITY_MAX_M)


def _nearest_point(point_xy: tuple, facilities_xy: list) -> tuple:
    if not facilities_xy:
        return None, None
    px, py = point_xy
    best_d, best_name = None, None
    for x, y, name in facilities_xy:
        d = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        if best_d is None or d < best_d:
            best_d, best_name = d, name
    return best_d, best_name


def _nearest_road(point, roads_lines: list) -> float | None:
    if not roads_lines:
        return None
    return min(point.distance(line) for line in roads_lines)


def _nearby_list(point_xy: tuple, hospitals_xy, schools_xy, shelters_xy, roads_named_lines, point) -> list:
    items = []
    for dist, name, ftype in [
        *[( ((x - point_xy[0]) ** 2 + (y - point_xy[1]) ** 2) ** 0.5, name, "hospital") for x, y, name in hospitals_xy],
        *[( ((x - point_xy[0]) ** 2 + (y - point_xy[1]) ** 2) ** 0.5, name, "school") for x, y, name in schools_xy],
        *[( ((x - point_xy[0]) ** 2 + (y - point_xy[1]) ** 2) ** 0.5, name, "shelter") for x, y, name in shelters_xy],
    ]:
        if dist <= config.FACILITY_LIST_MAX_DISTANCE_M:
            items.append({"type": ftype, "name": name, "distance_m": round(dist, 1)})
    for name, line in roads_named_lines:
        d = point.distance(line)
        if d <= config.FACILITY_LIST_MAX_DISTANCE_M:
            items.append({"type": "road", "name": name, "distance_m": round(d, 1)})
    items.sort(key=lambda it: it["distance_m"])
    return items[: config.FACILITY_LIST_MAX_ITEMS]


def _build_reason(p) -> str:
    parts = [f"{p.severity} severity" if p.severity else "Unknown severity"]
    if p.population_buffer_est is not None and p.population_buffer_est >= 1:
        parts.append(f"~{round(p.population_buffer_est)} people estimated nearby")
    candidates = []
    if p.nearest_hospital_m is not None:
        candidates.append((p.nearest_hospital_m, "hospital"))
    if p.nearest_school_m is not None:
        candidates.append((p.nearest_school_m, "school"))
    if candidates:
        dist, label = min(candidates, key=lambda c: c[0])
        parts.append(f"{dist:.0f} m from a {label}")
    return "; ".join(parts) + "."


def apply_hazard_zone(kept_polygons: list, hazard_zone_geom_4326) -> None:
    """Mutates in_hazard_zone on new_construction KEPT polygons whose
    centroid falls inside the user-provided hazard zone. hazard_zone_geom_4326
    is a shapely geometry in EPSG:4326; reprojected per-polygon to each
    polygon's own area CRS (safe even if polygons.area_crs is the same
    object for all, as it usually is within one analysis)."""
    if not kept_polygons or hazard_zone_geom_4326 is None:
        return
    for p in kept_polygons:
        if p.change_type != "new_construction":
            continue
        to_area = Transformer.from_crs("EPSG:4326", p.area_crs, always_xy=True).transform
        zone_area = shapely_transform(to_area, hazard_zone_geom_4326)
        p.in_hazard_zone = zone_area.contains(p.geometry.centroid)


def compute_priority(
    kept_polygons: list,
    facilities: dict,
    weights: dict = None,
    mode: str = "disaster",
) -> None:
    """Mutates nearest_hospital_m/name, nearest_school_m/name,
    nearest_main_road_m, nearby_facilities_json, priority_score,
    priority_rank and priority_reason on each polygon in place. No-op if
    there are no kept polygons."""
    if not kept_polygons:
        return

    w = weights or {
        "w1_severity": config.PRIORITY_W1_SEVERITY,
        "w2_population": config.PRIORITY_W2_POPULATION,
        "w3_facility_proximity": config.PRIORITY_W3_FACILITY_PROXIMITY,
        "w4_confidence": config.PRIORITY_W4_CONFIDENCE,
        "w5_route_impact": config.PRIORITY_W5_ROUTE_IMPACT,
    }

    area_crs = kept_polygons[0].area_crs
    to_area = Transformer.from_crs("EPSG:4326", area_crs, always_xy=True)

    hospitals_xy = [(*to_area.transform(f["lon"], f["lat"]), f["name"]) for f in facilities.get("hospitals", [])]
    schools_xy = [(*to_area.transform(f["lon"], f["lat"]), f["name"]) for f in facilities.get("schools", [])]
    shelters_xy = [(*to_area.transform(f["lon"], f["lat"]), f["name"]) for f in facilities.get("shelters", [])]

    from shapely.geometry import LineString
    roads_named_lines = [
        (r["name"], LineString([to_area.transform(lon, lat) for lon, lat in r["coords"]]))
        for r in facilities.get("roads", [])
        if len(r["coords"]) >= 2
    ]
    roads_lines = [line for _, line in roads_named_lines]

    for p in kept_polygons:
        centroid = p.geometry.centroid
        point_xy = (centroid.x, centroid.y)
        hosp_d, hosp_name = _nearest_point(point_xy, hospitals_xy)
        school_d, school_name = _nearest_point(point_xy, schools_xy)
        road_d = _nearest_road(centroid, roads_lines)

        p.nearest_hospital_m = round(hosp_d, 1) if hosp_d is not None else None
        p.nearest_hospital_name = hosp_name
        p.nearest_school_m = round(school_d, 1) if school_d is not None else None
        p.nearest_school_name = school_name
        p.nearest_main_road_m = round(road_d, 1) if road_d is not None else None
        p.nearby_facilities_json = json.dumps(
            _nearby_list(point_xy, hospitals_xy, schools_xy, shelters_xy, roads_named_lines, centroid)
        )

    population_values = [p.population_est for p in kept_polygons]
    norm_population = _normalize(population_values)

    for p, norm_pop in zip(kept_polygons, norm_population):
        facility_proximity = max(_closeness(p.nearest_hospital_m), _closeness(p.nearest_school_m))
        p.priority_score = round(
            w["w1_severity"] * (p.sev_score or 0.0)
            + w["w2_population"] * norm_pop
            + w["w3_facility_proximity"] * facility_proximity
            + w["w4_confidence"] * p.confidence
            + w["w5_route_impact"] * 0.0,
            4,
        )

    if mode == "prevention":
        kept_polygons.sort(
            key=lambda p: (p.in_hazard_zone and p.change_type == "new_construction", p.priority_score),
            reverse=True,
        )
    else:
        kept_polygons.sort(key=lambda p: p.priority_score, reverse=True)

    for i, p in enumerate(kept_polygons, start=1):
        p.priority_rank = i
        p.priority_reason = _build_reason(p)
