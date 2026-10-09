import json
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlmodel import select

from app.config import PROGRESS_STEPS
from app.db import get_session, UPLOADS_DIR, ANALYSES_DIR
from app.models import Analysis
from app.geo.preview import read_metadata
from app.pipeline.run import run_pipeline
from app.engines.select import VALID_FORCED_CHOICES

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
    analysis_id: str, before_path: str, after_path: str, output_dir: Path, engine_choice: str
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
):
    if engine not in VALID_FORCED_CHOICES:
        raise HTTPException(
            status_code=400, detail=f"engine must be one of {VALID_FORCED_CHOICES}"
        )

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
    )

    with get_session() as session:
        session.add(analysis)
        session.commit()

    background_tasks.add_task(
        _process_analysis, analysis_id, str(before_path), str(after_path), output_dir, engine
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
            "progress_steps": PROGRESS_STEPS,
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
            "reject_reason_counts": json.loads(analysis.reject_reason_counts) if analysis.reject_reason_counts else {},
            "summary_line": analysis.summary_line,
            "quality_report": json.loads(analysis.quality_report) if analysis.quality_report else None,
            "created_at": analysis.created_at.isoformat(),
        }


@router.get("/{analysis_id}/imagery/{which}")
async def get_imagery(analysis_id: str, which: str):
    if which not in ("before", "after"):
        raise HTTPException(status_code=400, detail="which must be 'before' or 'after'")
    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        png_path = analysis.before_png if which == "before" else analysis.after_png
        if not png_path:
            raise HTTPException(status_code=409, detail="Imagery not ready yet")
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
