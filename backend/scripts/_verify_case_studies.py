"""One-off verification: runs the real pipeline on every cached case
study and prints honest result numbers, to decide which ones are clear
enough to keep in the gallery. Not imported by anything."""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd  # noqa: E402

from app.case_studies import CASE_STUDIES, cached_tif_paths  # noqa: E402
from app.pipeline.run import run_pipeline  # noqa: E402

OUT_ROOT = Path(__file__).resolve().parent.parent / "data" / "_case_study_verify"


def main():
    for cs in CASE_STUDIES:
        slug = cs["slug"]
        before_tif, after_tif = cached_tif_paths(cs)
        print(f"\n=== {slug} ({cs['name']}) ===")
        out_dir = OUT_ROOT / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        result = run_pipeline(
            f"_verify_{slug}",
            str(before_tif),
            str(after_tif),
            out_dir,
            str(out_dir / "before.png"),
            str(out_dir / "after.png"),
            progress_cb=lambda step: None,
            engine_choice="auto",
            mode="disaster",
        )
        gdf = gpd.read_file(result["geojson_path"])
        kept = gdf[gdf["status"] == "kept"]
        rejected = gdf[gdf["status"] != "kept"]
        print(f"  engine={result['engine_key']} (fell_back={result['engine_fell_back']})")
        print(f"  kept={len(kept)} rejected={len(rejected)}")
        print(f"  change_type counts (kept): {dict(Counter(kept['change_type']))}")
        print(f"  reject_reason counts: {dict(Counter(rejected['reject_reason']))}")
        print(f"  quality: {result['quality_report']}")
        if len(kept):
            top = kept.sort_values("priority_score", ascending=False).iloc[0]
            print(
                f"  top priority: {top['change_type']} area={top['area_m2']:.0f} m2 "
                f"severity={top['severity']} score={top['priority_score']:.3f}"
            )
            print(f"  total_population_buffer_est: {result.get('total_population_buffer_est')}")


if __name__ == "__main__":
    sys.exit(main())
