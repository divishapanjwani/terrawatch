import json
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from rasterio.enums import Resampling
from shapely.geometry import shape as shapely_shape

from app import config, settings
from app.db import OSM_CACHE_DIR
from app.engines import select, spectral
from app.engines.common import compute_magnitude_map
from app.geo import features
from app.geo.align import load_aligned_pair
from app.geo.export import save_geojson, save_gpkg
from app.geo.morphology import clean_mask
from app.geo.preview import generate_preview_pair
from app.geo.quality import check_scene_dominance_warning, run_quality_check
from app.geo.vectorize import compute_bounds_4326, native_pixel_area_m2, vectorize
from app.impact.facilities import fetch_facilities
from app.impact.population import compute_population, generate_population_overlay_png
from app.impact.routes import RouteGraphError, compute_route_impacts
from app.pipeline.change_type import apply_change_types
from app.pipeline.false_alarm import apply_false_alarm_filter
from app.pipeline.priority import apply_hazard_zone, compute_priority
from app.pipeline.severity import score_severity

EPS = 1e-6


def _build_extra_maps(aligned, before_cloud_mask, after_cloud_mask, valid_mask) -> dict:
    extra_maps = {}

    ndvi_b, ndvi_a = features.compute_ndvi(aligned.before), features.compute_ndvi(aligned.after)
    if ndvi_b is not None and ndvi_a is not None:
        extra_maps["ndvi_delta"] = (ndvi_a - ndvi_b, Resampling.bilinear)

    ndwi_b, ndwi_a = features.compute_ndwi(aligned.before), features.compute_ndwi(aligned.after)
    if ndwi_b is not None and ndwi_a is not None:
        extra_maps["ndwi_delta"] = (ndwi_a - ndwi_b, Resampling.bilinear)

    ndbi_b, ndbi_a = features.compute_ndbi(aligned.before), features.compute_ndbi(aligned.after)
    if ndbi_b is not None and ndbi_a is not None:
        extra_maps["ndbi_delta"] = (ndbi_a - ndbi_b, Resampling.bilinear)

    brightness_b = features.compute_brightness(aligned.before)
    brightness_a = features.compute_brightness(aligned.after)
    scale = features.dynamic_range(brightness_b, valid_mask)
    extra_maps["brightness_delta_frac"] = ((brightness_a - brightness_b) / scale, Resampling.bilinear)

    texture_b = features.compute_texture(aligned.before)
    texture_a = features.compute_texture(aligned.after)
    texture_change_frac = np.abs(texture_a - texture_b) / (texture_b + texture_a + EPS)
    extra_maps["texture_change_frac"] = (texture_change_frac, Resampling.bilinear)

    cloud_either = (before_cloud_mask | after_cloud_mask).astype(np.float32)
    extra_maps["cloud_overlap"] = (cloud_either, Resampling.nearest)

    edge_map = features.dilate_invalid(valid_mask, config.EDGE_BUFFER_PX).astype(np.float32)
    extra_maps["edge_touch"] = (edge_map, Resampling.nearest)

    return extra_maps


def run_pipeline(
    analysis_id: str,
    before_path: str,
    after_path: str,
    out_dir: Path,
    before_png: Path,
    after_png: Path,
    progress_cb: Callable[[str], None],
    engine_choice: str = "auto",
    mode: str = "disaster",
    hazard_zone_geojson: Optional[str] = None,
) -> dict:
    progress_cb("validating")
    aligned = load_aligned_pair(before_path, after_path)
    bounds = generate_preview_pair(aligned, str(before_png), str(after_png))

    progress_cb("quality_check")
    quality_report, before_cloud_mask, after_cloud_mask = run_quality_check(aligned)

    progress_cb("detecting")
    try:
        prob_map, resolution = select.predict(aligned, forced=engine_choice)
    except Exception:
        prob_map = spectral.predict(aligned)
        from app.engines.select import EngineResolution

        resolution = EngineResolution(
            "spectral",
            spectral.ENGINE_NAME,
            engine_choice,
            select.rule_based_choice(aligned),
            select.pixel_size_m(aligned),
            fell_back=True,
        )
    engine_used = resolution.name
    quality_report.engine = engine_used

    magnitude_map = compute_magnitude_map(aligned)
    valid_mask = aligned.before_mask & aligned.after_mask

    progress_cb("filtering")
    binary_mask = clean_mask(prob_map, config.DETECTION_THRESHOLD, config.MORPH_RADIUS_PX, valid_mask)
    extra_maps = _build_extra_maps(aligned, before_cloud_mask, after_cloud_mask, valid_mask)

    progress_cb("vectorizing")
    polygons = vectorize(
        binary_mask,
        prob_map,
        magnitude_map,
        aligned,
        config.SIMPLIFY_TOLERANCE_M,
        engine_used,
        extra_maps=extra_maps,
    )

    apply_false_alarm_filter(polygons, aligned.band_count, quality_report.cloud_method)
    apply_change_types(polygons, aligned.band_count)

    scene_area_m2 = int(valid_mask.sum()) * native_pixel_area_m2(aligned)
    dominance_warning = check_scene_dominance_warning([p.area_m2 for p in polygons], scene_area_m2)
    if dominance_warning:
        quality_report.warnings.append(dominance_warning)

    kept = [p for p in polygons if p.status == "kept"]
    rejected = [p for p in polygons if p.status == "rejected"]
    score_severity(kept)  # severity normalization only among real (kept) changes

    progress_cb("impact_analysis")
    bounds_4326 = compute_bounds_4326(aligned)
    population_png_path = out_dir / "population.png"
    population_png_written = generate_population_overlay_png(bounds_4326, population_png_path)

    population_available = False
    total_population_buffer_est = None
    near_facility_count = None
    if kept:
        facilities = fetch_facilities(bounds_4326, OSM_CACHE_DIR)
        population_available = compute_population(kept, bounds_4326)
        try:
            compute_route_impacts(kept, facilities, bounds_4326)
        except RouteGraphError as exc:
            quality_report.warnings.append(f"Route graph unavailable, route_impact not computed: {exc}")
        if hazard_zone_geojson:
            hazard_geom = shapely_shape(json.loads(hazard_zone_geojson))
            apply_hazard_zone(kept, hazard_geom)
        compute_priority(kept, facilities, weights=settings.get_priority_weights(), mode=mode)

        total_population_buffer_est = (
            round(sum(p.population_buffer_est or 0.0 for p in kept), 1) if population_available else None
        )
        near_facility_count = sum(
            1
            for p in kept
            if (p.nearest_hospital_m is not None and p.nearest_hospital_m <= config.PRIORITY_PROXIMITY_MAX_M)
            or (p.nearest_school_m is not None and p.nearest_school_m <= config.PRIORITY_PROXIMITY_MAX_M)
        )

    geojson_path = out_dir / "polygons.geojson"
    gpkg_path = out_dir / "polygons.gpkg"
    save_geojson(polygons, analysis_id, str(geojson_path))
    save_gpkg(polygons, analysis_id, str(gpkg_path))

    progress_cb("done")

    reject_counts = dict(Counter(p.reject_reason for p in rejected))
    reason_str = ", ".join(f"{k}: {v}" for k, v in sorted(reject_counts.items()))
    summary_line = f"{len(polygons)} candidates → {len(kept)} kept, {len(rejected)} rejected" + (
        f" ({reason_str})" if reason_str else ""
    )

    return {
        "bounds": bounds,
        "engine": engine_used,
        "engine_key": resolution.key,
        "engine_requested": resolution.requested,
        "engine_fell_back": resolution.fell_back,
        "pixel_size_m": resolution.pixel_size_m,
        "polygon_count": len(kept),
        "kept_count": len(kept),
        "rejected_count": len(rejected),
        "reject_reason_counts": reject_counts,
        "summary_line": summary_line,
        "population_available": population_available,
        "population_png_path": str(population_png_path) if population_png_written else None,
        "total_population_buffer_est": total_population_buffer_est,
        "near_facility_count": near_facility_count,
        "quality_report": quality_report.to_dict(),
        "geojson_path": str(geojson_path),
        "gpkg_path": str(gpkg_path),
    }
