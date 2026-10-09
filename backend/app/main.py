import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db, DATA_DIR
from app.api.analyses import router as analyses_router

app = FastAPI(title="TerraWatch API")

EVAL_RESULTS_PATH = DATA_DIR / "eval_results.json"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyses_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/metrics")
def metrics():
    """Real precision/recall/F1/FPR from scripts/evaluate.py, never made up.
    Empty list if evaluate.py hasn't been run yet."""
    if not EVAL_RESULTS_PATH.exists():
        return {"results": []}
    return json.loads(EVAL_RESULTS_PATH.read_text())
