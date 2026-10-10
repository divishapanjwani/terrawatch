import json
import shutil
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from sqlmodel import select

from app import config
from app.config import PROGRESS_STEPS
from app.db import ANALYSES_DIR, OSM_CACHE_DIR, UPLOADS_DIR, get_session
from app.engines.select import VALID_FORCED_CHOICES
from app.geo.fetch import FetchError, fetch_scene_pair, resolve_bbox
from app.geo.preview import read_metadata
from app.impact.facilities import OSMFetchError, fetch_facilities
from app.models import Analysis
from app.pipeline.priority import recompute_hazard_zone_gdf
from app.pipeline.run import run_pipeline

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


def _save_upload(upload: UploadFile, dest_path) -> None:
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(upload.file, f)


def _set_progress(analysis_id: str, step: str) -> None:
    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            return
        analysis.progress_step = step
        session.add(analysis)
        session.commit()


def _process_analysis(
    analysis_id: str,
    before_path: str,
    after_path: str,
    output_dir: Path,
    engine_choice: str,
    mode: str = "disaster",
    hazard_zone_geojson: Optional[str] = None,
) -> None:
    before_png = output_dir / "before.png"
    after_png = output_dir / "after.png"
    try:
        before_meta = read_metadata(before_path)
        after_meta = read_metadata(after_path)
        if before_meta["crs"] is None or after_meta["crs"] is None:
            raise ValueError("One or both files have no CRS (not georeferenced).")

        result = run_pipeline(
            analysis_id,
            before_path,
            after_path,
            output_dir,
            before_png,
            after_png,
            progress_cb=lambda step: _set_progress(analysis_id, step),
            engine_choice=engine_choice,
            mode=mode,
            hazard_zone_geojson=hazard_zone_geojson,
        )

        def _fmt(b: dict) -> str:
            return f"{b['west']},{b['south']},{b['east']},{b['north']}"

        with get_session() as session:
            analysis = session.get(Analysis, analysis_id)
            analysis.status = "ready"
            analysis.progress_step = "done"
            analysis.before_png = str(before_png)
            analysis.after_png = str(after_png)
            analysis.bounds = _fmt(result["bounds"])
            analysis.engine = result["engine"]
            analysis.engine_key = result["engine_key"]
            analysis.engine_fell_back = result["engine_fell_back"]
            analysis.pixel_size_m = result["pixel_size_m"]
            analysis.polygon_count = result["polygon_count"]
            analysis.kept_count = result["kept_count"]
            analysis.rejected_count = result["rejected_count"]
            analysis.reject_reason_counts = json.dumps(result["reject_reason_counts"])
            analysis.summary_line = result["summary_line"]
            analysis.population_available = result["population_available"]
            analysis.population_png = result["population_png_path"]
            analysis.total_population_buffer_est = result["total_population_buffer_est"]
            analysis.near_facility_count = result["near_facility_count"]
            analysis.quality_report = json.dumps(result["quality_report"])
            analysis.geojson_path = result["geojson_path"]
            analysis.gpkg_path = result["gpkg_path"]
            session.add(analysis)
            session.commit()
    except Exception as exc:  # noqa: BLE001
        with get_session() as session:
            analysis = session.get(Analysis, analysis_id)
            analysis.status = "failed"
            analysis.error_message = str(exc)
            session.add(analysis)
            session.commit()


@router.post("")
async def create_analysis(
    background_tasks: BackgroundTasks,
    before: UploadFile = File(...),
    after: UploadFile = File(...),
    mode: str = Form("disaster"),
    engine: str = Form("auto"),
    hazard_zone: Optional[str] = Form(None),
):
    if engine not in VALID_FORCED_CHOICES:
        raise HTTPException(status_code=400, detail=f"engine must be one of {VALID_FORCED_CHOICES}")
    if hazard_zone:
        try:
            json.loads(hazard_zone)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="hazard_zone must be valid GeoJSON")

    analysis_id = uuid.uuid4().hex[:12]
    upload_dir = UPLOADS_DIR / analysis_id
    output_dir = ANALYSES_DIR / analysis_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    before_path = upload_dir / "before.tif"
    after_path = upload_dir / "after.tif"
    _save_upload(before, before_path)
    _save_upload(after, after_path)

    analysis = Analysis(
        id=analysis_id,
        mode=mode,
        status="pending",
        progress_step="validating",
        before_path=str(before_path),
        after_path=str(after_path),
        engine_choice=engine,
        hazard_zone_geojson=hazard_zone,
    )

    with get_session() as session:
        session.add(analysis)
        session.commit()

    background_tasks.add_task(
        _process_analysis,
        analysis_id,
        str(before_path),
        str(after_path),
        output_dir,
        engine,
        mode,
        hazard_zone,
    )

    return {"analysis_id": analysis_id}


def _process_fetch_and_analysis(
    analysis_id: str,
    place: Optional[str],
    bbox: Optional[tuple],
    before_date_range: str,
    after_date_range: str,
    max_cloud: float,
    upload_dir: Path,
    output_dir: Path,
    engine_choice: str,
    mode: str,
    case_study_slug: Optional[str] = None,
) -> None:
    _set_progress(analysis_id, "fetching")
    try:
        resolved_bbox = resolve_bbox(place, bbox)
        fetch_result = fetch_scene_pair(resolved_bbox, before_date_range, after_date_range, max_cloud, upload_dir)
        fetch_result["place"] = place
    except FetchError as exc:
        with get_session() as session:
            analysis = session.get(Analysis, analysis_id)
            analysis.status = "failed"
            analysis.error_message = str(exc)
            session.add(analysis)
            session.commit()
        return

    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        analysis.fetch_meta = json.dumps(fetch_result)
        if case_study_slug:
            analysis.case_study_slug = case_study_slug
        session.add(analysis)
        session.commit()

    _process_analysis(
        analysis_id,
        str(upload_dir / "before.tif"),
        str(upload_dir / "after.tif"),
        output_dir,
        engine_choice,
        mode,
    )


def _parse_bbox_str(bbox_str: str) -> tuple:
    parts = [float(x) for x in bbox_str.split(",")]
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="bbox must be 'west,south,east,north'")
    return tuple(parts)


@router.post("/fetch")
async def fetch_analysis(
    background_tasks: BackgroundTasks,
    before_date_range: str = Form(...),
    after_date_range: str = Form(...),
    place: Optional[str] = Form(None),
    bbox: Optional[str] = Form(None),
    max_cloud: float = Form(config.FETCH_DEFAULT_MAX_CLOUD),
    mode: str = Form("disaster"),
    engine: str = Form("auto"),
):
    """Auto-fetch: place name (geocoded via Nominatim) or a drawn bbox +
    before/after date ranges + max cloud % -> lowest-cloud Sentinel-2
    L2A scenes, clipped and run through the normal pipeline."""
    if engine not in VALID_FORCED_CHOICES:
        raise HTTPException(status_code=400, detail=f"engine must be one of {VALID_FORCED_CHOICES}")
    if not place and not bbox:
        raise HTTPException(status_code=400, detail="Provide either 'place' or 'bbox'")

    parsed_bbox = _parse_bbox_str(bbox) if bbox else None

    analysis_id = uuid.uuid4().hex[:12]
    upload_dir = UPLOADS_DIR / analysis_id
    output_dir = ANALYSES_DIR / analysis_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    analysis = Analysis(
        id=analysis_id,
        mode=mode,
        status="pending",
        progress_step="fetching",
        engine_choice=engine,
        is_auto_fetch=True,
    )
    with get_session() as session:
        session.add(analysis)
        session.commit()

    background_tasks.add_task(
        _process_fetch_and_analysis,
        analysis_id,
        place,
        parsed_bbox,
        before_date_range,
        after_date_range,
        max_cloud,
        upload_dir,
        output_dir,
        engine,
        mode,
    )

    return {"analysis_id": analysis_id}


@router.get("/{analysis_id}")
async def get_analysis(analysis_id: str):
    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not found")

        def _parse(s: Optional[str]):
            if not s:
                return None
            w, so, e, n = (float(x) for x in s.split(","))
            return {"west": w, "south": so, "east": e, "north": n}

        return {
            "id": analysis.id,
            "mode": analysis.mode,
            "status": analysis.status,
            "progress_step": analysis.progress_step,
            "progress_steps": config.FETCH_PROGRESS_STEPS if analysis.is_auto_fetch else PROGRESS_STEPS,
            "is_auto_fetch": analysis.is_auto_fetch,
            "fetch_meta": json.loads(analysis.fetch_meta) if analysis.fetch_meta else None,
            "case_study_slug": analysis.case_study_slug,
            "error_message": analysis.error_message,
            "bounds": _parse(analysis.bounds),
            "engine_choice": analysis.engine_choice,
            "engine": analysis.engine,
            "engine_key": analysis.engine_key,
            "engine_fell_back": analysis.engine_fell_back,
            "pixel_size_m": analysis.pixel_size_m,
            "polygon_count": analysis.polygon_count,
            "kept_count": analysis.kept_count,
            "rejected_count": analysis.rejected_count,
            "reject_reason_counts": (
                json.loads(analysis.reject_reason_counts) if analysis.reject_reason_counts else {}
            ),
            "summary_line": analysis.summary_line,
            "population_available": analysis.population_available,
            "total_population_buffer_est": analysis.total_population_buffer_est,
            "near_facility_count": analysis.near_facility_count,
            "hazard_zone_geojson": analysis.hazard_zone_geojson,
            "quality_report": json.loads(analysis.quality_report) if analysis.quality_report else None,
            "created_at": analysis.created_at.isoformat(),
        }


@router.get("/{analysis_id}/facilities")
async def get_facilities(analysis_id: str):
    """Hospitals/schools/shelters + main road lines for the map's
    Facilities/Roads layer toggles -- reads the same disk cache
    app/pipeline/run.py already populated during analysis, so this is
    cheap (no new OSM fetch in the common case)."""
    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        bounds_str = analysis.bounds
    if not bounds_str:
        return {"hospitals": [], "schools": [], "shelters": [], "roads": []}
    west, south, east, north = (float(x) for x in bounds_str.split(","))
    try:
        return fetch_facilities((west, south, east, north), OSM_CACHE_DIR)
    except OSMFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/{analysis_id}/imagery/{which}")
async def get_imagery(analysis_id: str, which: str):
    if which not in ("before", "after", "population"):
        raise HTTPException(status_code=400, detail="which must be 'before', 'after' or 'population'")
    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        png_path = {
            "before": analysis.before_png,
            "after": analysis.after_png,
            "population": analysis.population_png,
        }[which]
        if not png_path:
            status = 409 if which != "population" else 404
            detail = (
                "Imagery not ready yet"
                if which != "population"
                else "No population data available for this scene"
            )
            raise HTTPException(status_code=status, detail=detail)
        return FileResponse(png_path, media_type="image/png")


@router.get("/{analysis_id}/polygons")
async def get_polygons(analysis_id: str):
    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        geojson_path = analysis.geojson_path
    if not geojson_path or not Path(geojson_path).exists():
        return JSONResponse({"type": "FeatureCollection", "features": []})
    return JSONResponse(json.loads(Path(geojson_path).read_text()))


@router.get("/{analysis_id}/polygons/{polygon_id}/route")
async def get_polygon_route(analysis_id: str, polygon_id: str):
    """On-demand (not precomputed for every polygon): the original and
    detour route geometries to the nearest hospital, for the map to draw
    when this polygon is selected. See app/impact/routes.py."""
    from shapely.geometry import shape as shapely_shape

    from app.impact.routes import get_route_for_polygon

    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        geojson_path = analysis.geojson_path
        bounds_str = analysis.bounds
    if not geojson_path or not Path(geojson_path).exists() or not bounds_str:
        raise HTTPException(status_code=409, detail="Analysis not ready yet")

    fc = json.loads(Path(geojson_path).read_text())
    feature = next((f for f in fc["features"] if str(f["properties"].get("id")) == polygon_id), None)
    if feature is None:
        raise HTTPException(status_code=404, detail="Polygon not found")

    west, south, east, north = (float(x) for x in bounds_str.split(","))
    polygon_geom_4326 = shapely_shape(feature["geometry"])
    centroid_lat = feature["properties"]["centroid_lat"]
    centroid_lon = feature["properties"]["centroid_lon"]

    try:
        facilities = fetch_facilities((west, south, east, north), OSM_CACHE_DIR)
    except OSMFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    result = get_route_for_polygon(
        polygon_geom_4326, centroid_lat, centroid_lon, facilities, (west, south, east, north)
    )
    return result


@router.post("/{analysis_id}/hazard_zone")
async def set_hazard_zone(analysis_id: str, body: dict):
    """Apply a user-drawn/uploaded hazard zone AFTER the analysis is ready
    (Prevention mode) -- the zone is drawn relative to already-detected
    new_construction polygons, so this recomputes in_hazard_zone and
    re-ranks directly from the saved result files, with no re-detection
    and no re-fetch of facilities/population."""
    import geopandas as gpd
    from shapely.geometry import shape as shapely_shape

    geojson_body = body.get("geojson")
    if not geojson_body:
        raise HTTPException(status_code=400, detail="Missing 'geojson' field")
    try:
        hazard_geom = shapely_shape(geojson_body)
    except Exception:
        raise HTTPException(status_code=400, detail="'geojson' must be a valid GeoJSON geometry")

    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        if analysis.status != "ready" or not analysis.gpkg_path:
            raise HTTPException(status_code=409, detail="Analysis not ready yet")
        gpkg_path = analysis.gpkg_path
        geojson_path = analysis.geojson_path
        mode = analysis.mode

    gdf = gpd.read_file(gpkg_path, layer="changes")
    if gdf.empty:
        raise HTTPException(status_code=409, detail="No polygons to apply a hazard zone to")

    kept = gdf[gdf["status"] == "kept"]
    rejected = gdf[gdf["status"] != "kept"]
    updated_kept = recompute_hazard_zone_gdf(kept, hazard_geom, mode)
    merged = gpd.GeoDataFrame(
        pd.concat([updated_kept, rejected], ignore_index=True), geometry="geometry", crs=gdf.crs
    )

    merged.to_file(gpkg_path, driver="GPKG", layer="changes")
    merged.to_crs("EPSG:4326").to_file(geojson_path, driver="GeoJSON")

    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        analysis.hazard_zone_geojson = json.dumps(geojson_body)
        session.add(analysis)
        session.commit()

    in_zone_count = int(updated_kept["in_hazard_zone"].sum())
    return {"status": "ok", "in_hazard_zone_count": in_zone_count}


@router.get("/{analysis_id}/export")
async def export_analysis(analysis_id: str, format: str = "geojson"):
    if format not in ("geojson", "gpkg"):
        raise HTTPException(status_code=400, detail="format must be 'geojson' or 'gpkg'")
    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        path = analysis.geojson_path if format == "geojson" else analysis.gpkg_path
    if not path or not Path(path).exists():
        raise HTTPException(status_code=409, detail="Export not ready yet")
    media_type = "application/geo+json" if format == "geojson" else "application/geopackage+sqlite3"
    filename = f"{analysis_id}_changes.{format}"
    return FileResponse(path, media_type=media_type, filename=filename)


@router.get("/{analysis_id}/report")
async def get_field_report(analysis_id: str, format: str = "html", lang: str = "en"):
    """One-click field report: KPIs, a severity-colored map snapshot, the
    top 10 priority areas, and honesty notes -- built only from already-
    computed results (see app/reports/field_report.py), in English/Hindi/
    Marathi. format=html is the mobile-friendly shareable page;
    format=pdf renders the same content to PDF (WeasyPrint)."""
    from app.reports.field_report import build_context, render_html, render_pdf
    from app.reports.i18n import LANGUAGES
    from app.reports.map_snapshot import generate_map_snapshot

    if format not in ("html", "pdf"):
        raise HTTPException(status_code=400, detail="format must be 'html' or 'pdf'")
    if lang not in LANGUAGES:
        raise HTTPException(status_code=400, detail=f"lang must be one of {list(LANGUAGES)}")

    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        if analysis.status != "ready":
            raise HTTPException(status_code=409, detail="Analysis not ready yet")
        geojson_path = analysis.geojson_path
        after_png = analysis.after_png
        bounds_str = analysis.bounds
        output_dir = Path(geojson_path).parent

    if not geojson_path or not Path(geojson_path).exists() or not after_png or not bounds_str:
        raise HTTPException(status_code=409, detail="Report not ready yet")

    fc = json.loads(Path(geojson_path).read_text())
    kept_features = [f for f in fc["features"] if f["properties"].get("status") == "kept"]
    west, south, east, north = (float(x) for x in bounds_str.split(","))
    bounds = {"west": west, "south": south, "east": east, "north": north}

    snapshot_path = output_dir / "report_snapshot.png"
    if not snapshot_path.exists():
        generate_map_snapshot(after_png, bounds, kept_features, str(snapshot_path))

    ctx = build_context(analysis, kept_features, lang, str(snapshot_path))
    html = render_html(ctx)

    if format == "html":
        return HTMLResponse(html)

    pdf_bytes = render_pdf(html)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{analysis_id}_field_report_{lang}.pdf"'},
    )


@router.get("")
async def list_analyses():
    with get_session() as session:
        rows = session.exec(select(Analysis).order_by(Analysis.created_at.desc())).all()
        return [
            {
                "id": r.id,
                "mode": r.mode,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
