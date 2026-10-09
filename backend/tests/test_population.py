import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS
from shapely.geometry import box

from app import config
from app.impact.population import compute_population, population_raster_path

UTM_43N = CRS.from_epsg(32643)


class _FakePolygon:
    def __init__(self, geometry):
        self.geometry = geometry
        self.area_crs = UTM_43N
        self.population_est = None
        self.population_buffer_est = None


def _write_synthetic_raster(path, value=10.0, pixel_deg=0.01, size=50, west=76.0, north=11.6):
    """A size x size raster, EPSG:4326, every pixel = `value`, centered
    roughly on the Wayanad test polygons below."""
    transform = Affine.translation(west, north) * Affine.scale(pixel_deg, -pixel_deg)
    arr = np.full((size, size), value, dtype="float32")
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=size,
        width=size,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-99999.0,
    ) as dst:
        dst.write(arr, 1)


def test_population_raster_path_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "POPULATION_RASTER_PATH", tmp_path / "does_not_exist.tif")
    assert population_raster_path() is None


def test_compute_population_skips_gracefully_when_raster_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "POPULATION_RASTER_PATH", tmp_path / "does_not_exist.tif")
    p = _FakePolygon(box(622000, 1268000, 622100, 1268100))
    used = compute_population([p], bounds_4326=(76.0, 11.4, 76.3, 11.6))
    assert used is False
    assert p.population_est is None
    assert p.population_buffer_est is None


def test_compute_population_sums_known_value(tmp_path, monkeypatch):
    raster_path = tmp_path / "pop.tif"
    _write_synthetic_raster(raster_path, value=10.0, pixel_deg=0.001, size=2000, west=75.9, north=11.7)
    monkeypatch.setattr(config, "POPULATION_RASTER_PATH", raster_path)

    # A 500m x 500m polygon in UTM 43N, centered near (76.16, 11.47) which
    # lies inside the synthetic raster's extent.
    from pyproj import Transformer

    to_utm = Transformer.from_crs("EPSG:4326", UTM_43N, always_xy=True)
    cx, cy = to_utm.transform(76.16, 11.47)
    poly = box(cx - 250, cy - 250, cx + 250, cy + 250)
    p = _FakePolygon(poly)

    used = compute_population([p], bounds_4326=(75.9, 11.3, 76.3, 11.6), buffer_m=100.0)

    assert used is True
    assert p.population_est is not None and p.population_est > 0
    # Buffer estimate (polygon + 100m ring) must be >= the polygon-only estimate.
    assert p.population_buffer_est >= p.population_est


def test_compute_population_empty_list_is_noop(tmp_path, monkeypatch):
    raster_path = tmp_path / "pop.tif"
    _write_synthetic_raster(raster_path)
    monkeypatch.setattr(config, "POPULATION_RASTER_PATH", raster_path)
    assert compute_population([], bounds_4326=(75.9, 11.3, 76.3, 11.6)) is False
