"""OSCD dataset loader.

Expects the layout produced by extracting the three HF-mirrored OSCD zips
(see HANDOFF.md for the download step) into `backend/data/oscd_raw/`:

    data/oscd_raw/images/Onera Satellite Change Detection dataset - Images/<city>/imgs_1_rect/B##.tif
    data/oscd_raw/images/.../<city>/imgs_2_rect/B##.tif
    data/oscd_raw/train_labels/.../<city>/cm/cm.png
    data/oscd_raw/test_labels/.../<city>/cm/cm.png

`imgs_{1,2}_rect` are the official co-registered/resampled band stacks (all
13 bands already on one common pixel grid per city — confirmed by
inspection: every band, native 10/20/60m, comes out the same width/height).
None of this has real georeferencing (identity transform) — OSCD is for
model evaluation/training only, never for the geo pipeline.

We use 5 of the 13 bands, matching what app/engines/engine2.py and our own
Sentinel-2 fetch scripts use: Red (B04), Green (B03), Blue (B02), NIR
(B08), SWIR (B11).
"""
from pathlib import Path
from typing import Optional

import numpy as np
import rasterio

BAND_FILES = {"R": "B04.tif", "G": "B03.tif", "B": "B02.tif", "NIR": "B08.tif", "SWIR": "B11.tif"}
IMAGES_SUBDIR = "images/Onera Satellite Change Detection dataset - Images"
TRAIN_LABELS_SUBDIR = "train_labels/Onera Satellite Change Detection dataset - Train Labels"
TEST_LABELS_SUBDIR = "test_labels/Onera Satellite Change Detection dataset - Test Labels"

TRAIN_CITIES = [
    "abudhabi", "aguasclaras", "beihai", "beirut", "bercy", "bordeaux",
    "cupertino", "hongkong", "mumbai", "nantes", "paris", "pisa", "rennes", "saclay_e",
]
TEST_CITIES = [
    "brasilia", "chongqing", "dubai", "lasvegas", "milano",
    "montpellier", "norcia", "rio", "saclay_w", "valencia",
]


def _load_bands(city_dir: Path) -> np.ndarray:
    """Returns (5, H, W) uint16, bands in R,G,B,NIR,SWIR order."""
    bands = []
    for key in ["R", "G", "B", "NIR", "SWIR"]:
        with rasterio.open(city_dir / BAND_FILES[key]) as src:
            bands.append(src.read(1))
    return np.stack(bands, axis=0)


def load_oscd_city(base_dir: Path, city: str, split: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (before 5xHxW uint16, after 5xHxW uint16, label HxW bool)."""
    images_dir = base_dir / IMAGES_SUBDIR / city
    labels_subdir = TRAIN_LABELS_SUBDIR if split == "train" else TEST_LABELS_SUBDIR
    label_path = base_dir / labels_subdir / city / "cm" / "cm.png"

    before = _load_bands(images_dir / "imgs_1_rect")
    after = _load_bands(images_dir / "imgs_2_rect")

    from PIL import Image
    label = np.array(Image.open(label_path).convert("L")) > 127

    return before, after, label


def load_oscd_test_pairs(
    base_dir: Path, limit: Optional[int] = None
) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, str]]:
    cities = TEST_CITIES[:limit] if limit else TEST_CITIES
    pairs = []
    for city in cities:
        before, after, label = load_oscd_city(base_dir, city, "test")
        pairs.append((before, after, label, city))
    return pairs


def available(base_dir: Path) -> bool:
    return (base_dir / IMAGES_SUBDIR).exists()
