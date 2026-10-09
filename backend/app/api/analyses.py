import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlmodel import select

from app.db import get_session, UPLOADS_DIR, ANALYSES_DIR
from app.models import Analysis
from app.geo.align import load_aligned_pair
from app.geo.preview import generate_preview_pair, read_metadata

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


def _save_upload(upload: UploadFile, dest_path) -> None:
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(upload.file, f)


@router.post("")
async def create_analysis(
    before: UploadFile = File(...),
    after: UploadFile = File(...),
    mode: str = Form("disaster"),
):
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
    )

    with get_session() as session:
        session.add(analysis)
        session.commit()

    try:
        before_meta = read_metadata(str(before_path))
        after_meta = read_metadata(str(after_path))
        if before_meta["crs"] is None or after_meta["crs"] is None:
            raise ValueError("One or both files have no CRS (not georeferenced).")

        before_png = output_dir / "before.png"
        after_png = output_dir / "after.png"
        aligned = load_aligned_pair(str(before_path), str(after_path))
        bounds = generate_preview_pair(aligned, str(before_png), str(after_png))

        with get_session() as session:
            analysis = session.get(Analysis, analysis_id)
            analysis.status = "ready"
            analysis.progress_step = "done"
            analysis.before_png = str(before_png)
            analysis.after_png = str(after_png)
            analysis.bounds = f"{bounds['west']},{bounds['south']},{bounds['east']},{bounds['north']}"
            session.add(analysis)
            session.commit()
    except Exception as exc:  # noqa: BLE001
        with get_session() as session:
            analysis = session.get(Analysis, analysis_id)
            analysis.status = "failed"
            analysis.error_message = str(exc)
            session.add(analysis)
            session.commit()

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
            "error_message": analysis.error_message,
            "bounds": _parse(analysis.bounds),
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
    # Change-detection pipeline lands in a later phase; return an empty
    # GeoJSON FeatureCollection so the frontend map/list code path is stable.
    return JSONResponse({"type": "FeatureCollection", "features": []})


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
