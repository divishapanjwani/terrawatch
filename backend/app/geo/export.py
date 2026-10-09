import json

import geopandas as gpd
import pandas as pd

from app.geo.vectorize import PolygonResult


def _attrs(p: PolygonResult, analysis_id: str) -> dict:
    return {
        "id": p.id,
        "analysis_id": analysis_id,
        "status": p.status,
        "reject_reason": p.reject_reason,
        "change_type": p.change_type,
        "change_type_rule": p.change_type_rule,
        "needs_review": p.needs_review,
        "engine": p.engine,
        "area_m2": round(p.area_m2, 2),
        "change_magnitude": round(p.change_magnitude, 4),
        "confidence": round(p.confidence, 4),
        "severity": p.severity,
        "sev_score": round(p.sev_score, 4) if p.sev_score is not None else None,
        "centroid_lat": round(p.centroid_lat, 6),
        "centroid_lon": round(p.centroid_lon, 6),
        "nearest_hospital_m": p.nearest_hospital_m,
        "nearest_hospital_name": p.nearest_hospital_name,
        "nearest_school_m": p.nearest_school_m,
        "nearest_school_name": p.nearest_school_name,
        "nearest_main_road_m": p.nearest_main_road_m,
        "nearby_facilities_json": p.nearby_facilities_json,
        "population_est": p.population_est,
        "population_buffer_est": p.population_buffer_est,
        "in_hazard_zone": p.in_hazard_zone,
        "priority_score": p.priority_score,
        "priority_rank": p.priority_rank,
        "priority_reason": p.priority_reason,
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
