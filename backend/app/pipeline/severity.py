"""Severity = change strength, not damage. See app/config.py for thresholds.

sev_score = 0.5 * norm(area_m2) + 0.5 * norm(change_magnitude)
High >= 0.66, Medium >= 0.33, else Low.

norm() is min-max normalization across the polygons in THIS analysis (a
scene with only small changes still has a "biggest" one). A single-polygon
result normalizes to the midpoint (no other polygon to compare against).
"""
from app.config import SEVERITY_HIGH, SEVERITY_MEDIUM


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def score_severity(polygons: list) -> None:
    """Mutates each polygon's .sev_score and .severity in place."""
    areas = [p.area_m2 for p in polygons]
    magnitudes = [p.change_magnitude for p in polygons]
    norm_area = _normalize(areas)
    norm_mag = _normalize(magnitudes)

    for p, na, nm in zip(polygons, norm_area, norm_mag):
        score = 0.5 * na + 0.5 * nm
        p.sev_score = score
        if score >= SEVERITY_HIGH:
            p.severity = "High"
        elif score >= SEVERITY_MEDIUM:
            p.severity = "Medium"
        else:
            p.severity = "Low"
