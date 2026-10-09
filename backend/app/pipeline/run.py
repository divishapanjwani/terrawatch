from pathlib import Path
from typing import Callable

from app import config
from app.engines import spectral, siamese
from app.engines.common import compute_magnitude_map
from app.geo.align import load_aligned_pair
from app.geo.export import save_geojson, save_gpkg
from app.geo.morphology import clean_mask
from app.geo.preview import generate_preview_pair
from app.geo.vectorize import native_pixel_area_m2, vectorize
from app.pipeline.severity import score_severity


def run_pipeline(
    analysis_id: str,
    before_path: str,
    after_path: str,
    out_dir: Path,
    before_png: Path,
    after_png: Path,
    progress_cb: Callable[[str], None],
) -> dict:
    progress_cb("validating")
    aligned = load_aligned_pair(before_path, after_path)
    bounds = generate_preview_pair(aligned, str(before_png), str(after_png))

    progress_cb("detecting")
    engine_used = None
    prob_map = None
    if siamese.is_available():
        try:
            prob_map = siamese.predict(aligned)
            engine_used = siamese.ENGINE_NAME
        except Exception:
            prob_map = None
    if prob_map is None:
        prob_map = spectral.predict(aligned)
        engine_used = spectral.ENGINE_NAME

    magnitude_map = compute_magnitude_map(aligned)

    progress_cb("filtering")
    pixel_area_m2 = native_pixel_area_m2(aligned)
    valid_mask = aligned.before_mask & aligned.after_mask
    binary_mask = clean_mask(
        prob_map,
        config.DETECTION_THRESHOLD,
        pixel_area_m2,
        config.MIN_AREA_M2,
        config.MORPH_RADIUS_PX,
        valid_mask,
    )

    progress_cb("vectorizing")
    polygons = vectorize(
        binary_mask, prob_map, magnitude_map, aligned, config.SIMPLIFY_TOLERANCE_M, engine_used
    )
    score_severity(polygons)

    geojson_path = out_dir / "polygons.geojson"
    gpkg_path = out_dir / "polygons.gpkg"
    save_geojson(polygons, analysis_id, str(geojson_path))
    save_gpkg(polygons, analysis_id, str(gpkg_path))

    progress_cb("done")

    return {
        "bounds": bounds,
        "engine": engine_used,
        "polygon_count": len(polygons),
        "geojson_path": str(geojson_path),
        "gpkg_path": str(gpkg_path),
    }
