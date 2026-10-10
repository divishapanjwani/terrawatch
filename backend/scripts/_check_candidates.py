"""One-off research script (not part of the app): checks real Sentinel-2
L2A scene availability/cloud-cover for candidate case-study bboxes before
committing to final coordinates/dates. Not imported by anything."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sentinel2_fetch import open_catalog  # noqa: E402

CANDIDATES = {
    "sikkim_glof_chungthang": {
        "bbox": (88.60, 27.56, 88.70, 27.64),
        "before": "2023-01-01/2023-09-30",
        "after": "2023-10-04/2024-04-30",
    },
    "himachal_flood_kullu": {
        "bbox": (77.05, 31.90, 77.17, 32.00),
        "before": "2023-03-01/2023-06-30",
        "after": "2023-07-10/2023-12-31",
    },
    "pune_punawale_ravet": {
        "bbox": (73.72, 18.615, 73.77, 18.665),
        "before": "2019-01-01/2019-04-30",
        "after": "2024-01-01/2024-04-30",
    },
    "pune_kharadi": {
        "bbox": (73.92, 18.53, 73.97, 18.58),
        "before": "2019-01-01/2019-04-30",
        "after": "2024-01-01/2024-04-30",
    },
    "pune_hinjewadi_orig": {
        "bbox": (73.74, 18.55, 73.78, 18.58),
        "before": "2019-01-01/2019-04-30",
        "after": "2024-01-01/2024-04-30",
    },
}


def main():
    catalog = open_catalog()
    for name, c in CANDIDATES.items():
        print(f"\n=== {name}  bbox={c['bbox']} ===")
        for label, dr in [("before", c["before"]), ("after", c["after"])]:
            search = catalog.search(
                collections=["sentinel-2-l2a"],
                bbox=c["bbox"],
                datetime=dr,
                sortby=[{"field": "eo:cloud_cover", "direction": "asc"}],
                max_items=5,
            )
            items = list(search.items())
            if not items:
                print(f"  {label} [{dr}]: NO SCENES FOUND")
                continue
            print(f"  {label} [{dr}]: {len(items)} candidates shown (lowest cloud first)")
            for it in items[:5]:
                print(
                    f"    {it.datetime.date()}  cloud={it.properties.get('eo:cloud_cover'):.1f}%  id={it.id}"
                )


if __name__ == "__main__":
    sys.exit(main())
