from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
ANALYSES_DIR = DATA_DIR / "analyses"
OSM_CACHE_DIR = DATA_DIR / "osm_cache"
DB_PATH = DATA_DIR / "terrawatch.db"

for d in (DATA_DIR, UPLOADS_DIR, ANALYSES_DIR, OSM_CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
