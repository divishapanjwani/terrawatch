import numpy as np
import pytest
from pyproj import CRS
from rasterio.transform import from_origin

from app import config
from app.geo.align import AlignedPair
from app.geo.quality import compute_cloud_mask, run_quality_check


def _make_aligned(before, after, pixel_size=1.0):
    crs = CRS.from_epsg(32643)
    transform = from_origin(370000, 2050000, pixel_size, pixel_size)
    h, w = before.shape[1], before.shape[2]
    mask = np.ones((h, w), dtype=bool)
    return AlignedPair(
        before=before,
        after=after,
        before_mask=mask,
        after_mask=mask,
        crs=crs,
        transform=transform,
        width=w,
        height=h,
        band_count=before.shape[0],
        dtype=str(before.dtype),
    )


def test_compute_cloud_mask_uses_scl_when_6_bands_present():
    bands = np.zeros((6, 10, 10), dtype=np.uint16)
    bands[5, 0:3, 0:3] = 9  # cloud high probability
    bands[5, 5:8, 5:8] = 4  # vegetation (not cloud)
    mask, method = compute_cloud_mask(bands)
    assert method == "scl"
    assert mask[0:3, 0:3].all()
    assert not mask[5:8, 5:8].any()


def test_compute_cloud_mask_falls_back_to_heuristic_without_scl():
    bands = np.full((4, 20, 20), 50, dtype=np.uint8)
    bands[2:6, 2:6, :] = 255  # bright, flat (R=G=B=255) patch -> cloud-like
    mask, method = compute_cloud_mask(bands)
    assert method == "brightness_heuristic"
    assert mask.dtype == bool


def test_misalignment_zero_for_identical_images():
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, size=(3, 64, 64)).astype(np.uint8)
    aligned = _make_aligned(img, img.copy())
    report, _, _ = run_quality_check(aligned)
    assert report.misalignment_px == pytest.approx(0.0, abs=0.05)
    assert not any("misalign" in w for w in report.warnings)


def test_misalignment_detects_known_shift():
    rng = np.random.default_rng(1)
    before = rng.integers(0, 255, size=(3, 80, 80)).astype(np.uint8)
    shift_px = 3
    after = np.zeros_like(before)
    after[:, :, shift_px:] = before[:, :, : 80 - shift_px]
    aligned = _make_aligned(before, after)
    report, _, _ = run_quality_check(aligned)
    assert report.misalignment_px == pytest.approx(shift_px, abs=0.5)
    assert any("misalign" in w for w in report.warnings)


def test_cloud_warning_triggered_above_threshold():
    before = np.full((4, 20, 20), 50, dtype=np.uint8)
    after = before.copy()
    # Make the whole after-image bright and flat -> ~100% cloud heuristic
    after[:3] = 255
    aligned = _make_aligned(before, after)
    report, _, _ = run_quality_check(aligned)
    assert report.after_cloud_pct > config.CLOUD_WARNING_PCT
    assert any("cloud" in w.lower() for w in report.warnings)


def test_no_warnings_for_clean_pair():
    rng = np.random.default_rng(2)
    before = rng.integers(60, 140, size=(4, 30, 30)).astype(np.uint8)
    after = before.copy()
    aligned = _make_aligned(before, after)
    report, _, _ = run_quality_check(aligned)
    assert report.warnings == []
