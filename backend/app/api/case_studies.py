import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.api.analyses import _process_analysis
from app.case_studies import CASE_STUDIES, cached_tif_paths, get_case_study
from app.db import ANALYSES_DIR, get_session
from app.models import Analysis

router = APIRouter(prefix="/api/case_studies", tags=["case_studies"])


@router.get("")
async def list_case_studies():
    out = []
    for cs in CASE_STUDIES:
        before_tif, after_tif = cached_tif_paths(cs)
        out.append(
            {
                "slug": cs["slug"],
                "name": cs["name"],
                "location": cs["location"],
                "event_date": cs["event_date"],
                "category": cs["category"],
                "description": cs["description"],
                "bbox": list(cs["bbox"]) if cs["bbox"] else None,
                "known_scenes": cs.get("known_scenes"),
                "thumbnail_url": f"/case_studies/{cs['slug']}.jpg",
                "cached": before_tif.exists() and after_tif.exists(),
            }
        )
    return out


@router.post("/{slug}/load")
async def load_case_study(slug: str, background_tasks: BackgroundTasks, mode: str = "disaster", engine: str = "auto"):
    cs = get_case_study(slug)
    if cs is None:
        raise HTTPException(status_code=404, detail=f"Unknown case study '{slug}'")
    before_tif, after_tif = cached_tif_paths(cs)
    if not (before_tif.exists() and after_tif.exists()):
        raise HTTPException(
            status_code=409,
            detail=f"'{slug}' has no cached imagery. Run scripts/fetch_case_studies.py first.",
        )

    analysis_id = uuid.uuid4().hex[:12]
    output_dir = ANALYSES_DIR / analysis_id
    output_dir.mkdir(parents=True, exist_ok=True)

    analysis = Analysis(
        id=analysis_id,
        mode=mode,
        status="pending",
        progress_step="validating",
        engine_choice=engine,
        case_study_slug=slug,
    )
    with get_session() as session:
        session.add(analysis)
        session.commit()

    background_tasks.add_task(
        _process_analysis,
        analysis_id,
        str(before_tif),
        str(after_tif),
        output_dir,
        engine,
        mode,
    )

    return {"analysis_id": analysis_id}
