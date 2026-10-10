"""Unit tests for app/geo/fetch.py -- bbox resolution and the
draw-a-box size guard (no network calls; geocoding/STAC fetch paths
aren't exercised here)."""

import pytest

from app.geo.fetch import FetchError, resolve_bbox


def test_resolve_bbox_passthrough():
    bbox = (76.12, 11.44, 76.18, 11.51)
    assert resolve_bbox(None, bbox) == bbox


def test_resolve_bbox_requires_place_or_bbox():
    with pytest.raises(FetchError):
        resolve_bbox(None, None)


def test_resolve_bbox_rejects_oversized_box():
    # ~70km x 75km -- the real box drawn during testing that never
    # finished fetching before this guard was added.
    huge = (80.827, 22.000, 81.464, 22.697)
    with pytest.raises(FetchError, match="too large"):
        resolve_bbox(None, huge)


def test_resolve_bbox_accepts_wayanad_scale_box():
    wayanad_scale = (76.12, 11.44, 76.18, 11.51)
    assert resolve_bbox(None, wayanad_scale) == wayanad_scale


def test_resolve_bbox_accepts_box_right_at_the_limit():
    from app import config

    limit = config.FETCH_MAX_BBOX_SIDE_DEG
    box = (76.0, 11.0, 76.0 + limit, 11.0 + limit)
    assert resolve_bbox(None, box) == box


def test_resolve_bbox_rejects_box_just_over_the_limit():
    from app import config

    limit = config.FETCH_MAX_BBOX_SIDE_DEG
    box = (76.0, 11.0, 76.0 + limit + 0.01, 11.0 + limit)
    with pytest.raises(FetchError, match="too large"):
        resolve_bbox(None, box)
