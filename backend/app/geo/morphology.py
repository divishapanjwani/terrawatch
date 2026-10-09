import numpy as np
from skimage.morphology import closing, disk, opening


def clean_mask(
    prob_map: np.ndarray,
    threshold: float,
    morph_radius_px: int,
    valid_mask: np.ndarray,
) -> np.ndarray:
    """Threshold -> opening -> closing. Returns a boolean mask.

    Deliberately does NOT drop small objects here -- every surviving
    candidate goes on to vectorization and gets an explicit "too_small"
    rejection (app/pipeline/false_alarm.py) if it's below the minimum
    area, so it's still visible on the rejected-changes layer instead of
    silently vanishing."""
    binary = (prob_map >= threshold) & valid_mask

    if morph_radius_px > 0:
        selem = disk(morph_radius_px)
        binary = opening(binary, selem)
        binary = closing(binary, selem)

    return binary
