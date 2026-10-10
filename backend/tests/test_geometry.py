import numpy as np
import pytest
from pyproj import CRS, Transformer
from rasterio.transform import from_origin

from app.geo.align import AlignedPair
from app.geo.vectorize import native_pixel_area_m2, resolve_area_crs, vectorize


def _make_aligned(width=500, height=500, pixel_size=1.0, crs_epsg=32643):
    crs = CRS.from_epsg(crs_epsg)
    transform = from_origin(370000, 2050000, pixel_size, pixel_size)
    before = np.zeros((3, height, width), dtype=np.uint8)
    after = np.zeros((3, height, width), dtype=np.uint8)
    mask = np.ones((height, width), dtype=bool)
    return AlignedPair(
        before=before,
        after=after,
        before_mask=mask,
        after_mask=mask,
        crs=crs,
        transform=transform,
        width=width,
        height=height,
        band_count=3,
        dtype="uint8",
    )


def test_native_pixel_area_m2_projected_crs():
    aligned = _make_aligned(pixel_size=2.0)
    assert native_pixel_area_m2(aligned) == pytest.approx(4.0)


def test_resolve_area_crs_returns_native_when_projected():
    aligned = _make_aligned()
    area_crs = resolve_area_crs(aligned.crs, (73.0, 18.0, 73.1, 18.1))
    assert area_crs == aligned.crs


def test_vectorize_area_m2_matches_known_rectangle():
    aligned = _make_aligned(pixel_size=1.0)
    # 30 x 20 pixel rectangle at 1 m/px -> 600 m^2, matching the known R1
    # "new building" fixture in terrawatch-test-pair.
    mask = np.zeros((aligned.height, aligned.width), dtype=bool)
    mask[100:120, 100:130] = True
    prob_map = np.where(mask, 0.9, 0.0).astype(np.float32)
    magnitude_map = np.where(mask, 50.0, 0.0).astype(np.float32)

    polygons = vectorize(mask, prob_map, magnitude_map, aligned, simplify_tolerance_m=0.0, engine="test")

    assert len(polygons) == 1
    assert polygons[0].area_m2 == pytest.approx(600.0, rel=0.01)


def test_vectorize_centroid_matches_independent_pyproj_conversion():
    aligned = _make_aligned(pixel_size=1.0)
    mask = np.zeros((aligned.height, aligned.width), dtype=bool)
    mask[100:120, 100:130] = True
    prob_map = np.where(mask, 0.9, 0.0).astype(np.float32)
    magnitude_map = np.where(mask, 50.0, 0.0).astype(np.float32)

    polygons = vectorize(mask, prob_map, magnitude_map, aligned, simplify_tolerance_m=0.0, engine="test")
    poly = polygons[0]

    # Independently compute the expected centroid: rows 100..119, cols
    # 100..129 -> world bounds x in [370100, 370130], y in [2049880, 2049900]
    # (pixel size 1 m, origin (370000, 2050000), y decreasing downward).
    expected_x, expected_y = 370115.0, 2049890.0
    transformer = Transformer.from_crs(aligned.crs, "EPSG:4326", always_xy=True)
    expected_lon, expected_lat = transformer.transform(expected_x, expected_y)

    assert poly.centroid_lon == pytest.approx(expected_lon, abs=1e-4)
    assert poly.centroid_lat == pytest.approx(expected_lat, abs=1e-4)


def test_vectorize_confidence_and_magnitude_are_mean_over_component():
    aligned = _make_aligned(pixel_size=1.0)
    mask = np.zeros((aligned.height, aligned.width), dtype=bool)
    mask[100:110, 100:110] = True  # 10x10 = 100 px, all same values below

    prob_map = np.zeros((aligned.height, aligned.width), dtype=np.float32)
    prob_map[100:110, 100:110] = 0.75
    magnitude_map = np.zeros((aligned.height, aligned.width), dtype=np.float32)
    magnitude_map[100:110, 100:110] = 42.0

    polygons = vectorize(mask, prob_map, magnitude_map, aligned, simplify_tolerance_m=0.0, engine="test")

    assert len(polygons) == 1
    assert polygons[0].confidence == pytest.approx(0.75, abs=1e-3)
    assert polygons[0].change_magnitude == pytest.approx(42.0, abs=1e-3)


def test_vectorize_drops_empty_mask():
    aligned = _make_aligned()
    mask = np.zeros((aligned.height, aligned.width), dtype=bool)
    prob_map = np.zeros((aligned.height, aligned.width), dtype=np.float32)
    magnitude_map = np.zeros((aligned.height, aligned.width), dtype=np.float32)

    polygons = vectorize(mask, prob_map, magnitude_map, aligned, simplify_tolerance_m=0.0, engine="test")
    assert polygons == []
