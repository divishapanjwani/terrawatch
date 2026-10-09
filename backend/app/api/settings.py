from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import settings as settings_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


class PriorityWeights(BaseModel):
    w1_severity: float | None = None
    w2_population: float | None = None
    w3_facility_proximity: float | None = None
    w4_confidence: float | None = None
    w5_route_impact: float | None = None


@router.get("/weights")
async def get_weights():
    return settings_store.get_priority_weights()


@router.post("/weights")
async def set_weights(weights: PriorityWeights):
    data = {k: v for k, v in weights.model_dump().items() if v is not None}
    for k, v in data.items():
        if v < 0:
            raise HTTPException(status_code=400, detail=f"{k} must be >= 0")
    return settings_store.set_priority_weights(data)
