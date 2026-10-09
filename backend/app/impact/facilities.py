"""Hospitals/clinics/schools from OpenStreetMap, via the Overpass API,
cached to disk so re-running the same scene doesn't re-fetch.

Clinics are grouped into "hospitals" for nearest-facility purposes --
the data model only tracks nearest_hospital_m / nearest_school_m
(see PROJECT_BRIEF.md section 6).
"""
import json
import time
from pathlib import Path

import requests

from app import config


class OSMFetchError(RuntimeError):
    """Raised when the Overpass API request fails or times out."""


def _cache_path(buffered_bounds: tuple, cache_dir: Path) -> Path:
    key = "_".join(f"{v:.3f}" for v in buffered_bounds)
    return cache_dir / f"facilities_{key}.json"


def _build_query(bounds: tuple) -> str:
    west, south, east, north = bounds
    bbox = f"{south},{west},{north},{east}"
    return f"""
[out:json][timeout:{config.OSM_TIMEOUT_S}];
(
  node["amenity"="hospital"]({bbox});
  way["amenity"="hospital"]({bbox});
  node["amenity"="clinic"]({bbox});
  way["amenity"="clinic"]({bbox});
  node["amenity"="school"]({bbox});
  way["amenity"="school"]({bbox});
);
out center;
"""


def fetch_facilities(bounds_4326: tuple, cache_dir: Path) -> dict:
    """bounds_4326: (west, south, east, north) of the analysis scene.
    Returns {"hospitals": [{"lat","lon","name"}, ...], "schools": [...]}.
    Raises OSMFetchError on network/HTTP failure -- callers should
    surface this as a real analysis error, not fake the numbers.
    """
    west, south, east, north = bounds_4326
    buf = config.OSM_FACILITY_BUFFER_DEG
    buffered = (west - buf, south - buf, east + buf, north + buf)

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(buffered, cache_dir)
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    # overpass-api.de is a shared, rate-limited public instance that
    # occasionally 504s under load (noted in its own usage docs) -- one
    # short retry before giving up, not an open-ended fight.
    last_exc: Exception | None = None
    data = None
    for attempt in range(2):
        try:
            resp = requests.post(
                config.OVERPASS_URL,
                data={"data": _build_query(buffered)},
                headers={"User-Agent": "TerraWatch/1.0 (disaster-response demo)"},
                timeout=config.OSM_TIMEOUT_S + 5,
            )
            resp.raise_for_status()
            data = resp.json()
            break
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt == 0:
                time.sleep(5)
    if data is None:
        raise OSMFetchError(f"OSM/Overpass fetch failed: {last_exc}") from last_exc

    hospitals, schools = [], []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        amenity = tags.get("amenity")
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None and "center" in el:
            lat, lon = el["center"].get("lat"), el["center"].get("lon")
        if lat is None or lon is None:
            continue
        name = tags.get("name", "Unnamed")
        if amenity in ("hospital", "clinic"):
            hospitals.append({"lat": lat, "lon": lon, "name": name})
        elif amenity == "school":
            schools.append({"lat": lat, "lon": lon, "name": name})

    result = {"hospitals": hospitals, "schools": schools}
    cache_file.write_text(json.dumps(result))
    return result
