import numpy as np
from skimage.morphology import opening, closing, disk, remove_small_objects


def clean_mask(
    prob_map: np.ndarray,
    threshold: float,
    pixel_area_m2: float,
    min_area_m2: float,
    morph_radius_px: int,
    valid_mask: np.ndarray,
) -> np.ndarray:
    """Threshold -> opening -> closing -> drop small objects. Returns a
    boolean mask. `pixel_area_m2` converts the m^2 minimum area into a
    pixel-count minimum."""
    binary = (prob_map >= threshold) & valid_mask

    if morph_radius_px > 0:
        selem = disk(morph_radius_px)
        binary = opening(binary, selem)
        binary = closing(binary, selem)

    min_size_px = max(1, int(round(min_area_m2 / pixel_area_m2)))
    # max_size removes objects <= max_size (keeps objects > max_size), so
    # max_size=min_size_px-1 keeps objects >= min_size_px.
    binary = remove_small_objects(binary, max_size=min_size_px - 1, connectivity=1)

    return binary
