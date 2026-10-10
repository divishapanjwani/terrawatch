"""Download the WorldPop India 2020 unconstrained population-count raster
(1 km, UN-adjusted) used for Phase 5's population_est / population_buffer_est.

One country-wide file covers both demo scenes (Wayanad, Kerala and Pune,
Maharashtra) -- no per-region download needed. ~18 MB.

Source: WorldPop "Global 2000-2020 1km UNadj" series.
https://www.worldpop.org/methods/populations/
"""

import sys
import urllib.request
from pathlib import Path

URL = (
    "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/"
    "2020/IND/ind_ppp_2020_1km_Aggregated_UNadj.tif"
)
OUT_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "population" / "ind_ppp_2020_1km_Aggregated_UNadj.tif"
)


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.exists():
        print(f"Already downloaded: {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)")
        return
    print(f"Downloading {URL} -> {OUT_PATH}")
    urllib.request.urlretrieve(URL, OUT_PATH)
    print(f"Done: {OUT_PATH.stat().st_size:,} bytes")


if __name__ == "__main__":
    sys.exit(main())
