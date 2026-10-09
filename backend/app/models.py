from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Analysis(SQLModel, table=True):
    id: str = Field(primary_key=True)
    mode: str = Field(default="disaster")  # disaster | prevention
    status: str = Field(default="pending")  # pending | ready | failed
    progress_step: str = Field(default="validating")
    error_message: Optional[str] = Field(default=None)

    before_path: Optional[str] = Field(default=None)
    after_path: Optional[str] = Field(default=None)
    before_png: Optional[str] = Field(default=None)
    after_png: Optional[str] = Field(default=None)

    # bounding coordinates in EPSG:4326, as "west,south,east,north"
    # (before/after previews now share identical bounds — see app/geo/align.py)
    bounds: Optional[str] = Field(default=None)

    engine_choice: str = Field(default="auto")  # auto | tinycd | engine2 | spectral (requested)
    engine: Optional[str] = Field(default=None)  # engine actually used (ENGINE_NAME)
    engine_key: Optional[str] = Field(default=None)  # tinycd | engine2 | spectral (actually used)
    engine_fell_back: bool = Field(default=False)
    pixel_size_m: Optional[float] = Field(default=None)
    polygon_count: int = Field(default=0)
    geojson_path: Optional[str] = Field(default=None)
    gpkg_path: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=utcnow)
