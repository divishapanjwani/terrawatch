"""Pre-detection quality check: cloud cover, misalignment, resolution,
bands. Run once per analysis, saved with it, and shown as a quiet amber
warning banner in the UI when a threshold is crossed. Also produces the
per-pixel cloud masks the false-alarm filter uses (app/pipeline/false_alarm.py).
"""

from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np
from skimage.registration import phase_cross_correlation

from app import config
from app.geo.align import AlignedPair

# Band index convention used throughout the pipeline (see engine2.py):
# 0=R, 1=G, 2=B, 3=NIR, 4=SWIR, 5=SCL (if present).
SCL_BAND_INDEX = 5


@dataclass
class QualityReport:
    before_cloud_pct: float
    after_cloud_pct: float
    cloud_method: str  # "scl" | "brightness_heuristic"
    misalignment_px: float
    resolution_m: float
    band_count: int
    engine: Optional[str] = None
    warnings: Optional[list] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _brightness_heuristic_cloud_mask(rgb: np.ndarray) -> np.ndarray:
    """rgb: (3, H, W) native-dtype. Cloud-like = bright AND low-saturation
    (flat colored), both relative to this image's own distribution."""
    rgb = rgb.astype(np.float32)
    brightness = rgb.mean(axis=0)
    saturation = (rgb.max(axis=0) - rgb.min(axis=0)) / (brightness + 1e-6)
    bright_thresh = np.percentile(brightness, config.CLOUD_HEURISTIC_BRIGHTNESS_PERCENTILE)
    sat_thresh = np.percentile(saturation, config.CLOUD_HEURISTIC_SATURATION_PERCENTILE)
    return (brightness >= bright_thresh) & (saturation <= sat_thresh)


def compute_cloud_mask(bands: np.ndarray) -> tuple[np.ndarray, str]:
    """bands: (N, H, W) native dtype, band order R,G,B,NIR,SWIR,[SCL].
    Returns (cloud_mask bool (H,W), method)."""
    if bands.shape[0] > SCL_BAND_INDEX:
        scl = bands[SCL_BAND_INDEX]
        mask = np.isin(scl, config.SCL_CLOUD_CLASSES)
        return mask, "scl"
    rgb = bands[: min(3, bands.shape[0])]
    if rgb.shape[0] < 3:
        rgb = np.repeat(rgb[:1], 3, axis=0)
    return _brightness_heuristic_cloud_mask(rgb), "brightness_heuristic"


def compute_misalignment_px(before_rgb: np.ndarray, after_rgb: np.ndarray, valid_mask: np.ndarray) -> float:
    """Phase-correlation residual shift (pixels) between before/after,
    AFTER they've already been resampled onto the same grid by
    app/geo/align.py. A non-zero result here means the source imagery's own
    georeferencing doesn't actually line up with reality by that many
    pixels, not just that the grids differ."""
    before_gray = before_rgb.astype(np.float32).mean(axis=0)
    after_gray = after_rgb.astype(np.float32).mean(axis=0)
    if valid_mask.any():
        before_gray = np.where(valid_mask, before_gray, 0.0)
        after_gray = np.where(valid_mask, after_gray, 0.0)
    shift, _error, _diffphase = phase_cross_correlation(before_gray, after_gray, upsample_factor=10)
    return float(np.hypot(shift[0], shift[1]))


def run_quality_check(aligned: AlignedPair) -> tuple[QualityReport, np.ndarray, np.ndarray]:
    """Returns (report, before_cloud_mask, after_cloud_mask)."""
    before_cloud_mask, before_method = compute_cloud_mask(aligned.before)
    after_cloud_mask, after_method = compute_cloud_mask(aligned.after)
    method = before_method if before_method == after_method else f"{before_method}/{after_method}"

    valid = aligned.before_mask & aligned.after_mask
    before_cloud_pct = float(100.0 * before_cloud_mask[valid].mean()) if valid.any() else 0.0
    after_cloud_pct = float(100.0 * after_cloud_mask[valid].mean()) if valid.any() else 0.0

    before_rgb = aligned.before[: min(3, aligned.band_count)]
    after_rgb = aligned.after[: min(3, aligned.band_count)]
    misalignment_px = compute_misalignment_px(before_rgb, after_rgb, valid)

    resolution_m = float(abs(aligned.transform.a))

    warnings = []
    if before_cloud_pct > config.CLOUD_WARNING_PCT:
        warnings.append(f"Before image is {before_cloud_pct:.0f}% cloud-covered.")
    if after_cloud_pct > config.CLOUD_WARNING_PCT:
        warnings.append(f"After image is {after_cloud_pct:.0f}% cloud-covered.")
    if misalignment_px > config.MISALIGNMENT_WARNING_PX:
        warnings.append(
            f"Before/after images appear misaligned by ~{misalignment_px:.1f} px "
            "even after co-registration -- check source georeferencing."
        )

    report = QualityReport(
        before_cloud_pct=before_cloud_pct,
        after_cloud_pct=after_cloud_pct,
        cloud_method=method,
        misalignment_px=misalignment_px,
        resolution_m=resolution_m,
        band_count=aligned.band_count,
        warnings=warnings,
    )
    return report, before_cloud_mask, after_cloud_mask
