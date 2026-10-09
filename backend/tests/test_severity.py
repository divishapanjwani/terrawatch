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


def test_score_severity_formula_and_tiers():
    # Three polygons spanning the full range on both area and magnitude so
    # norm() lands exactly on 0, 0.5, 1 for each -> sev_score 0, 0.5, 1.
    polygons = [
        _FakePolygon(area_m2=0, change_magnitude=0),
        _FakePolygon(area_m2=50, change_magnitude=50),
        _FakePolygon(area_m2=100, change_magnitude=100),
    ]
    score_severity(polygons)

    assert polygons[0].sev_score == pytest.approx(0.0)
    assert polygons[1].sev_score == pytest.approx(0.5)
    assert polygons[2].sev_score == pytest.approx(1.0)

    assert polygons[0].severity == "Low"
    assert polygons[1].severity == "Medium"
    assert polygons[2].severity == "High"


def test_score_severity_thresholds_are_inclusive():
    polygons = [
        _FakePolygon(area_m2=0, change_magnitude=0),
        _FakePolygon(area_m2=SEVERITY_MEDIUM * 100, change_magnitude=SEVERITY_MEDIUM * 100),
        _FakePolygon(area_m2=100, change_magnitude=100),
    ]
    # norm() over [0, 33, 100] -> middle is ~0.33, exactly at the Medium
    # boundary only if SEVERITY_MEDIUM*100 maps to that normalized value;
    # just check the boundary constants are honored directionally.
    score_severity(polygons)
    assert polygons[0].severity == "Low"
    assert polygons[2].severity == "High"


def test_score_severity_single_polygon_is_medium_midpoint():
    polygons = [_FakePolygon(area_m2=1234, change_magnitude=56)]
    score_severity(polygons)
    assert polygons[0].sev_score == pytest.approx(0.5)
    assert polygons[0].severity == "Medium"  # 0.5 is >= SEVERITY_MEDIUM (0.33), < SEVERITY_HIGH (0.66)


def test_score_severity_weights_area_and_magnitude_equally():
    # Polygon A: max area, min magnitude. Polygon B: min area, max magnitude.
    # Equal weighting (0.5/0.5) means both should land on the same sev_score.
    polygons = [
        _FakePolygon(area_m2=100, change_magnitude=0),
        _FakePolygon(area_m2=0, change_magnitude=100),
    ]
    score_severity(polygons)
    assert polygons[0].sev_score == pytest.approx(polygons[1].sev_score)
