import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

# Read-only bundled assets (eval results, demo/case-study imagery, population raster).
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
# Writable runtime state (sqlite db, uploads, analysis outputs, caches, settings).
# Defaults to DATA_DIR locally; in deployment point TERRAWATCH_STATE_DIR at a
# persistent disk so it survives restarts without hiding the bundled assets.
STATE_DIR = Path(os.environ.get("TERRAWATCH_STATE_DIR", DATA_DIR))
UPLOADS_DIR = STATE_DIR / "uploads"
ANALYSES_DIR = STATE_DIR / "analyses"
OSM_CACHE_DIR = STATE_DIR / "osm_cache"
ROUTE_GRAPH_CACHE_DIR = STATE_DIR / "route_graphs"
DB_PATH = STATE_DIR / "terrawatch.db"

for d in (DATA_DIR, STATE_DIR, UPLOADS_DIR, ANALYSES_DIR, OSM_CACHE_DIR, ROUTE_GRAPH_CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
