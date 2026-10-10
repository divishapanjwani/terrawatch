"""Auto-fetch: place name or drawn bbox + before/after date ranges + max
cloud % -> lowest-cloud Sentinel-2 L2A scenes from Microsoft Planetary
Computer, clipped to the bbox, saved as the same 6-band (R,G,B,NIR,SWIR,
SCL) GeoTIFF format scripts/sentinel2_fetch.py already uses for the
Wayanad demo pair -- so the result feeds the normal pipeline unchanged.

Geocoding uses OpenStreetMap's Nominatim (no key needed, usage-policy
rate limit of 1 req/sec -- see NOMINATIM_MIN_INTERVAL_S below).
"""

import sys
import time
from pathlib import Path
from typing import Optional

import requests

from app import config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.sentinel2_fetch import find_scene, open_catalog, save_clip  # noqa: E402

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "TerraWatch-AI/1.0 (disaster-response demo; see README.md)"

_last_nominatim_call = 0.0


class FetchError(Exception):
    """Raised for any user-facing auto-fetch failure (geocoding failed,
    no scene found under the cloud threshold, etc). Message is shown
    as-is in the UI, so keep it in plain language."""


def geocode_place(place: str) -> tuple[float, float]:
    """Returns (lat, lon) for a place name via Nominatim. Raises
    FetchError if nothing matches -- never silently guesses a location."""
    global _last_nominatim_call
    wait = config.NOMINATIM_MIN_INTERVAL_S - (time.monotonic() - _last_nominatim_call)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": place, "format": "json", "limit": 1, "countrycodes": "in"},
            headers={"User-Agent": NOMINATIM_USER_AGENT},
            timeout=10,
        )
        _last_nominatim_call = time.monotonic()
        resp.raise_for_status()
        results = resp.json()
    except requests.RequestException as exc:
        raise FetchError(f"Place search failed (network error): {exc}") from exc
    if not results:
        raise FetchError(f"Could not find '{place}' in India. Try a more specific place name.")
    return float(results[0]["lat"]), float(results[0]["lon"])


def bbox_from_point(lat: float, lon: float, half_size_deg: Optional[float] = None) -> tuple:
    """A roughly-square bbox centered on (lat, lon). Default half-size
    matches the Wayanad demo's scale (~6-8 km across)."""
    h = half_size_deg if half_size_deg is not None else config.FETCH_DEFAULT_BBOX_HALF_SIZE_DEG
    return (lon - h, lat - h, lon + h, lat + h)


def _check_bbox_size(bbox: tuple) -> None:
    west, south, east, north = bbox
    width, height = east - west, north - south
    if width > config.FETCH_MAX_BBOX_SIDE_DEG or height > config.FETCH_MAX_BBOX_SIDE_DEG:
        raise FetchError(
            f"That area is too large ({width:.2f}° x {height:.2f}°) -- max "
            f"{config.FETCH_MAX_BBOX_SIDE_DEG}° per side (~"
            f"{config.FETCH_MAX_BBOX_SIDE_DEG * 111:.0f} km). Draw a smaller box."
        )


def resolve_bbox(place: Optional[str], bbox: Optional[tuple]) -> tuple:
    """Exactly one of place/bbox must be given. Returns a (west, south,
    east, north) bbox, geocoding `place` if that's what was given. Raises
    FetchError if a drawn bbox is implausibly large -- see
    config.FETCH_MAX_BBOX_SIDE_DEG."""
    if bbox is not None:
        _check_bbox_size(bbox)
        return bbox
    if place:
        lat, lon = geocode_place(place)
        return bbox_from_point(lat, lon)
    raise FetchError("Provide either a place name or a bounding box.")


def fetch_scene_pair(
    bbox: tuple,
    before_date_range: str,
    after_date_range: str,
    max_cloud: float,
    out_dir: Path,
) -> dict:
    """Finds the lowest-cloud Sentinel-2 L2A scene in each date range,
    clips both to bbox, writes before.tif/after.tif into out_dir. Returns
    the chosen-scene metadata (date, cloud %) for both, shown in the UI."""
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog = open_catalog()

    try:
        before_item = find_scene(catalog, bbox, before_date_range, max_cloud=max_cloud)
    except RuntimeError as exc:
        raise FetchError(f"No 'before' scene found: {exc}") from exc
    try:
        after_item = find_scene(catalog, bbox, after_date_range, max_cloud=max_cloud)
    except RuntimeError as exc:
        raise FetchError(f"No 'after' scene found: {exc}") from exc

    before_path = out_dir / "before.tif"
    after_path = out_dir / "after.tif"
    before_meta = save_clip(before_item, bbox, before_path)
    after_meta = save_clip(after_item, bbox, after_path)

    return {
        "bbox": list(bbox),
        "before_scene": before_meta,
        "after_scene": after_meta,
    }
