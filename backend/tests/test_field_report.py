"""Unit tests for the field report's localized reason builder and
context assembly (app/reports/field_report.py) -- no network calls, no
PDF rendering (that needs system Pango/Cairo, covered by manual/CI smoke
testing instead, not unit tests)."""

from app.reports.field_report import _localized_reason, build_context
from app.reports.i18n import get_translations


def _props(**overrides):
    base = {
        "severity": "High",
        "population_buffer_est": 936.0,
        "nearest_hospital_m": 7637.7,
        "nearest_school_m": 576.2,
        "route_impact": "no_alternative",
        "detour_m": None,
        "in_hazard_zone": False,
    }
    base.update(overrides)
    return base


def test_localized_reason_en_matches_expected_shape():
    t = get_translations("en")
    reason = _localized_reason(_props(), t)
    assert "High severity" in reason
    assert "~936 people estimated nearby" in reason
    assert "576 m from a school" in reason
    assert "possible blockage — verify on ground" in reason


def test_localized_reason_hi_is_not_english():
    t = get_translations("hi")
    reason = _localized_reason(_props(), t)
    assert "severity" not in reason  # no English leaking through
    assert "936" in reason  # the number itself is still inserted verbatim
    assert "संभावित अवरोध" in reason


def test_localized_reason_mr_is_not_english():
    t = get_translations("mr")
    reason = _localized_reason(_props(), t)
    assert "severity" not in reason
    assert "936" in reason
    assert "संभाव्य अडथळा" in reason


def test_localized_reason_detour_phrase():
    t = get_translations("en")
    reason = _localized_reason(_props(route_impact="detour", detour_m=1234.0), t)
    assert "1234 m detour" in reason


def test_localized_reason_no_route_impact_omits_route_phrase():
    t = get_translations("en")
    reason = _localized_reason(_props(route_impact=None), t)
    assert "blockage" not in reason


def test_localized_reason_hazard_zone_prefix():
    t = get_translations("en")
    reason = _localized_reason(_props(in_hazard_zone=True), t)
    assert reason.startswith(t["hazard_zone_wording"])


class _FakeAnalysis:
    id = "test123"
    engine = "unet_oscd"
    kept_count = 2
    rejected_count = 1
    total_population_buffer_est = 100.0
    near_facility_count = 1


def test_build_context_ranks_and_rounds(tmp_path):
    kept_features = [
        {
            "properties": {
                "priority_rank": 2.0,
                "change_type": "other",
                "area_m2": 500.0,
                "population_buffer_est": 10.0,
                "severity": "Low",
                "nearest_hospital_m": None,
                "nearest_hospital_name": None,
                "nearest_school_m": None,
                "route_impact": None,
                "detour_m": None,
                "in_hazard_zone": False,
                "centroid_lat": 11.0,
                "centroid_lon": 76.0,
            },
            "geometry": {"type": "Polygon", "coordinates": [[[76.0, 11.0]]]},
        },
        {
            "properties": {
                "priority_rank": 1.0,
                "change_type": "new_construction",
                "area_m2": 1000.0,
                "population_buffer_est": 50.0,
                "severity": "High",
                "nearest_hospital_m": None,
                "nearest_hospital_name": None,
                "nearest_school_m": None,
                "route_impact": None,
                "detour_m": None,
                "in_hazard_zone": False,
                "centroid_lat": 11.1,
                "centroid_lon": 76.1,
            },
            "geometry": {"type": "Polygon", "coordinates": [[[76.1, 11.1]]]},
        },
    ]
    ctx = build_context(_FakeAnalysis(), kept_features, "en", str(tmp_path / "missing.png"))
    assert ctx["rows"][0]["rank"] == 1  # sorted by priority_rank, not list order
    assert ctx["rows"][0]["type"] == "New construction"
    assert ctx["snapshot_data_uri"] is None  # missing file -> gracefully None, not a crash
    assert ctx["area_changed_km2"] == "0.0"  # (500+1000) m2 -> ~0.0015 km2, rounds to 0.0
