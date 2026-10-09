"""Priority score (KEPT polygons only, Disaster mode).

priority_score = w_severity * sev_score + w_confidence * confidence
                + w_hospital * closeness(nearest_hospital_m)
                + w_school * closeness(nearest_school_m)

closeness(d) = clamp(1 - d / PRIORITY_PROXIMITY_MAX_M, 0, 1) -- 1.0 right
next to a facility, 0 at or beyond PRIORITY_PROXIMITY_MAX_M. Weights and the
proximity cutoff are in app/config.py. priority_rank is the 1-based rank by
score, highest first; priority_reason is a plain-language sentence citing
severity and whichever of hospital/school is nearer.
"""
from pyproj import Transformer

from app import config


def _closeness(distance_m: float | None) -> float:
    if distance_m is None:
        return 0.0
    return max(0.0, 1.0 - distance_m / config.PRIORITY_PROXIMITY_MAX_M)


def _nearest(point_xy: tuple, facilities_xy: list) -> tuple:
    if not facilities_xy:
        return None, None
    px, py = point_xy
    best_d, best_name = None, None
    for x, y, name in facilities_xy:
        d = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        if best_d is None or d < best_d:
            best_d, best_name = d, name
    return best_d, best_name


def _build_reason(p) -> str:
    parts = [f"{p.severity} severity" if p.severity else "Unknown severity"]
    candidates = []
    if p.nearest_hospital_m is not None:
        candidates.append((p.nearest_hospital_m, "hospital"))
    if p.nearest_school_m is not None:
        candidates.append((p.nearest_school_m, "school"))
    if candidates:
        dist, label = min(candidates, key=lambda c: c[0])
        parts.append(f"{dist:.0f} m from a {label}")
    return "; ".join(parts) + "."


def compute_priority(kept_polygons: list, facilities: dict) -> None:
    """Mutates nearest_hospital_m/name, nearest_school_m/name,
    priority_score, priority_rank and priority_reason on each polygon
    in place. No-op if there are no kept polygons."""
    if not kept_polygons:
        return

    area_crs = kept_polygons[0].area_crs
    to_area = Transformer.from_crs("EPSG:4326", area_crs, always_xy=True)

    hospitals_xy = [
        (*to_area.transform(f["lon"], f["lat"]), f["name"])
        for f in facilities.get("hospitals", [])
    ]
    schools_xy = [
        (*to_area.transform(f["lon"], f["lat"]), f["name"])
        for f in facilities.get("schools", [])
    ]

    for p in kept_polygons:
        centroid = p.geometry.centroid
        hosp_d, hosp_name = _nearest((centroid.x, centroid.y), hospitals_xy)
        school_d, school_name = _nearest((centroid.x, centroid.y), schools_xy)
        p.nearest_hospital_m = round(hosp_d, 1) if hosp_d is not None else None
        p.nearest_hospital_name = hosp_name
        p.nearest_school_m = round(school_d, 1) if school_d is not None else None
        p.nearest_school_name = school_name

        p.priority_score = round(
            config.PRIORITY_WEIGHT_SEVERITY * (p.sev_score or 0.0)
            + config.PRIORITY_WEIGHT_CONFIDENCE * p.confidence
            + config.PRIORITY_WEIGHT_HOSPITAL_PROXIMITY * _closeness(hosp_d)
            + config.PRIORITY_WEIGHT_SCHOOL_PROXIMITY * _closeness(school_d),
            4,
        )

    kept_polygons.sort(key=lambda p: p.priority_score, reverse=True)
    for i, p in enumerate(kept_polygons, start=1):
        p.priority_rank = i
        p.priority_reason = _build_reason(p)
