import numpy as np

from app.geo.align import AlignedPair
from app.engines.common import compute_magnitude_map

ENGINE_NAME = "spectral_baseline"


def predict(aligned: AlignedPair) -> np.ndarray:
    """Fallback / comparison baseline: normalize the raw spectral change
    magnitude by its 98th percentile over valid pixels to get a pseudo
    probability map in [0, 1]. This is intentionally simple — it is NOT
    the main detector (see app/engines/siamese.py); it exists so the UI
    always has something to show and so Engine 1 has a baseline to beat."""
    magnitude = compute_magnitude_map(aligned)
    valid = aligned.before_mask & aligned.after_mask
    if not valid.any():
        return np.zeros_like(magnitude)
    scale = np.percentile(magnitude[valid], 98)
    if scale <= 0:
        scale = 1.0
    prob = np.clip(magnitude / scale, 0, 1)
    prob[~valid] = 0
    return prob.astype(np.float32)
