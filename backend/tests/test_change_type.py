from app import config
from app.pipeline.change_type import classify_change_type, apply_change_types


class _FakePolygon:
    def __init__(self, area_m2=1000.0, status="kept", extra=None):
        self.area_m2 = area_m2
        self.status = status
        self.extra = extra or {}
        self.change_type = None
        self.change_type_rule = None


def test_rgb_only_input_is_unavailable():
    p = _FakePolygon(extra={"ndwi_delta": 0.5})
    change_type, rule = classify_change_type(p, band_count=3)
    assert change_type == "other"
    assert "unavailable" in rule


def test_flooding_detected_from_ndwi():
    p = _FakePolygon(extra={
        "ndwi_delta": config.FLOODING_NDWI_THRESHOLD + 0.1, "ndvi_delta": 0.0, "ndbi_delta": 0.0,
    })
    change_type, rule = classify_change_type(p, band_count=4)
    assert change_type == "flooding"
    assert "NDWI" in rule


def test_landslide_bare_soil_detected():
    p = _FakePolygon(
        area_m2=config.LANDSLIDE_MIN_AREA_M2 + 100,
        extra={
            "ndwi_delta": 0.0,
            "ndvi_delta": config.LANDSLIDE_NDVI_THRESHOLD - 0.1,
            "ndbi_delta": config.LANDSLIDE_NDBI_CEILING - 0.01,
        },
    )
    change_type, rule = classify_change_type(p, band_count=5)
    assert change_type == "landslide_bare_soil"


def test_landslide_requires_minimum_area():
    """A small patch with a landslide-like spectral signature shouldn't be
    labeled a landslide -- real landslides are large."""
    p = _FakePolygon(
        area_m2=config.LANDSLIDE_MIN_AREA_M2 - 50,
        extra={
            "ndwi_delta": 0.0,
            "ndvi_delta": config.LANDSLIDE_NDVI_THRESHOLD - 0.1,
            "ndbi_delta": config.LANDSLIDE_NDBI_CEILING - 0.01,
        },
    )
    change_type, rule = classify_change_type(p, band_count=5)
    assert change_type != "landslide_bare_soil"


def test_landslide_with_bare_soil_ndbi_bump_not_new_construction():
    """Real Wayanad landslide polygon (ΔNDVI -0.13, ΔNDBI +0.085, texture
    0.47, 1.56M m²): too mild on ΔNDVI/ΔNDBI for the strict landslide rule,
    but a real landslide -- bare soil/debris raises ΔNDBI the same way
    construction does, and the strict rule's NDBI ceiling alone can't
    tell them apart. High texture change over a large contiguous area is
    the tell; this must not fall through to new_construction."""
    p = _FakePolygon(
        area_m2=1_556_600.0,
        extra={"ndwi_delta": 0.09, "ndvi_delta": -0.13, "ndbi_delta": 0.085, "texture_change_frac": 0.47},
    )
    change_type, rule = classify_change_type(p, band_count=6)
    assert change_type == "landslide_bare_soil"
    assert "texture" in rule


def test_new_construction_area_cap():
    """A sprawling high-ΔNDBI area without the landslide's texture/NDVI
    signature still shouldn't be labeled new_construction -- real
    construction footprints are small and local."""
    p = _FakePolygon(
        area_m2=config.NEW_CONSTRUCTION_MAX_AREA_M2 + 1000,
        extra={"ndwi_delta": 0.0, "ndvi_delta": 0.0, "ndbi_delta": config.NEW_CONSTRUCTION_NDBI_THRESHOLD + 0.05},
    )
    change_type, _ = classify_change_type(p, band_count=5)
    assert change_type != "new_construction"


def test_new_construction_detected():
    p = _FakePolygon(extra={
        "ndwi_delta": 0.0, "ndvi_delta": 0.0,
        "ndbi_delta": config.NEW_CONSTRUCTION_NDBI_THRESHOLD + 0.05,
    })
    change_type, rule = classify_change_type(p, band_count=5)
    assert change_type == "new_construction"


def test_structure_lost_detected():
    p = _FakePolygon(extra={
        "ndwi_delta": 0.0, "ndvi_delta": 0.0,
        "ndbi_delta": config.STRUCTURE_LOST_NDBI_THRESHOLD - 0.05,
    })
    change_type, rule = classify_change_type(p, band_count=5)
    assert change_type == "structure_lost"


def test_vegetation_loss_fallback():
    p = _FakePolygon(extra={
        "ndwi_delta": 0.0, "ndbi_delta": 0.0,
        "ndvi_delta": config.VEGETATION_LOSS_NDVI_THRESHOLD - 0.02,
    })
    change_type, rule = classify_change_type(p, band_count=4)
    assert change_type == "vegetation_loss"


def test_other_when_nothing_matches():
    p = _FakePolygon(extra={"ndwi_delta": 0.0, "ndvi_delta": 0.0, "ndbi_delta": 0.0})
    change_type, rule = classify_change_type(p, band_count=5)
    assert change_type == "other"


def test_flooding_checked_before_landslide():
    """A polygon with both a flood-level NDWI signal and a landslide-like
    NDVI/area/NDBI profile should be labeled flooding (checked first) --
    water presence takes priority over bare-soil inference."""
    p = _FakePolygon(
        area_m2=config.LANDSLIDE_MIN_AREA_M2 + 100,
        extra={
            "ndwi_delta": config.FLOODING_NDWI_THRESHOLD + 0.1,
            "ndvi_delta": config.LANDSLIDE_NDVI_THRESHOLD - 0.1,
            "ndbi_delta": config.LANDSLIDE_NDBI_CEILING - 0.01,
        },
    )
    change_type, _ = classify_change_type(p, band_count=5)
    assert change_type == "flooding"


def test_apply_change_types_skips_rejected_polygons():
    rejected = _FakePolygon(status="rejected", extra={"ndwi_delta": 0.5})
    kept = _FakePolygon(status="kept", extra={"ndwi_delta": 0.5, "ndvi_delta": 0.0, "ndbi_delta": 0.0})
    apply_change_types([rejected, kept], band_count=4)
    assert rejected.change_type is None
    assert kept.change_type == "flooding"
