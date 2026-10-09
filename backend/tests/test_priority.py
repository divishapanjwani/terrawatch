from pyproj import CRS
from shapely.geometry import Point, Polygon, box

from app.pipeline.priority import apply_hazard_zone, compute_priority

UTM_43N = CRS.from_epsg(32643)  # Wayanad's actual UTM zone


class _FakePolygon:
    def __init__(self, geometry, sev_score=0.5, confidence=0.7, severity="Medium",
                 change_type="other", population_est=0.0, population_buffer_est=0.0):
        self.geometry = geometry
        self.area_crs = UTM_43N
        self.sev_score = sev_score
        self.confidence = confidence
        self.severity = severity
        self.change_type = change_type
        self.population_est = population_est
        self.population_buffer_est = population_buffer_est
        self.nearest_hospital_m = None
        self.nearest_hospital_name = None
        self.nearest_school_m = None
        self.nearest_school_name = None
        self.nearest_main_road_m = None
        self.nearby_facilities_json = None
        self.in_hazard_zone = False
        self.priority_score = None
        self.priority_rank = None
        self.priority_reason = None


# Centroid of each polygon below, reprojected to EPSG:4326, is roughly
# (76.16, 11.47) -- near the real Wayanad facilities used in these tests.
def _square_at(cx, cy, half=10.0):
    return box(cx - half, cy - half, cx + half, cy + half)


def test_compute_priority_ranks_closer_facility_higher():
    """Two otherwise-identical polygons: the one closer to a hospital
    should score higher and rank #1."""
    from pyproj import Transformer
    to_utm = Transformer.from_crs("EPSG:4326", UTM_43N, always_xy=True)
    hx, hy = to_utm.transform(76.16, 11.47)

    near = _FakePolygon(_square_at(hx + 100, hy + 100))  # ~140m from the hospital
    far = _FakePolygon(_square_at(hx + 50000, hy + 50000))  # ~70km away, beyond proximity range
    facilities = {"hospitals": [{"lat": 11.47, "lon": 76.16, "name": "Test Hospital"}], "schools": []}

    compute_priority([near, far], facilities)

    assert near.priority_rank == 1
    assert far.priority_rank == 2
    assert near.nearest_hospital_m < far.nearest_hospital_m
    assert near.priority_score > far.priority_score


def test_compute_priority_weights_population():
    """With population weighted in, the higher-population polygon should
    score higher even with identical severity/confidence/facility distance."""
    p_low_pop = _FakePolygon(_square_at(622000, 1268000), population_est=0.0)
    p_high_pop = _FakePolygon(_square_at(622000, 1268000), population_est=1000.0)
    weights = {
        "w1_severity": 0.0, "w2_population": 1.0, "w3_facility_proximity": 0.0,
        "w4_confidence": 0.0, "w5_route_impact": 0.0,
    }

    compute_priority([p_low_pop, p_high_pop], {"hospitals": [], "schools": []}, weights=weights)

    assert p_high_pop.priority_score > p_low_pop.priority_score
    assert p_high_pop.priority_rank == 1


def test_compute_priority_reason_mentions_people_and_facility():
    p = _FakePolygon(_square_at(622000, 1268000), severity="High", population_buffer_est=420.0)
    facilities = {"hospitals": [{"lat": 11.47, "lon": 76.1602, "name": "Nearby Hospital"}], "schools": []}

    compute_priority([p], facilities)

    assert "High severity" in p.priority_reason
    assert "420 people" in p.priority_reason
    assert "hospital" in p.priority_reason


def test_compute_priority_no_facilities_no_crash():
    p = _FakePolygon(_square_at(622000, 1268000))
    compute_priority([p], {"hospitals": [], "schools": []})
    assert p.nearest_hospital_m is None
    assert p.nearest_school_m is None
    assert p.priority_rank == 1


def test_compute_priority_empty_list_is_noop():
    compute_priority([], {"hospitals": [], "schools": []})  # must not raise


def test_prevention_mode_ranks_hazard_zone_new_construction_first():
    """A low-severity new_construction polygon inside a hazard zone must
    outrank a high-severity polygon outside it, in Prevention mode."""
    inside = _FakePolygon(_square_at(622000, 1268000), sev_score=0.1, change_type="new_construction")
    outside = _FakePolygon(_square_at(622000, 1268200), sev_score=0.9, change_type="landslide_bare_soil")

    # Hazard zone in EPSG:4326 covering the "inside" polygon's centroid only.
    from pyproj import Transformer
    to_4326 = Transformer.from_crs(UTM_43N, "EPSG:4326", always_xy=True)
    cx, cy = inside.geometry.centroid.x, inside.geometry.centroid.y
    lon, lat = to_4326.transform(cx, cy)
    zone = Polygon([(lon - 0.01, lat - 0.01), (lon + 0.01, lat - 0.01), (lon + 0.01, lat + 0.01), (lon - 0.01, lat + 0.01)])

    apply_hazard_zone([inside, outside], zone)
    assert inside.in_hazard_zone is True
    assert outside.in_hazard_zone is False

    compute_priority([inside, outside], {"hospitals": [], "schools": []}, mode="prevention")
    assert inside.priority_rank == 1


def test_nearest_main_road_and_nearby_facilities():
    """A road line and a school both within FACILITY_LIST_MAX_DISTANCE_M
    should produce a correct nearest_main_road_m and show up in the
    nearby-facilities list, sorted by distance."""
    from pyproj import Transformer
    to_4326 = Transformer.from_crs(UTM_43N, "EPSG:4326", always_xy=True)

    p = _FakePolygon(_square_at(622000, 1268000))
    cx, cy = p.geometry.centroid.x, p.geometry.centroid.y
    road_lon1, road_lat1 = to_4326.transform(cx - 500, cy)
    road_lon2, road_lat2 = to_4326.transform(cx + 500, cy)  # road passes right through the polygon
    school_lon, school_lat = to_4326.transform(cx + 50, cy + 50)  # ~70m away

    facilities = {
        "hospitals": [],
        "schools": [{"lat": school_lat, "lon": school_lon, "name": "Close School"}],
        "shelters": [],
        "roads": [{"name": "Test Road", "highway": "primary", "coords": [[road_lon1, road_lat1], [road_lon2, road_lat2]]}],
    }

    compute_priority([p], facilities)

    assert p.nearest_main_road_m is not None
    assert p.nearest_main_road_m < 10  # road runs through the polygon's centroid

    import json
    nearby = json.loads(p.nearby_facilities_json)
    assert any(item["type"] == "school" and item["name"] == "Close School" for item in nearby)
    assert any(item["type"] == "road" and item["name"] == "Test Road" for item in nearby)
    # sorted by distance ascending
    assert nearby == sorted(nearby, key=lambda it: it["distance_m"])


def test_apply_hazard_zone_only_flags_new_construction():
    p = _FakePolygon(_square_at(622000, 1268000), change_type="landslide_bare_soil")
    huge_zone = box(-180, -90, 180, 90)  # covers everything
    apply_hazard_zone([p], huge_zone)
    assert p.in_hazard_zone is False  # not new_construction, never flagged
