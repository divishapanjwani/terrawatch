"""
Generate a synthetic before/after GeoTIFF pair with KNOWN planted changes,
so the TerraWatch pipeline can be checked against an exact answer key.

Scene: 512 x 512 px at 1 m/pixel (512 m x 512 m), EPSG:32643 (UTM 43N, near Pune).
Bands (uint8): 1=Red, 2=Green, 3=Blue, 4=NIR.

REAL changes (should be detected):
  R1 new_building       20 x 30 m roof on empty land
  R2 destroyed_building 25 x 25 m building replaced by rubble
  R3 flooding           irregular water body over grassland
  R4 landslide          diagonal bare-soil strip over vegetation
  R5 small_shed         4 x 4 m = 16 m2 (tests the minimum-area filter)

FAKE changes (should NOT end up as real changes):
  F1 seasonal_vegetation  green crop field turns brown (same field, same shape)
  F2 shadow_shift         shadows of unchanged buildings flip from SE to SW
  F3 cloud                small soft cloud in the after image
  F4 global_brightness    whole after image ~6% brighter + sensor noise

Run:  python make_test_pair.py   (needs numpy, scipy, rasterio, shapely, pillow)
"""
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.transform import from_origin
from rasterio.warp import transform as warp_transform
from scipy.ndimage import gaussian_filter, shift as nd_shift
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from PIL import Image

OUT = Path(__file__).parent
H = W = 512
RES = 1.0
CRS = "EPSG:32643"
ORIGIN_E, ORIGIN_N = 373000.0, 2049000.0  # top-left corner, near Pune
TRANSFORM = from_origin(ORIGIN_E, ORIGIN_N, RES, RES)
rng = np.random.default_rng(42)

def smooth_noise(sigma, amp):
    n = gaussian_filter(rng.standard_normal((H, W)), sigma)
    return n / (n.std() + 1e-9) * amp

def paint(img, mask, rgbn, jitter=0.0):
    for b in range(4):
        val = rgbn[b] + (rng.standard_normal(mask.sum()) * jitter if jitter else 0)
        img[b][mask] = val

def rect(r0, r1, c0, c1):
    m = np.zeros((H, W), bool)
    m[r0:r1, c0:c1] = True
    return m

rows, cols = np.mgrid[0:H, 0:W]

# ---------------- base landscape ----------------
base = np.zeros((4, H, W), np.float32)
soil_mix = (smooth_noise(25, 1) > 0.3)  # patches of dry soil among grass
grass = np.array([85, 120, 60, 170], np.float32)
soil = np.array([140, 120, 95, 115], np.float32)
for b in range(4):
    base[b] = np.where(soil_mix, soil[b], grass[b]) + smooth_noise(3, 6)

# roads
road = rect(250, 258, 0, W) | rect(0, H, 300, 308)
paint(base, road, [115, 115, 112, 100], 3)

before = base.copy()
after = base.copy()

# ---------------- unchanged buildings (with shadows) ----------------
buildings = [  # r0, r1, c0, c1, roof colour
    (40, 58, 30, 50, [190, 185, 175, 160]),
    (40, 60, 75, 95, [170, 90, 70, 120]),
    (85, 105, 30, 55, [200, 200, 195, 170]),
    (85, 103, 80, 100, [160, 160, 160, 140]),
    (130, 150, 40, 65, [180, 110, 80, 125]),
    (100, 120, 420, 440, [195, 190, 180, 165]),
    (140, 160, 360, 385, [175, 95, 75, 120]),
]
SHADOW = 0.45
def shadow_mask(r0, r1, c0, c1, dr, dc):
    s = rect(r0 + dr, r1 + dr, c0 + dc, c1 + dc)
    return s & ~rect(r0, r1, c0, c1)

shadow_before = np.zeros((H, W), bool)
shadow_after = np.zeros((H, W), bool)
bld_union = np.zeros((H, W), bool)
for r0, r1, c0, c1, col in buildings:
    shadow_before |= shadow_mask(r0, r1, c0, c1, 5, 5)    # sun from NW -> shadow SE
    shadow_after |= shadow_mask(r0, r1, c0, c1, 5, -5)    # sun from NE -> shadow SW
    bld_union |= rect(r0, r1, c0, c1)
shadow_before &= ~bld_union
shadow_after &= ~bld_union
before[:, shadow_before] *= SHADOW
after[:, shadow_after] *= SHADOW
for r0, r1, c0, c1, col in buildings:
    m = rect(r0, r1, c0, c1)
    paint(before, m, col, 2)
    paint(after, m, col, 2)

ignore = np.zeros((H, W), bool)   # pixels excluded from scoring (shadows of changed buildings)

# ---------------- REAL changes ----------------
real = {}

# R1 new building (after only) + its shadow (ignored for scoring)
r1 = rect(330, 350, 60, 90)
s1 = shadow_mask(330, 350, 60, 90, 5, -5) & ~r1
after[:, s1] *= SHADOW
paint(after, r1, [205, 95, 70, 125], 2)
real["R1"] = ("new_building", r1)
ignore |= s1

# R2 destroyed building: present before, rubble after
r2 = rect(60, 85, 370, 395)
s2 = shadow_mask(60, 85, 370, 395, 5, 5) & ~r2
before[:, s2] *= SHADOW
paint(before, r2, [185, 180, 170, 160], 2)
rubble = smooth_noise(1.0, 25)
for b, v in enumerate([125, 115, 105, 105]):
    after[b][r2] = v + rubble[r2]
real["R2"] = ("destroyed_building", r2)
ignore |= s2

# R3 flood: irregular ellipse
ell = ((rows - 420) / 25.0) ** 2 + ((cols - 180) / 45.0) ** 2
r3 = (ell + smooth_noise(6, 0.25)) < 1.0
paint(after, r3, [45, 65, 95, 25], 3)
real["R3"] = ("flooding", r3)

# R4 landslide strip from (300,420) to (470,470), width ~14 m
p0, p1 = np.array([300, 420.0]), np.array([470, 470.0])
d = p1 - p0
t = np.clip(((rows - p0[0]) * d[0] + (cols - p0[1]) * d[1]) / (d @ d), 0, 1)
dist = np.hypot(rows - (p0[0] + t * d[0]), cols - (p0[1] + t * d[1]))
r4 = dist < 7
# make the strip sit on vegetation in "before"
paint(before, r4, [70, 125, 55, 185], 5)
paint(after, r4, [155, 125, 95, 110], 6)
real["R4"] = ("landslide_bare_soil", r4)

# R5 small shed
r5 = rect(200, 204, 450, 454)
paint(after, r5, [210, 210, 205, 170], 1)
real["R5"] = ("small_shed_16m2", r5)

# ---------------- FAKE changes ----------------
fake = {}
# F1 seasonal vegetation: crop field green -> brown, with row texture
f1 = rect(140, 220, 150, 270)
rows_tex = (np.sin(cols * 2 * np.pi / 6) * 6)
for b, v in enumerate([60, 115, 45, 200]):
    before[b][f1] = v + rows_tex[f1] + smooth_noise(2, 4)[f1]
for b, v in enumerate([150, 125, 70, 120]):
    after[b][f1] = v + rows_tex[f1] + smooth_noise(2, 4)[f1]
fake["F1"] = ("seasonal_vegetation", f1)

# F2 shadow shift
f2 = shadow_before ^ shadow_after
fake["F2"] = ("shadow_shift", f2)

# F3 cloud (soft)
cd = np.hypot(rows - 460, cols - 330)
alpha = np.clip(1 - cd / 22, 0, 1) ** 0.7
alpha *= 0.85
for b in range(4):
    after[b] = after[b] * (1 - alpha) + 235 * alpha
f3 = alpha > 0.15
fake["F3"] = ("cloud", f3)

# F4 global brightness + sensor noise (applied everywhere)
after = after * 1.06 + 3
before += rng.standard_normal(before.shape) * 3
after += rng.standard_normal(after.shape) * 3

before = np.clip(before, 0, 255).astype(np.uint8)
after = np.clip(after, 0, 255).astype(np.uint8)

# ---------------- write rasters ----------------
profile = dict(driver="GTiff", height=H, width=W, count=4, dtype="uint8",
               crs=CRS, transform=TRANSFORM, compress="deflate", tiled=True,
               blockxsize=256, blockysize=256, photometric="RGB")
def write(name, arr, count=4, desc=("Red", "Green", "Blue", "NIR"), extra=None):
    p = dict(profile, count=count)
    if count != 3 and count != 4:
        p.pop("photometric")
    if count == 4:
        p["photometric"] = "RGB"
        p["alpha"] = "unspecified"
    p.update(extra or {})
    with rasterio.open(OUT / name, "w", **p) as dst:
        dst.write(arr if arr.ndim == 3 else arr[None])
        for i, dsc in enumerate(desc[:count], 1):
            dst.set_band_description(i, dsc)

write("before.tif", before)
write("after.tif", after)
write("before_rgb.tif", before[:3], count=3)
write("after_rgb.tif", after[:3], count=3)

# misaligned variant: after shifted 3 px east (tests alignment warning)
mis = np.stack([nd_shift(after[b], (0, 3), order=0, mode="nearest") for b in range(4)])
write("after_misaligned_3px.tif", mis)

real_mask = np.zeros((H, W), np.uint8)
for _, (_, m) in real.items():
    real_mask[m] = 1
real_mask[ignore & (real_mask == 0)] = 255
write("ground_truth_real_changes.tif", real_mask, count=1, desc=("real_change(1)/ignore(255)",),
      extra={"photometric": "MINISBLACK", "nodata": None})

fake_mask = np.zeros((H, W), np.uint8)
for _, (_, m) in fake.items():
    fake_mask[m] = 1
write("fake_changes_mask.tif", fake_mask, count=1, desc=("fake_change(1)",),
      extra={"photometric": "MINISBLACK", "nodata": None})

# ---------------- answer key ----------------
def mask_to_poly(m):
    geoms = [shape(g) for g, v in shapes(m.astype(np.uint8), mask=m, transform=TRANSFORM) if v == 1]
    return unary_union(geoms)

def to_lonlat(x, y):
    lon, lat = warp_transform(CRS, "EPSG:4326", [x], [y])
    return lon[0], lat[0]

features, table = [], []
for kind, group in (("real", real), ("fake", fake)):
    for rid, (label, m) in group.items():
        poly = mask_to_poly(m)
        c = poly.centroid
        lon, lat = to_lonlat(c.x, c.y)
        area = float(m.sum() * RES * RES)
        # reproject polygon to EPSG:4326 for the geojson
        def proj_ring(coords):
            xs, ys = zip(*coords)
            lo, la = warp_transform(CRS, "EPSG:4326", list(xs), list(ys))
            return list(zip(lo, la))
        gj = mapping(poly)
        if gj["type"] == "Polygon":
            gj["coordinates"] = [proj_ring(r) for r in gj["coordinates"]]
        else:
            gj["coordinates"] = [[proj_ring(r) for r in p] for p in gj["coordinates"]]
        props = dict(id=rid, kind=kind, label=label, area_m2=area,
                     centroid_lat=round(lat, 6), centroid_lon=round(lon, 6))
        features.append(dict(type="Feature", properties=props, geometry=gj))
        table.append(props)

(OUT / "answer_key.geojson").write_text(json.dumps(dict(type="FeatureCollection", features=features), indent=1))
(OUT / "answer_key.json").write_text(json.dumps(table, indent=1))

# ---------------- preview ----------------
def rgb(a):
    return np.transpose(a[:3], (1, 2, 0))
gap = np.full((H, 12, 3), 255, np.uint8)
gt_vis = np.zeros((H, W, 3), np.uint8)
gt_vis[real_mask == 1] = [220, 50, 40]
gt_vis[fake_mask == 1] = [140, 140, 140]
gt_vis[real_mask == 255] = [60, 60, 60]
Image.fromarray(np.hstack([rgb(before), gap, rgb(after), gap, gt_vis])).save(OUT / "preview_before_after_answers.png")

for row in table:
    print(row)
