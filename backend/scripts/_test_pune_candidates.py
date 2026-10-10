"""One-off research script: fetches 3 candidate Pune bboxes and runs the
real pipeline on each to see which actually yields honest new_construction
detections (per HANDOFF.md, the original Phase 5 Pune bbox did not).
Not imported by anything; results decide app/case_studies.py's final
pune_growth bbox."""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.geo.fetch import fetch_scene_pair  # noqa: E402
from app.pipeline.run import run_pipeline  # noqa: E402

CANDIDATES = {
    "pune_punawale_ravet": (73.72, 18.615, 73.77, 18.665),
    "pune_kharadi": (73.92, 18.53, 73.97, 18.58),
    "pune_hinjewadi_orig": (73.74, 18.55, 73.78, 18.58),
}
BEFORE = "2019-01-01/2019-04-30"
AFTER = "2024-01-01/2024-04-30"
OUT_ROOT = Path(__file__).resolve().parent.parent / "data" / "_pune_candidates"


def main():
    for name, bbox in CANDIDATES.items():
        print(f"\n=== {name}  {bbox} ===")
        tif_dir = OUT_ROOT / name
        before_tif, after_tif = tif_dir / "before.tif", tif_dir / "after.tif"
        if not (before_tif.exists() and after_tif.exists()):
            fetch_scene_pair(bbox, BEFORE, AFTER, 20, tif_dir)

        out_dir = OUT_ROOT / name / "run"
        out_dir.mkdir(parents=True, exist_ok=True)
        result = run_pipeline(
            f"_test_{name}",
            str(before_tif),
            str(after_tif),
            out_dir,
            str(out_dir / "before.png"),
            str(out_dir / "after.png"),
            progress_cb=lambda step: None,
            engine_choice="auto",
            mode="disaster",
        )
        import geopandas as gpd

        gdf = gpd.read_file(result["geojson_path"])
        kept = gdf[gdf["status"] == "kept"]
        print(f"  engine={result['engine_key']} kept={len(kept)} rejected={result['rejected_count']}")
        print(f"  change_type counts: {Counter(kept['change_type'])}")
        if len(kept):
            print(f"  area_m2 range: {kept['area_m2'].min():.0f} - {kept['area_m2'].max():.0f}")


if __name__ == "__main__":
    sys.exit(main())
