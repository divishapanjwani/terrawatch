"""Fetch a small real Sentinel-2 L2A before/after pair (Pune, Maharashtra
urban growth area) from Microsoft Planetary Computer. See
scripts/sentinel2_fetch.py for the shared fetch/clip logic.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sentinel2_fetch import find_scene, open_catalog, save_clip  # noqa: E402

# Small bbox near Pune, Maharashtra (urban growth area), ~3km x 3km.
BBOX = (73.74, 18.55, 73.78, 18.58)
BEFORE_DATE = "2019-01-01/2019-03-01"
AFTER_DATE = "2024-01-01/2024-03-01"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "real_test_pair"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = open_catalog()

    before_item = find_scene(catalog, BBOX, BEFORE_DATE)
    after_item = find_scene(catalog, BBOX, AFTER_DATE)

    save_clip(before_item, BBOX, OUT_DIR / "before.tif")
    save_clip(after_item, BBOX, OUT_DIR / "after.tif")


if __name__ == "__main__":
    sys.exit(main())
