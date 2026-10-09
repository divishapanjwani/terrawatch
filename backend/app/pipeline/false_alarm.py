"""Classify each candidate polygon as kept or rejected, with a reason.

Checks run in this priority order (first match wins): cloud, too_small,
misalignment_edge, vegetation_seasonal, shadow_illumination. Checks that
need bands/features the input doesn't have (e.g. NDVI on RGB-only input)
are skipped and reported as "unavailable" rather than silently treated as
false.
"""
from dataclasses import dataclass

from app import config
from app.geo.vectorize import PolygonResult

REASONS = ["cloud", "too_small", "misalignment_edge", "vegetation_seasonal", "shadow_illumination"]

REASON_LABELS = {
    "cloud": "Rejected: overlaps a cloud in the before or after image.",
    "too_small": "Rejected: smaller than the minimum area for a real change.",
    "misalignment_edge": "Rejected: sits at the edge of the valid image area, likely an alignment artifact.",
    "vegetation_seasonal": "Rejected: looks like a seasonal vegetation change (color shift only, no sign of construction, water, or bare soil).",
    "shadow_illumination": "Rejected: brightness changed but the underlying structure/texture didn't -- likely a shadow or lighting change.",
}


@dataclass
class AvailableChecks:
    vegetation: bool
    shadow: bool  # texture-based shadow check needs at least RGB, always available
    cloud: bool  # always available (SCL or brightness heuristic)
    edge: bool  # always available
    too_small: bool  # always available


def available_checks(band_count: int) -> AvailableChecks:
    return AvailableChecks(
        vegetation=band_count >= 4,  # needs NDVI (R,NIR) at minimum
        shadow=True,
        cloud=True,
        edge=True,
        too_small=True,
    )


def classify(p: PolygonResult, band_count: int, cloud_method: str = "brightness_heuristic") -> tuple[str, str | None]:
    """Returns (status, reject_reason). status is "kept" or "rejected"."""
    checks = available_checks(band_count)
    extra = p.extra

    # too_small first: a trivial noise blob shouldn't get a more specific-
    # sounding (and possibly coincidental) reason like "cloud" or "shadow".
    if checks.too_small and p.area_m2 < config.TOO_SMALL_AREA_M2:
        return "rejected", "too_small"

    cloud_threshold = (
        config.CLOUD_OVERLAP_FRAC_THRESHOLD_SCL if cloud_method == "scl"
        else config.CLOUD_OVERLAP_FRAC_THRESHOLD_HEURISTIC
    )
    if checks.cloud and extra.get("cloud_overlap", 0.0) >= cloud_threshold:
        return "rejected", "cloud"

    if checks.edge and extra.get("edge_touch", 0.0) >= config.EDGE_TOUCH_FRAC_THRESHOLD:
        return "rejected", "misalignment_edge"

    if checks.vegetation:
        ndvi_d = extra.get("ndvi_delta", 0.0)
        ndbi_d = extra.get("ndbi_delta", 0.0)
        ndwi_d = extra.get("ndwi_delta", 0.0)
        texture_frac = extra.get("texture_change_frac", 1.0)
        if (
            abs(ndvi_d) >= config.VEGETATION_SEASONAL_NDVI_THRESHOLD
            and abs(ndbi_d) < config.VEGETATION_SEASONAL_NDBI_CEILING
            and abs(ndwi_d) < config.VEGETATION_SEASONAL_NDWI_CEILING
            and texture_frac < config.VEGETATION_SEASONAL_TEXTURE_CEILING
        ):
            return "rejected", "vegetation_seasonal"

    if checks.shadow:
        brightness_frac = extra.get("brightness_delta_frac", 0.0)
        texture_frac = extra.get("texture_change_frac", 1.0)
        if (
            abs(brightness_frac) >= config.SHADOW_BRIGHTNESS_FRAC_THRESHOLD
            and texture_frac < config.SHADOW_TEXTURE_FRAC_THRESHOLD
        ):
            return "rejected", "shadow_illumination"

    return "kept", None


def apply_false_alarm_filter(
    polygons: list[PolygonResult], band_count: int, cloud_method: str = "brightness_heuristic"
) -> None:
    """Mutates each polygon's .status, .reject_reason, .needs_review in place."""
    for p in polygons:
        status, reason = classify(p, band_count, cloud_method)
        p.status = status
        p.reject_reason = reason
        p.needs_review = p.confidence < config.CONFIDENCE_NEEDS_REVIEW_THRESHOLD
