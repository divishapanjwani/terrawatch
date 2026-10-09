"""Ablation masks for evaluation: raw model -> +morphology -> +false-alarm
filter, each as a pixel-level prediction mask, for plain (non-georeferenced)
test datasets (LEVIR-CD, OSCD). Mirrors the real pipeline's stages
(app/pipeline/run.py) but works directly on plain numpy arrays with a
known pixel size instead of going through AlignedPair/CRS machinery, which
doesn't apply to these datasets.
"""
from types import SimpleNamespace

import numpy as np
from skimage.measure import label as cc_label

from app import config
from app.geo import features
from app.geo.morphology import clean_mask
from app.geo.quality import compute_cloud_mask
from app.pipeline.false_alarm import classify

EPS = 1e-6


def ablation_masks(
    prob_map: np.ndarray,
    before_bands: np.ndarray,
    after_bands: np.ndarray,
    threshold: float,
    pixel_size_m: float,
) -> dict[str, np.ndarray]:
    """Returns {"raw": mask, "morphology": mask, "false_alarm_filter": mask},
    each a boolean (H, W) array."""
    valid = np.ones(prob_map.shape, dtype=bool)

    raw = prob_map >= threshold
    morphology = clean_mask(prob_map, threshold, config.MORPH_RADIUS_PX, valid)

    before_cloud, cloud_method = compute_cloud_mask(before_bands)
    after_cloud, _ = compute_cloud_mask(after_bands)
    cloud_either = before_cloud | after_cloud

    ndvi_b, ndvi_a = features.compute_ndvi(before_bands), features.compute_ndvi(after_bands)
    ndvi_delta = (ndvi_a - ndvi_b) if (ndvi_b is not None and ndvi_a is not None) else None
    ndwi_b, ndwi_a = features.compute_ndwi(before_bands), features.compute_ndwi(after_bands)
    ndwi_delta = (ndwi_a - ndwi_b) if (ndwi_b is not None and ndwi_a is not None) else None
    ndbi_b, ndbi_a = features.compute_ndbi(before_bands), features.compute_ndbi(after_bands)
    ndbi_delta = (ndbi_a - ndbi_b) if (ndbi_b is not None and ndbi_a is not None) else None

    brightness_b = features.compute_brightness(before_bands)
    brightness_a = features.compute_brightness(after_bands)
    scale = features.dynamic_range(brightness_b, valid)
    brightness_delta_frac = (brightness_a - brightness_b) / scale

    texture_b = features.compute_texture(before_bands)
    texture_a = features.compute_texture(after_bands)
    texture_change_frac = np.abs(texture_a - texture_b) / (texture_b + texture_a + EPS)

    edge_map = np.zeros(prob_map.shape, dtype=bool)  # no real nodata boundary on plain test images

    labels = cc_label(morphology, connectivity=1)
    pixel_area_m2 = pixel_size_m ** 2
    band_count = before_bands.shape[0]

    false_alarm_filter = np.zeros_like(morphology)
    for val in range(1, int(labels.max()) + 1):
        comp = labels == val
        if not comp.any():
            continue
        extra = {
            "cloud_overlap": float(cloud_either[comp].mean()),
            "edge_touch": float(edge_map[comp].mean()),
            "brightness_delta_frac": float(brightness_delta_frac[comp].mean()),
            "texture_change_frac": float(texture_change_frac[comp].mean()),
        }
        if ndvi_delta is not None:
            extra["ndvi_delta"] = float(ndvi_delta[comp].mean())
        if ndwi_delta is not None:
            extra["ndwi_delta"] = float(ndwi_delta[comp].mean())
        if ndbi_delta is not None:
            extra["ndbi_delta"] = float(ndbi_delta[comp].mean())

        fake_polygon = SimpleNamespace(area_m2=float(comp.sum()) * pixel_area_m2, extra=extra)
        status, _reason = classify(fake_polygon, band_count, cloud_method)
        if status == "kept":
            false_alarm_filter[comp] = True

    return {"raw": raw, "morphology": morphology, "false_alarm_filter": false_alarm_filter}
