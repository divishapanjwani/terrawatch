import numpy as np

from app.geo.align import AlignedPair


def compute_magnitude_map(aligned: AlignedPair) -> np.ndarray:
    """Per-pixel spectral change magnitude: Euclidean distance across all
    aligned bands, in native DN units. Independent of which detection
    engine is used — this is the physical "how much did the pixel change"
    measure used for the change_magnitude attribute and (as a fallback) for
    the spectral baseline's own probability map."""
    before = aligned.before.astype(np.float32)
    after = aligned.after.astype(np.float32)
    diff = after - before
    return np.sqrt((diff**2).sum(axis=0))
