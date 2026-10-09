"""Engine 2: a small U-Net trained on OSCD for Sentinel-2 multispectral
change detection (app/engines/unet_model.py). Input follows the brief:
stacked before/after bands + index differences (dNDVI, dNDWI, dNDBI,
dBrightness).

Band convention (matches our own Sentinel-2 fetch scripts and OSCD):
index 0=Red, 1=Green, 2=Blue, 3=NIR, 4=SWIR (if present). Values are raw
Sentinel-2-style reflectance (uint16, DN = reflectance * 10000) — NOT
0-255 display bytes. If a 5th (SWIR) band isn't available, the SWIR band
and the NDBI channel are zero-filled and that's reflected in confidence.
"""
from pathlib import Path

import numpy as np
import torch

from app.geo.align import AlignedPair
from app.engines.unet_model import SmallUNet

ENGINE_NAME = "unet_oscd"

WEIGHTS_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "engine2" / "unet_oscd.pth"

REFLECTANCE_SCALE = 10000.0
EPS = 1e-6
IN_CHANNELS = 14  # 5 before + 5 after + dNDVI + dNDWI + dNDBI + dBrightness
BASE_WIDTH = 16

_model = None
_load_failed = False


def _load_model():
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    try:
        if not WEIGHTS_PATH.exists():
            raise FileNotFoundError(f"Engine 2 weights not found at {WEIGHTS_PATH}")
        model = SmallUNet(in_channels=IN_CHANNELS, base_width=BASE_WIDTH)
        state_dict = torch.load(str(WEIGHTS_PATH), map_location="cpu")
        model.load_state_dict(state_dict, strict=True)
        model.eval()
        _model = model
    except Exception:
        _load_failed = True
        _model = None
    return _model


def is_available() -> bool:
    return _load_model() is not None


def _pad_5bands(bands: np.ndarray) -> np.ndarray:
    """bands: (N, H, W), N in {3,4,5}. Returns (5, H, W) float32, padding
    with zeros for any missing NIR/SWIR band."""
    n, h, w = bands.shape
    out = np.zeros((5, h, w), dtype=np.float32)
    out[: min(n, 5)] = bands[: min(n, 5)].astype(np.float32)
    return out


def compute_features(before_5band: np.ndarray, after_5band: np.ndarray) -> np.ndarray:
    """before/after: (5, H, W) raw Sentinel-2-style reflectance (R,G,B,NIR,SWIR).
    Returns (14, H, W) float32 feature stack for the U-Net."""
    before = np.clip(before_5band.astype(np.float32) / REFLECTANCE_SCALE, 0, 1.5)
    after = np.clip(after_5band.astype(np.float32) / REFLECTANCE_SCALE, 0, 1.5)

    def indices(x):
        r, g, b, nir, swir = x
        ndvi = (nir - r) / (nir + r + EPS)
        ndwi = (g - nir) / (g + nir + EPS)
        ndbi = (swir - nir) / (swir + nir + EPS)
        brightness = (r + g + b) / 3.0
        return ndvi, ndwi, ndbi, brightness

    ndvi_b, ndwi_b, ndbi_b, bright_b = indices(before)
    ndvi_a, ndwi_a, ndbi_a, bright_a = indices(after)

    d_ndvi = ndvi_a - ndvi_b
    d_ndwi = ndwi_a - ndwi_b
    d_ndbi = ndbi_a - ndbi_b
    d_bright = bright_a - bright_b

    return np.concatenate(
        [before, after, d_ndvi[None], d_ndwi[None], d_ndbi[None], d_bright[None]], axis=0
    ).astype(np.float32)


def _pad_to_multiple(x: np.ndarray, multiple: int = 16) -> tuple[np.ndarray, int, int]:
    _, h, w = x.shape
    pad_h = (-h) % multiple
    pad_w = (-w) % multiple
    return np.pad(x, ((0, 0), (0, pad_h), (0, pad_w)), mode="reflect"), h, w


def predict_arrays(before_bands: np.ndarray, after_bands: np.ndarray) -> np.ndarray:
    """before/after: (N, H, W) raw Sentinel-2-style reflectance, N in {3,4,5}.
    Returns (H, W) float32 probability map (no CRS/alignment involved)."""
    model = _load_model()
    if model is None:
        raise RuntimeError("Engine 2 weights are not available")

    before5 = _pad_5bands(before_bands)
    after5 = _pad_5bands(after_bands)
    features = compute_features(before5, after5)
    features_padded, h, w = _pad_to_multiple(features)

    with torch.no_grad():
        x = torch.from_numpy(features_padded).unsqueeze(0).float()
        out = model(x)
    prob = out.squeeze(0).squeeze(0).numpy()[:h, :w]
    return prob.astype(np.float32)


def predict(aligned: AlignedPair) -> np.ndarray:
    return predict_arrays(aligned.before, aligned.after)
