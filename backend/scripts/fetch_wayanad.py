"""Fetch a Sentinel-2 L2A before/after pair covering the Mundakkai /
Chooralmala landslide area, Wayanad district, Kerala (event: 30 July 2024).

Coordinates (verified against village-level sources, not the district
centroid — the Wikipedia "2024 Wayanad landslides" infobox itself is off
by ~33km and should not be used):
  Mundakkai village:    11.4859N, 76.1559E
  Chooralmala village:  11.5022N, 76.1548E
  Landslide source/crown (Nature Sci. Reports 2025, "Mundakkai-Chooralmala
    landslide: assessment of initiation, progression, and impact",
    https://www.nature.com/articles/s41598-025-07828-3): ~11.465N, 76.135E

BBOX below covers the crown-to-village debris path.

Kerala's SW monsoon runs June-September, so "before" imagery is searched
in the driest pre-monsoon window (Jan-Apr 2024); "after" is searched
starting the day of the event through the following months since monsoon
cloud cover may delay the first clear post-event scene.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sentinel2_fetch import find_scene, open_catalog, save_clip  # noqa: E402

BBOX = (76.12, 11.44, 76.18, 11.51)
BEFORE_DATE = "2024-01-01/2024-04-30"
AFTER_DATE = "2024-07-30/2024-12-31"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "wayanad"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = open_catalog()

    print("Searching for lowest-cloud pre-monsoon scene (before)...")
    before_item = find_scene(catalog, BBOX, BEFORE_DATE, max_cloud=20)
    print("Searching for lowest-cloud post-event scene (after)...")
    after_item = find_scene(catalog, BBOX, AFTER_DATE, max_cloud=20)

    save_clip(before_item, BBOX, OUT_DIR / "before.tif")
    save_clip(after_item, BBOX, OUT_DIR / "after.tif")


if __name__ == "__main__":
    sys.exit(main())
