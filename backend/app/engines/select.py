"""Engine auto-selection by resolution and band count.

Rule: <=2 m/pixel AND <5 bands (RGB-like, NIR tolerated) -> TinyCD
(Engine 1, trained on 0.5m LEVIR-CD). Everything coarser or genuinely
multispectral -> Engine 2 (OSCD U-Net), falling back to the spectral
baseline if the chosen engine's weights aren't available. This is the
safety net: Engine 1 must never run on Sentinel-2-class imagery, and the
map must never come back empty just because a trained engine is missing.
"""
import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

from app.geo.align import AlignedPair
from app.geo.vectorize import native_pixel_area_m2
from app.engines import siamese, spectral, engine2

HIGH_RES_MAX_PIXEL_M = 2.0
MULTISPECTRAL_MIN_BANDS = 5  # >=5 bands counts as true multispectral regardless of resolution

VALID_FORCED_CHOICES = ("auto", "tinycd", "engine2", "spectral")


@dataclass
class EngineResolution:
    key: str  # "tinycd" | "engine2" | "spectral" — what actually ran
    name: str  # ENGINE_NAME for the engine that actually ran
    requested: str  # what was asked for ("auto" or a forced choice)
    rule_choice: str  # what the resolution/band-count rule picked, before availability fallback
    pixel_size_m: float
    fell_back: bool  # True if the requested/rule-chosen engine wasn't available


def pixel_size_m(aligned: AlignedPair) -> float:
    return math.sqrt(native_pixel_area_m2(aligned))


def rule_based_choice(aligned: AlignedPair) -> str:
    px = pixel_size_m(aligned)
    if px <= HIGH_RES_MAX_PIXEL_M and aligned.band_count < MULTISPECTRAL_MIN_BANDS:
        return "tinycd"
    return "engine2"


def _predict_fn(key: str) -> Callable[[AlignedPair], np.ndarray]:
    return {"tinycd": siamese.predict, "engine2": engine2.predict, "spectral": spectral.predict}[key]


def _engine_name(key: str) -> str:
    return {"tinycd": siamese.ENGINE_NAME, "engine2": engine2.ENGINE_NAME, "spectral": spectral.ENGINE_NAME}[key]


def _is_available(key: str) -> bool:
    if key == "tinycd":
        return siamese.is_available()
    if key == "engine2":
        return engine2.is_available()
    return True  # spectral is always available


def resolve_engine(aligned: AlignedPair, forced: str = "auto") -> EngineResolution:
    if forced not in VALID_FORCED_CHOICES:
        raise ValueError(f"Unknown engine choice {forced!r}, expected one of {VALID_FORCED_CHOICES}")

    rule_choice = rule_based_choice(aligned)
    px = pixel_size_m(aligned)

    if forced == "spectral":
        return EngineResolution("spectral", spectral.ENGINE_NAME, forced, rule_choice, px, fell_back=False)

    if forced in ("tinycd", "engine2"):
        if _is_available(forced):
            return EngineResolution(forced, _engine_name(forced), forced, rule_choice, px, fell_back=False)
        return EngineResolution("spectral", spectral.ENGINE_NAME, forced, rule_choice, px, fell_back=True)

    # auto: use the rule's choice if available.
    if _is_available(rule_choice):
        return EngineResolution(rule_choice, _engine_name(rule_choice), "auto", rule_choice, px, fell_back=False)

    # Fallback must never cross the resolution boundary the other way: if the
    # rule picked Engine 2 (coarse/multispectral input) and it's unavailable,
    # fall straight to the spectral baseline -- NOT to TinyCD, which must
    # never run on Sentinel-2-class imagery. Only TinyCD's own unavailability
    # may fall through to Engine 2 (still RGB-like, still a trained model).
    if rule_choice == "tinycd" and _is_available("engine2"):
        return EngineResolution("engine2", _engine_name("engine2"), "auto", rule_choice, px, fell_back=True)
    return EngineResolution("spectral", spectral.ENGINE_NAME, "auto", rule_choice, px, fell_back=True)


def predict(aligned: AlignedPair, forced: str = "auto") -> tuple[np.ndarray, EngineResolution]:
    resolution = resolve_engine(aligned, forced)
    prob_map = _predict_fn(resolution.key)(aligned)
    return prob_map, resolution
