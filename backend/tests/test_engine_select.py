from unittest.mock import patch

import numpy as np
from pyproj import CRS
from rasterio.transform import from_origin

from app.engines import select
from app.geo.align import AlignedPair


def _make_aligned(pixel_size_m, band_count=4, crs_epsg=32643):
    crs = CRS.from_epsg(crs_epsg)
    transform = from_origin(370000, 2050000, pixel_size_m, pixel_size_m)
    shape = (band_count, 50, 50)
    mask = np.ones((50, 50), dtype=bool)
    return AlignedPair(
        before=np.zeros(shape, dtype=np.uint8),
        after=np.zeros(shape, dtype=np.uint8),
        before_mask=mask,
        after_mask=mask,
        crs=crs,
        transform=transform,
        width=50,
        height=50,
        band_count=band_count,
        dtype="uint8",
    )


def test_rule_based_choice_high_res_rgb_is_tinycd():
    aligned = _make_aligned(pixel_size_m=1.0, band_count=4)
    assert select.rule_based_choice(aligned) == "tinycd"


def test_rule_based_choice_sentinel2_resolution_is_engine2():
    aligned = _make_aligned(pixel_size_m=10.0, band_count=4)
    assert select.rule_based_choice(aligned) == "engine2"


def test_rule_based_choice_high_res_but_truly_multispectral_is_engine2():
    aligned = _make_aligned(pixel_size_m=1.0, band_count=13)
    assert select.rule_based_choice(aligned) == "engine2"


def test_auto_never_falls_back_to_tinycd_on_coarse_input_when_engine2_unavailable():
    """Regression test: a prior bug made the auto fallback chain route
    10m Sentinel-2 input to TinyCD when Engine 2 was unavailable, which the
    brief explicitly forbids ('Never run TinyCD on Sentinel-2')."""
    aligned = _make_aligned(pixel_size_m=10.0, band_count=4)
    with (
        patch.object(select.siamese, "is_available", return_value=True),
        patch.object(select.engine2, "is_available", return_value=False),
    ):
        resolution = select.resolve_engine(aligned, forced="auto")
    assert resolution.key == "spectral"
    assert resolution.rule_choice == "engine2"
    assert resolution.fell_back is True


def test_auto_uses_engine2_when_available_on_coarse_input():
    aligned = _make_aligned(pixel_size_m=10.0, band_count=4)
    with patch.object(select.engine2, "is_available", return_value=True):
        resolution = select.resolve_engine(aligned, forced="auto")
    assert resolution.key == "engine2"
    assert resolution.fell_back is False


def test_auto_tinycd_unavailable_falls_through_to_engine2_then_spectral():
    aligned = _make_aligned(pixel_size_m=1.0, band_count=3)
    with (
        patch.object(select.siamese, "is_available", return_value=False),
        patch.object(select.engine2, "is_available", return_value=True),
    ):
        resolution = select.resolve_engine(aligned, forced="auto")
    assert resolution.key == "engine2"
    assert resolution.rule_choice == "tinycd"
    assert resolution.fell_back is True

    with (
        patch.object(select.siamese, "is_available", return_value=False),
        patch.object(select.engine2, "is_available", return_value=False),
    ):
        resolution = select.resolve_engine(aligned, forced="auto")
    assert resolution.key == "spectral"


def test_forced_choice_unavailable_falls_back_to_spectral():
    aligned = _make_aligned(pixel_size_m=1.0, band_count=3)
    with patch.object(select.engine2, "is_available", return_value=False):
        resolution = select.resolve_engine(aligned, forced="engine2")
    assert resolution.key == "spectral"
    assert resolution.requested == "engine2"
    assert resolution.fell_back is True


def test_forced_spectral_always_used():
    aligned = _make_aligned(pixel_size_m=1.0, band_count=3)
    resolution = select.resolve_engine(aligned, forced="spectral")
    assert resolution.key == "spectral"
    assert resolution.fell_back is False
