"""Engine 1: TinyCD, a pretrained Siamese change-detection CNN trained on
LEVIR-CD (AndreaCodegoni/Tiny_model_4_CD). Tried in priority order
TinyCD -> BIT -> ChangeFormer per the brief; TinyCD's weights are the only
one of the three with a scripted (non-interactive) download, so it's what's
wired in. Falls back to the spectral baseline (app/engines/spectral.py) if
the weights file is missing or fails to load.
"""

import threading
from pathlib import Path

import numpy as np
import torch

from app.geo.align import AlignedPair

ENGINE_NAME = "siamese_levir_cd"

WEIGHTS_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "tinycd" / "levir_best.pth"

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

TILE_SIZE = 256
TILE_OVERLAP = 32

_model = None
_load_failed = False
_load_lock = threading.Lock()


def _load_model():
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    with _load_lock:
        if _model is not None or _load_failed:
            return _model
        try:
            from app.engines.tinycd_src.change_classifier import ChangeClassifier

            if not WEIGHTS_PATH.exists():
                raise FileNotFoundError(f"TinyCD weights not found at {WEIGHTS_PATH}")
            model = ChangeClassifier(bkbn_name="efficientnet_b4", pretrained=False, output_layer_bkbn="3")
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


def _to_rgb_uint8(bands: np.ndarray, dtype: str) -> np.ndarray:
    """bands: (>=3, H, W) native dtype -> (3, H, W) uint8 (TinyCD expects
    photographic 0-255 RGB, matching LEVIR-CD)."""
    rgb = bands[:3].astype(np.float32)
    if dtype == "uint8":
        return np.clip(rgb, 0, 255).astype(np.uint8)
    out = np.zeros_like(rgb, dtype=np.uint8)
    for i in range(3):
        band = rgb[i]
        lo, hi = np.percentile(band, [2, 98])
        if hi <= lo:
            hi = lo + 1
        out[i] = np.clip((band - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    return out


def _normalize(rgb_uint8: np.ndarray) -> torch.Tensor:
    x = rgb_uint8.astype(np.float32) / 255.0
    x = (x - _IMAGENET_MEAN[:, None, None]) / _IMAGENET_STD[:, None, None]
    return torch.from_numpy(x).unsqueeze(0).float()


def _padded_size(total: int, tile: int, stride: int) -> int:
    if total <= tile:
        return tile
    n_steps = -(-(total - tile) // stride)  # ceil division
    return tile + n_steps * stride


def predict(aligned: AlignedPair) -> np.ndarray:
    """Tiled (256x256, overlapping) inference on an aligned geo raster pair.
    Returns a (H, W) float32 probability map."""
    if aligned.band_count < 3:
        raise ValueError("Engine 1 requires at least 3 (RGB) bands")
    before_rgb = _to_rgb_uint8(aligned.before, aligned.dtype)
    after_rgb = _to_rgb_uint8(aligned.after, aligned.dtype)
    return predict_arrays(before_rgb, after_rgb, aligned.dtype)


def predict_arrays(before_bands: np.ndarray, after_bands: np.ndarray, dtype: str) -> np.ndarray:
    """Tiled (256x256, overlapping) inference on plain (>=3, H, W) arrays —
    no CRS/georeferencing involved. Used directly for LEVIR-CD evaluation,
    which ships as plain PNGs with no geo metadata. Stitched by averaging
    overlapping tile predictions. Returns a (H, W) float32 probability map
    (the model applies sigmoid internally)."""
    model = _load_model()
    if model is None:
        raise RuntimeError("TinyCD weights are not available")

    before_rgb = _to_rgb_uint8(before_bands, dtype)
    after_rgb = _to_rgb_uint8(after_bands, dtype)

    H, W = before_rgb.shape[1], before_rgb.shape[2]
    stride = TILE_SIZE - TILE_OVERLAP

    Hp = _padded_size(H, TILE_SIZE, stride)
    Wp = _padded_size(W, TILE_SIZE, stride)
    pad_h, pad_w = Hp - H, Wp - W

    before_p = np.pad(before_rgb, ((0, 0), (0, pad_h), (0, pad_w)), mode="reflect")
    after_p = np.pad(after_rgb, ((0, 0), (0, pad_h), (0, pad_w)), mode="reflect")

    prob_sum = np.zeros((Hp, Wp), dtype=np.float32)
    weight_sum = np.zeros((Hp, Wp), dtype=np.float32)

    ys = list(range(0, Hp - TILE_SIZE + 1, stride)) or [0]
    xs = list(range(0, Wp - TILE_SIZE + 1, stride)) or [0]

    with torch.no_grad():
        for y in ys:
            for x in xs:
                b_tile = before_p[:, y : y + TILE_SIZE, x : x + TILE_SIZE]
                a_tile = after_p[:, y : y + TILE_SIZE, x : x + TILE_SIZE]
                out = model(_normalize(b_tile), _normalize(a_tile))
                prob_tile = out.squeeze(0).squeeze(0).numpy()
                prob_sum[y : y + TILE_SIZE, x : x + TILE_SIZE] += prob_tile
                weight_sum[y : y + TILE_SIZE, x : x + TILE_SIZE] += 1.0

    weight_sum[weight_sum == 0] = 1.0
    prob = (prob_sum / weight_sum)[:H, :W]
    return prob.astype(np.float32)
