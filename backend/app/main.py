from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.api.analyses import router as analyses_router

app = FastAPI(title="TerraWatch API")

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
