"""Severity = change strength, not damage. See app/config.py for thresholds.

sev_score = max(norm(log1p(area_m2)), norm(log1p(change_magnitude)))
High >= 0.66, Medium >= 0.33, else Low.

norm() is min-max normalization across the polygons in THIS analysis (a
scene with only small changes still has a "biggest" one). A single-polygon
result normalizes to the midpoint (no other polygon to compare against).

Two deliberate choices, both fixing a real failure mode observed on
Wayanad (a 1.56M m^2 landslide, by far the largest kept polygon, scored
only "Medium"):

- log1p before normalizing. Polygon areas in this app can span 3+ orders
  of magnitude in one analysis. Plain min-max normalization lets a single
  huge outlier stretch the 0-1 range so far that every other real,
  substantial change (e.g. a 140,000 m^2 polygon) compresses to a
  near-zero score -- not just unfair to that polygon, but to the whole
  distribution. Log-scaling keeps the normalization sensitive to
  differences among the small/medium polygons too.
- max(), not an average, of the two normalized factors. A severity
  formed by averaging area and magnitude lets a massive, high-confidence
  change get capped by a merely-middling per-pixel magnitude (and vice
  versa). A change is severe if it is either very LARGE or very INTENSE;
  it shouldn't need to be both at once to earn High.
"""
import math

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
    log_areas = [math.log1p(max(p.area_m2, 0.0)) for p in polygons]
    log_mags = [math.log1p(max(p.change_magnitude, 0.0)) for p in polygons]
    norm_area = _normalize(log_areas)
    norm_mag = _normalize(log_mags)

    for p, na, nm in zip(polygons, norm_area, norm_mag):
        score = max(na, nm)
        p.sev_score = score
        if score >= SEVERITY_HIGH:
            p.severity = "High"
        elif score >= SEVERITY_MEDIUM:
            p.severity = "Medium"
        else:
            p.severity = "Low"
