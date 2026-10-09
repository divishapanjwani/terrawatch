from app import config
from app.pipeline.false_alarm import available_checks, classify


class _FakePolygon:
    def __init__(self, area_m2=1000.0, confidence=0.8, extra=None):
        self.area_m2 = area_m2
        self.confidence = confidence
        self.extra = extra or {}


def test_available_checks_rgb_only_disables_vegetation():
    checks = available_checks(band_count=3)
    assert checks.vegetation is False
    assert checks.shadow is True
    assert checks.cloud is True
    assert checks.edge is True
    assert checks.too_small is True


def test_available_checks_with_nir_enables_vegetation():
    checks = available_checks(band_count=4)
    assert checks.vegetation is True


def test_too_small_rejected():
    p = _FakePolygon(area_m2=config.TOO_SMALL_AREA_M2 - 1)
    status, reason = classify(p, band_count=4)
    assert status == "rejected"
    assert reason == "too_small"


def test_large_enough_not_rejected_as_too_small():
    p = _FakePolygon(area_m2=config.TOO_SMALL_AREA_M2 + 1000)
    status, reason = classify(p, band_count=4)
    assert reason != "too_small"


def test_cloud_rejected_scl_method():
    p = _FakePolygon(extra={"cloud_overlap": config.CLOUD_OVERLAP_FRAC_THRESHOLD_SCL + 0.01})
    status, reason = classify(p, band_count=6, cloud_method="scl")
    assert status == "rejected"
    assert reason == "cloud"


def test_cloud_not_rejected_below_scl_threshold():
    p = _FakePolygon(extra={"cloud_overlap": config.CLOUD_OVERLAP_FRAC_THRESHOLD_SCL - 0.1})
    status, reason = classify(p, band_count=6, cloud_method="scl")
    assert reason != "cloud"


def test_cloud_heuristic_uses_lower_more_conservative_threshold():
    # A value that would trigger under the SCL threshold but is below the
    # (lower) heuristic threshold still rejects -- but a value between the
    # two thresholds should only reject under heuristic, not under... wait,
    # heuristic threshold is LOWER so it rejects MORE readily; confirm that
    # a value above the heuristic threshold but below the SCL threshold
    # rejects under heuristic method and not under scl method.
    mid_value = (config.CLOUD_OVERLAP_FRAC_THRESHOLD_HEURISTIC + config.CLOUD_OVERLAP_FRAC_THRESHOLD_SCL) / 2
    p = _FakePolygon(extra={"cloud_overlap": mid_value})
    status_heuristic, reason_heuristic = classify(p, band_count=3, cloud_method="brightness_heuristic")
    status_scl, reason_scl = classify(p, band_count=3, cloud_method="scl")
    assert reason_heuristic == "cloud"
    assert reason_scl != "cloud"


def test_misalignment_edge_rejected():
    p = _FakePolygon(extra={"edge_touch": config.EDGE_TOUCH_FRAC_THRESHOLD + 0.1})
    status, reason = classify(p, band_count=4)
    assert status == "rejected"
    assert reason == "misalignment_edge"


def test_vegetation_seasonal_rejected_when_ndvi_dominant_and_low_texture():
    p = _FakePolygon(
        extra={
            "ndvi_delta": -0.3,
            "ndbi_delta": 0.0,
            "ndwi_delta": 0.0,
            "texture_change_frac": 0.05,
        }
    )
    status, reason = classify(p, band_count=4)
    assert status == "rejected"
    assert reason == "vegetation_seasonal"


def test_vegetation_seasonal_not_triggered_with_high_texture_change():
    """A landslide can share a large |ΔNDVI| with seasonal vegetation loss,
    but it also changes ground texture/structure -- that's the
    discriminator. High texture change should NOT be classified as
    vegetation_seasonal even with a big NDVI shift."""
    p = _FakePolygon(
        extra={
            "ndvi_delta": -0.6,
            "ndbi_delta": 0.0,
            "ndwi_delta": 0.0,
            "texture_change_frac": config.VEGETATION_SEASONAL_TEXTURE_CEILING + 0.1,
            "brightness_delta_frac": 0.0,
        }
    )
    status, reason = classify(p, band_count=4)
    assert reason != "vegetation_seasonal"


def test_vegetation_seasonal_not_triggered_with_builtup_signal():
    p = _FakePolygon(
        extra={
            "ndvi_delta": -0.3,
            "ndbi_delta": config.VEGETATION_SEASONAL_NDBI_CEILING + 0.1,
            "ndwi_delta": 0.0,
            "texture_change_frac": 0.05,
        }
    )
    status, reason = classify(p, band_count=4)
    assert reason != "vegetation_seasonal"


def test_vegetation_unavailable_for_rgb_only_input():
    """RGB-only (3-band) input can't compute NDVI (needs NIR) -- the
    vegetation_seasonal rule must not fire even if the (unavailable)
    feature happens to be present in extra."""
    p = _FakePolygon(
        extra={
            "ndvi_delta": -0.5,
            "ndbi_delta": 0.0,
            "ndwi_delta": 0.0,
            "texture_change_frac": 0.05,
        }
    )
    status, reason = classify(p, band_count=3)
    assert reason != "vegetation_seasonal"


def test_shadow_illumination_rejected_brightness_only():
    p = _FakePolygon(extra={"brightness_delta_frac": 0.5, "texture_change_frac": 0.01})
    status, reason = classify(p, band_count=3)
    assert status == "rejected"
    assert reason == "shadow_illumination"


def test_shadow_illumination_not_triggered_with_real_texture_change():
    p = _FakePolygon(
        extra={
            "brightness_delta_frac": 0.5,
            "texture_change_frac": config.SHADOW_TEXTURE_FRAC_THRESHOLD + 0.2,
        }
    )
    status, reason = classify(p, band_count=3)
    assert reason != "shadow_illumination"


def test_kept_when_no_rule_matches():
    p = _FakePolygon(
        area_m2=5000,
        extra={
            "ndvi_delta": 0.0,
            "ndbi_delta": 0.0,
            "ndwi_delta": 0.0,
            "brightness_delta_frac": 0.0,
            "texture_change_frac": 0.5,
            "cloud_overlap": 0.0,
            "edge_touch": 0.0,
        },
    )
    status, reason = classify(p, band_count=4)
    assert status == "kept"
    assert reason is None


def test_too_small_takes_priority_over_cloud():
    """A trivial noise blob shouldn't get a coincidental 'cloud' label --
    too_small is checked first."""
    p = _FakePolygon(area_m2=1.0, extra={"cloud_overlap": 0.9})
    status, reason = classify(p, band_count=4)
    assert reason == "too_small"


def test_needs_review_flag_from_apply_filter():
    from app.pipeline.false_alarm import apply_false_alarm_filter

    low_conf = _FakePolygon(area_m2=5000, confidence=config.CONFIDENCE_NEEDS_REVIEW_THRESHOLD - 0.1)
    high_conf = _FakePolygon(area_m2=5000, confidence=config.CONFIDENCE_NEEDS_REVIEW_THRESHOLD + 0.1)
    polygons = [low_conf, high_conf]
    apply_false_alarm_filter(polygons, band_count=3)
    assert low_conf.needs_review is True
    assert high_conf.needs_review is False
