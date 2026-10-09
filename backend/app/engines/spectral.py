import numpy as np

from app.geo.align import AlignedPair
from app.engines.common import compute_magnitude_map

ENGINE_NAME = "spectral_baseline"


def predict(aligned: AlignedPair) -> np.ndarray:
    """Fallback / comparison baseline: normalize the raw spectral change
    magnitude by its 98th percentile over valid pixels to get a pseudo
    probability map in [0, 1]. This is intentionally simple — it is NOT
    the main detector; it exists so the UI always has something to show
    and so the trained engines have a baseline to beat."""
    magnitude = compute_magnitude_map(aligned)
    valid = aligned.before_mask & aligned.after_mask
    return predict_arrays_from_magnitude(magnitude, valid)


def predict_arrays(before_bands: np.ndarray, after_bands: np.ndarray) -> np.ndarray:
    """Same baseline on plain (bands, H, W) arrays with no CRS/alignment
    involved — used for OSCD evaluation."""
    before = before_bands.astype(np.float32)
    after = after_bands.astype(np.float32)
    magnitude = np.sqrt(((after - before) ** 2).sum(axis=0))
    valid = np.ones(magnitude.shape, dtype=bool)
    return predict_arrays_from_magnitude(magnitude, valid)


def predict_arrays_from_magnitude(magnitude: np.ndarray, valid: np.ndarray) -> np.ndarray:
    if not valid.any():
        return np.zeros_like(magnitude, dtype=np.float32)
    scale = np.percentile(magnitude[valid], 98)
    if scale <= 0:
        scale = 1.0
    prob = np.clip(magnitude / scale, 0, 1)
    prob[~valid] = 0
    return prob.astype(np.float32)
