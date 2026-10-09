from pathlib import Path

from sqlmodel import SQLModel, create_engine, Session

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
ANALYSES_DIR = DATA_DIR / "analyses"
DB_PATH = DATA_DIR / "terrawatch.db"

for d in (DATA_DIR, UPLOADS_DIR, ANALYSES_DIR):
    d.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
