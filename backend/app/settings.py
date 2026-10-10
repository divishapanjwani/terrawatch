"""Editable priority-score weights, persisted to data/settings.json. Read
once per new analysis in app/pipeline/run.py -- editing them in the
Settings panel takes effect for the NEXT analysis you run, not analyses
already on screen (no live recompute).
"""

import json

from app import config
from app.db import DATA_DIR

SETTINGS_PATH = DATA_DIR / "settings.json"

WEIGHT_KEYS = ["w1_severity", "w2_population", "w3_facility_proximity", "w4_confidence", "w5_route_impact"]

_DEFAULTS = {
    "w1_severity": config.PRIORITY_W1_SEVERITY,
    "w2_population": config.PRIORITY_W2_POPULATION,
    "w3_facility_proximity": config.PRIORITY_W3_FACILITY_PROXIMITY,
    "w4_confidence": config.PRIORITY_W4_CONFIDENCE,
    "w5_route_impact": config.PRIORITY_W5_ROUTE_IMPACT,
}


def get_priority_weights() -> dict:
    if SETTINGS_PATH.exists():
        try:
            stored = json.loads(SETTINGS_PATH.read_text())
            return {k: float(stored.get(k, _DEFAULTS[k])) for k in WEIGHT_KEYS}
        except (json.JSONDecodeError, ValueError, TypeError):
            return dict(_DEFAULTS)
    return dict(_DEFAULTS)


def set_priority_weights(weights: dict) -> dict:
    current = get_priority_weights()
    for k in WEIGHT_KEYS:
        if k in weights:
            current[k] = float(weights[k])
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(current))
    return current
