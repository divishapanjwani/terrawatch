"""
Score TerraWatch output against the planted answer key.

Usage:
    python check_results.py path/to/exported_changes.geojson
    python check_results.py path/to/exported_changes.gpkg      (needs geopandas)

Only polygons with status == "kept" are scored (if the field exists);
everything else in the file is treated as a reported real change.
Coordinates may be EPSG:4326 (default for GeoJSON) or any CRS named in the file.
"""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from shapely.geometry import shape

HERE = Path(__file__).parent
MATCH_OVERLAP = 0.30     # a planted change counts as "found" if >=30% of it is covered


def load_features(path):
    path = Path(path)
    if path.suffix.lower() == ".gpkg":
        import geopandas as gpd
        gdf = gpd.read_file(path)
        crs = gdf.crs.to_string() if gdf.crs else "EPSG:4326"
        feats = json.loads(gdf.to_json())["features"]
        return feats, crs
    data = json.loads(path.read_text())
    crs = "EPSG:4326"
    if "crs" in data:
        crs = data["crs"].get("properties", {}).get("name", crs)
        if "CRS84" in crs:
            crs = "EPSG:4326"
    return data["features"], crs


def main(result_path):
    with rasterio.open(HERE / "ground_truth_real_changes.tif") as src:
        gt = src.read(1)
        grid_crs, transform, shape_hw = src.crs, src.transform, (src.height, src.width)
    with rasterio.open(HERE / "fake_changes_mask.tif") as src:
        fake = src.read(1) == 1
    key = json.loads((HERE / "answer_key.geojson").read_text())["features"]

    feats, crs = load_features(result_path)
    kept = [f for f in feats if f.get("properties", {}).get("status", "kept") == "kept"]
    rejected = len(feats) - len(kept)

    geoms = [transform_geom(crs, grid_crs, f["geometry"]) for f in kept if f.get("geometry")]
    pred = rasterize([(g, 1) for g in geoms], out_shape=shape_hw, transform=transform,
                     fill=0, dtype="uint8") == 1 if geoms else np.zeros(shape_hw, bool)

    valid = gt != 255
    real = gt == 1
    tp = (pred & real & valid).sum()
    fp = (pred & ~real & valid).sum()
    fn = (~pred & real & valid).sum()
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0

    print(f"\nScored {len(kept)} kept polygons ({rejected} rejected/other ignored) from {result_path}\n")
    print("PIXEL SCORES (real changes)")
    print(f"  precision {prec:.2f}   recall {rec:.2f}   F1 {f1:.2f}")

    print("\nPLANTED REAL CHANGES")
    pred_polys = [shape(g) for g in geoms]
    for k in key:
        p = k["properties"]
        kg = transform_geom("EPSG:4326", grid_crs, k["geometry"])
        km = rasterize([(kg, 1)], out_shape=shape_hw, transform=transform, fill=0, dtype="uint8") == 1
        cover = (pred & km).sum() / km.sum()
        if p["kind"] == "real":
            found = cover >= MATCH_OVERLAP
            line = f"  {'FOUND ' if found else 'MISSED'} {p['id']} {p['label']:<22} covered {cover:5.0%}"
            if found:
                kshape = shape(kg)
                best = max(pred_polys, key=lambda q: q.intersection(kshape).area)
                area_err = (best.area - p["area_m2"]) / p["area_m2"]
                cdist = best.centroid.distance(kshape.centroid)
                line += f" | your area {best.area:7.0f} m2 vs {p['area_m2']:7.0f} ({area_err:+.0%}) | centroid off by {cdist:.1f} m"
            if p["id"] == "R5" and not found:
                line += "  (OK if your minimum-area filter is above 16 m2)"
            print(line)
    print("\nPLANTED FAKE CHANGES (lower is better)")
    for k in key:
        p = k["properties"]
        if p["kind"] != "fake":
            continue
        kg = transform_geom("EPSG:4326", grid_crs, k["geometry"])
        km = rasterize([(kg, 1)], out_shape=shape_hw, transform=transform, fill=0, dtype="uint8") == 1
        cover = (pred & km).sum() / km.sum()
        verdict = "good" if cover < 0.10 else ("partly flagged" if cover < MATCH_OVERLAP else "FALSE ALARM")
        print(f"  {p['id']} {p['label']:<20} flagged {cover:5.0%}  -> {verdict}")

    bg_fp = (pred & ~real & ~fake & valid).sum()
    print(f"\nOther false-positive pixels (background noise / brightness shift): {bg_fp} m2")
    print("\nTip: in Phase 2 the fake changes may still show up; after Phase 4 (false-alarm filter) "
          "F1-F3 should drop to 'good' and appear as rejected polygons with reasons instead.\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
