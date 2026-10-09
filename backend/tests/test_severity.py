import pytest

from app.config import SEVERITY_HIGH, SEVERITY_MEDIUM
from app.pipeline.severity import score_severity, _normalize


class _FakePolygon:
    def __init__(self, area_m2, change_magnitude):
        self.area_m2 = area_m2
        self.change_magnitude = change_magnitude
        self.sev_score = None
        self.severity = None


def test_normalize_min_max():
    assert _normalize([0.0, 50.0, 100.0]) == pytest.approx([0.0, 0.5, 1.0])


def test_normalize_single_value_is_midpoint():
    assert _normalize([42.0]) == pytest.approx([0.5])


def test_normalize_all_equal_is_midpoint():
    assert _normalize([10.0, 10.0, 10.0]) == pytest.approx([0.5, 0.5, 0.5])


def test_normalize_empty():
    assert _normalize([]) == []


def test_score_severity_thresholds_still_honored():
    # Both factors span the full range together -> min gets 0 on both
    # (sev_score 0, Low), max gets 1 on both (sev_score 1, High).
    polygons = [
        _FakePolygon(area_m2=0, change_magnitude=0),
        _FakePolygon(area_m2=100, change_magnitude=100),
    ]
    score_severity(polygons)
    assert polygons[0].sev_score == pytest.approx(0.0)
    assert polygons[0].severity == "Low"
    assert polygons[1].sev_score == pytest.approx(1.0)
    assert polygons[1].severity == "High"


def test_score_severity_single_polygon_is_medium_midpoint():
    polygons = [_FakePolygon(area_m2=1234, change_magnitude=56)]
    score_severity(polygons)
    assert polygons[0].sev_score == pytest.approx(0.5)
    assert polygons[0].severity == "Medium"  # 0.5 is >= SEVERITY_MEDIUM (0.33), < SEVERITY_HIGH (0.66)


def test_log_scaling_prevents_one_outlier_crushing_everyone_else():
    """Regression test for the real Wayanad bug: a single huge-area
    polygon must not compress every other substantial polygon's
    normalized score toward zero. Under plain linear min-max, the
    50,000 m^2 polygon here would normalize to ~0.05 (50_000/1_000_000);
    log-scaling keeps it meaningfully separated from the tiny one."""
    polygons = [
        _FakePolygon(area_m2=100, change_magnitude=0),
        _FakePolygon(area_m2=50_000, change_magnitude=0),
        _FakePolygon(area_m2=1_000_000, change_magnitude=0),
    ]
    score_severity(polygons)
    assert polygons[1].sev_score > 0.3


def test_max_combination_large_area_alone_reaches_high():
    """A genuinely massive polygon with only middling magnitude must
    still reach High -- regression test for the real bug where the
    1.56M m^2 Wayanad landslide (the single largest kept polygon, area
    norm = 1.0) scored only "Medium" because averaging with a
    middle-of-the-pack magnitude dragged it down."""
    polygons = [
        _FakePolygon(area_m2=10, change_magnitude=5000),
        _FakePolygon(area_m2=1_500_000, change_magnitude=1200),
    ]
    score_severity(polygons)
    assert polygons[1].severity == "High"


def test_max_combination_high_magnitude_alone_reaches_high():
    """Symmetric case: a small polygon with an extreme per-pixel
    magnitude is also severe, even with a small, unremarkable area --
    max() must not favor area over magnitude either."""
    polygons = [
        _FakePolygon(area_m2=1_500_000, change_magnitude=10),
        _FakePolygon(area_m2=50, change_magnitude=9000),
    ]
    score_severity(polygons)
    assert polygons[1].severity == "High"


def test_zero_area_and_magnitude_is_not_an_error():
    polygons = [_FakePolygon(area_m2=0, change_magnitude=0), _FakePolygon(area_m2=500, change_magnitude=500)]
    score_severity(polygons)  # must not raise (log1p(0) == 0, fine)
    assert polygons[0].sev_score == pytest.approx(0.0)
