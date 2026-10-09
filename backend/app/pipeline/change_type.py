"""Estimate a change type for KEPT polygons, rule-based on spectral index
deltas. Marked "estimated" everywhere it's shown -- this is a heuristic
label, not a confirmed classification. Checked in this priority order
(first match wins): flooding, landslide_bare_soil, new_construction,
structure_lost, vegetation_loss, other.
"""
from app import config
from app.geo.vectorize import PolygonResult

CHANGE_TYPES = [
    "new_construction", "structure_lost", "flooding",
    "landslide_bare_soil", "vegetation_loss", "other",
]


def classify_change_type(p: PolygonResult, band_count: int) -> tuple[str, str]:
    """Returns (change_type, rule_description)."""
    if band_count < 4:
        return "other", "spectral indices unavailable (RGB-only input, needs NIR for NDVI/NDWI/NDBI)"

    extra = p.extra
    ndvi_d = extra.get("ndvi_delta")
    ndwi_d = extra.get("ndwi_delta")
    ndbi_d = extra.get("ndbi_delta")

    if ndwi_d is not None and ndwi_d >= config.FLOODING_NDWI_THRESHOLD:
        return "flooding", f"ΔNDWI {ndwi_d:+.2f} >= {config.FLOODING_NDWI_THRESHOLD} (water increased)"

    if (
        ndvi_d is not None and ndbi_d is not None
        and ndvi_d <= config.LANDSLIDE_NDVI_THRESHOLD
        and ndbi_d < config.LANDSLIDE_NDBI_CEILING
        and p.area_m2 >= config.LANDSLIDE_MIN_AREA_M2
    ):
        return (
            "landslide_bare_soil",
            f"ΔNDVI {ndvi_d:+.2f} <= {config.LANDSLIDE_NDVI_THRESHOLD} and ΔNDBI "
            f"{ndbi_d:+.2f} < {config.LANDSLIDE_NDBI_CEILING} on a {p.area_m2:,.0f} m² area "
            "(vegetation loss without a built-up signature, large area)",
        )

    if ndbi_d is not None and ndbi_d >= config.NEW_CONSTRUCTION_NDBI_THRESHOLD:
        return "new_construction", f"ΔNDBI {ndbi_d:+.2f} >= {config.NEW_CONSTRUCTION_NDBI_THRESHOLD} (built-up signature increased)"

    if ndbi_d is not None and ndbi_d <= config.STRUCTURE_LOST_NDBI_THRESHOLD:
        return "structure_lost", f"ΔNDBI {ndbi_d:+.2f} <= {config.STRUCTURE_LOST_NDBI_THRESHOLD} (built-up signature decreased)"

    if ndvi_d is not None and ndvi_d <= config.VEGETATION_LOSS_NDVI_THRESHOLD:
        return "vegetation_loss", f"ΔNDVI {ndvi_d:+.2f} <= {config.VEGETATION_LOSS_NDVI_THRESHOLD} (vegetation loss)"

    return "other", "no change-type rule matched"


def apply_change_types(polygons: list[PolygonResult], band_count: int) -> None:
    """Mutates .change_type / .change_type_rule for KEPT polygons only."""
    for p in polygons:
        if p.status != "kept":
            continue
        change_type, rule = classify_change_type(p, band_count)
        p.change_type = change_type
        p.change_type_rule = rule
