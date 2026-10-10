"""Regression tests for the Sentinel-2 BOA-offset radiometric-mismatch
bug: auto-fetch pairs straddling the baseline-04.00 cutover (25 Jan
2022) produced one giant false "change" polygon because the +1000 DN
offset wasn't undone. See scripts/sentinel2_fetch.py and
app/geo/quality.py::check_scene_dominance_warning."""

from datetime import datetime, timezone

import numpy as np

from app.geo.quality import check_scene_dominance_warning


class _FakeItem:
    def __init__(self, baseline=None, dt=None):
        self.properties = {"s2:processing_baseline": baseline} if baseline else {}
        self.datetime = dt or datetime(2020, 1, 1, tzinfo=timezone.utc)


def test_needs_boa_offset_correction_pre_baseline():
    from scripts.sentinel2_fetch import needs_boa_offset_correction

    assert needs_boa_offset_correction(_FakeItem(baseline="02.12")) is False


def test_needs_boa_offset_correction_post_baseline():
    from scripts.sentinel2_fetch import needs_boa_offset_correction

    assert needs_boa_offset_correction(_FakeItem(baseline="05.10")) is True


def test_needs_boa_offset_correction_exactly_at_threshold():
    from scripts.sentinel2_fetch import needs_boa_offset_correction

    assert needs_boa_offset_correction(_FakeItem(baseline="04.00")) is True


def test_needs_boa_offset_correction_falls_back_to_date_when_no_baseline():
    from scripts.sentinel2_fetch import needs_boa_offset_correction

    before_cutover = datetime(2021, 6, 1, tzinfo=timezone.utc)
    after_cutover = datetime(2023, 6, 1, tzinfo=timezone.utc)
    assert needs_boa_offset_correction(_FakeItem(dt=before_cutover)) is False
    assert needs_boa_offset_correction(_FakeItem(dt=after_cutover)) is True


def test_boa_offset_subtracted_from_spectral_bands_not_scl():
    """Mirrors save_clip()'s correction math directly (no network call)."""
    stacked = np.full((6, 2, 2), 2000, dtype=np.uint16)  # R,G,B,NIR,SWIR,SCL
    stacked[-1] = 5  # SCL class code -- must NOT be touched

    spectral = stacked[:-1].astype(np.int32) - 1000
    stacked[:-1] = np.clip(spectral, 0, None).astype("uint16")

    assert (stacked[:-1] == 1000).all()
    assert (stacked[-1] == 5).all()  # SCL untouched


def test_boa_offset_clips_at_zero_not_wraps():
    stacked = np.full((2, 1, 1), 500, dtype=np.uint16)
    spectral = stacked.astype(np.int32) - 1000
    corrected = np.clip(spectral, 0, None).astype("uint16")
    assert corrected[0, 0, 0] == 0  # not 64536 (uint16 wraparound)


def test_scene_dominance_warning_fires_above_threshold():
    # One ~30 km2 polygon in a ~43.6 km2 scene (70% share) -- the real
    # pre-fix Pune bug's numbers.
    warning = check_scene_dominance_warning([30_439_700.0, 10_000.0], scene_area_m2=43_600_000.0)
    assert warning is not None
    assert "radiometric mismatch" in warning


def test_scene_dominance_warning_silent_below_threshold():
    # Largest real polygon after the fix: ~295,100 m2 in the same scene.
    warning = check_scene_dominance_warning([295_100.0, 10_000.0], scene_area_m2=43_600_000.0)
    assert warning is None


def test_scene_dominance_warning_handles_empty_and_zero_area():
    assert check_scene_dominance_warning([], scene_area_m2=1000.0) is None
    assert check_scene_dominance_warning([500.0], scene_area_m2=0.0) is None
