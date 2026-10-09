import json

import geopandas as gpd
import pandas as pd

from app.geo.vectorize import PolygonResult


def _attrs(p: PolygonResult, analysis_id: str) -> dict:
    return {
        "id": p.id,
        "analysis_id": analysis_id,
        "status": p.status,
        "engine": p.engine,
        "area_m2": round(p.area_m2, 2),
        "change_magnitude": round(p.change_magnitude, 4),
        "confidence": round(p.confidence, 4),
        "severity": p.severity,
        "sev_score": round(p.sev_score, 4) if p.sev_score is not None else None,
        "centroid_lat": round(p.centroid_lat, 6),
        "centroid_lon": round(p.centroid_lon, 6),
    }


def to_geodataframe(polygons: list[PolygonResult], analysis_id: str) -> gpd.GeoDataFrame:
    """Native (projected, meters) CRS GeoDataFrame — used for area-accurate
    GeoPackage export."""
    if not polygons:
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=None)
    crs = polygons[0].area_crs
    rows = [_attrs(p, analysis_id) for p in polygons]
    geoms = [p.geometry for p in polygons]
    return gpd.GeoDataFrame(pd.DataFrame(rows), geometry=geoms, crs=crs)


def save_geojson(polygons: list[PolygonResult], analysis_id: str, out_path: str) -> None:
    if not polygons:
        with open(out_path, "w") as f:
            json.dump({"type": "FeatureCollection", "features": []}, f)
        return
    gdf = to_geodataframe(polygons, analysis_id).to_crs("EPSG:4326")
    gdf.to_file(out_path, driver="GeoJSON")


def save_gpkg(polygons: list[PolygonResult], analysis_id: str, out_path: str) -> None:
    if not polygons:
        gdf = gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs="EPSG:4326")
    else:
        gdf = to_geodataframe(polygons, analysis_id)
    gdf.to_file(out_path, driver="GPKG", layer="changes")
