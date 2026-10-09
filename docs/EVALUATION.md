# Evaluation

Three independent evaluations, each on data that actually fits it:

1. **Model-quality ablation** — pixel-level precision/recall/F1, each engine
   on its own resolution-matched, human-labeled test split.
2. **Geo-pipeline acceptance test** — a synthetic, planted-answer-key pair
   that exercises areas, centroids, severity, and export, where "ground
   truth" is exact by construction.
3. **End-to-end real-world case study** — Wayanad, where every number is
   independently re-verified against the live GeoJSON export (see the main
   README's results table).

## 1. Datasets and splits

| Dataset | Used for | Images | Georeferenced? | Resolution |
|---|---|---|---|---|
| [LEVIR-CD](https://justchenhao.github.io/LEVIR/) test split | Engine 1 (TinyCD) | 128 | No (plain PNG) | 0.5 m, RGB |
| [OSCD](https://ieee-dataport.org/open-access/onera-satellite-change-detection-dataset) test split | Engine 2 (U-Net) + spectral baseline | 10 cities | No (13-band rasters, no CRS header used) | 10–60 m, Sentinel-2 |
| `terrawatch-test-pair/` (synthetic, in-repo) | Full geo pipeline | 1 planted pair | Yes (EPSG:32643 UTM) | 1 m, 4-band |
| `sample_data/wayanad/` (real Sentinel-2) | End-to-end case study | 1 real pair | Yes (EPSG:4326 clip) | 10 m, 5-band |

LEVIR-CD and OSCD ship with **no georeferencing**, so `scripts/evaluate.py`
and `app/pipeline/ablation.py` deliberately bypass the geo pipeline (no CRS,
no alignment, no vectorization) and score raw pixel masks directly — see
Gotcha #6 in `HANDOFF.md`. The geo pipeline itself (areas, centroids,
severity, export) is exercised separately by `terrawatch-test-pair/`, which
*is* georeferenced.

## 2. Metric definitions

All model-quality numbers below are **pixel-level**, computed against the
dataset's own human-annotated change mask:

- **Precision** = TP / (TP + FP) — of the pixels flagged as changed, what
  fraction really changed.
- **Recall** = TP / (TP + FN) — of the pixels that really changed, what
  fraction was flagged.
- **F1** = harmonic mean of precision and recall.
- **Accuracy** = (TP + TN) / all pixels.
- **False-positive rate** = FP / (FP + TN).

The ablation adds each pipeline stage in order and re-scores the same
images, so each row shows exactly what that stage changed:

1. **raw** — the engine's thresholded probability map, nothing else.
2. **+ morphology** — opening + closing applied.
3. **+ false-alarm filter** — `app/pipeline/false_alarm.py`'s kept/rejected
   classification applied; only `kept` pixels count as "flagged" in this
   stage's precision/recall.

The synthetic test-pair numbers below are also pixel-level precision/recall/
F1, but scored against `terrawatch-test-pair/ground_truth_real_changes.tif`
using a ≥30%-overlap "found" criterion per planted polygon (see
`check_results.py`) — a different, independent scoring script from
`scripts/evaluate.py`, used deliberately because unlike LEVIR-CD/OSCD this
pair *is* georeferenced and lets us also check areas/centroids/severity, not
just pixels.

## 3. Full ablation table

From `backend/data/eval_results.json` (`GET /api/metrics`, Accuracy page in
the UI):

| Engine | Dataset | Stage | Precision | Recall | F1 | Accuracy | FPR |
|---|---|---|---|---|---|---|---|
| Spectral baseline | OSCD | raw | 15.8% | 59.2% | 0.250 | 81.6% | 17.1% |
| Spectral baseline | OSCD | + morphology | 18.8% | 54.5% | 0.280 | 85.5% | 12.8% |
| Spectral baseline | OSCD | **+ false-alarm filter** | **21.9%** | 53.4% | **0.311** | 87.8% | 10.4% |
| Engine 2 (U-Net) | OSCD | raw | 19.6% | 93.5% | 0.324 | 79.8% | 20.9% |
| Engine 2 (U-Net) | OSCD | + morphology | 19.7% | 93.5% | 0.325 | 79.9% | 20.8% |
| Engine 2 (U-Net) | OSCD | **+ false-alarm filter** | **20.0%** | 92.6% | **0.329** | 80.5% | 20.2% |
| TinyCD | LEVIR-CD | raw | 92.9% | 89.9% | 0.914 | 99.1% | 0.4% |
| TinyCD | LEVIR-CD | + morphology | 92.9% | 89.8% | 0.914 | 99.1% | 0.4% |
| TinyCD | LEVIR-CD | + false-alarm filter | 93.1% | 87.7% | 0.903 | 99.0% | 0.4% |

**Reading this honestly:** precision improves at every stage on both OSCD
engines — the spectral baseline's precision improves by nearly 40%
relative (15.8% → 21.9%). On LEVIR-CD, TinyCD is already so well-calibrated
for its own domain that the filter *trades* a little recall (89.9% → 87.7%)
for a small precision gain — not every stage helps every model, and that's
reported as-is rather than tuned to look uniformly good.

### Reproducing these numbers

```bash
cd backend && source venv/bin/activate

# LEVIR-CD (needs the 496 MB test split — see README "Optional downloads")
python scripts/evaluate.py levircd --ablation

# OSCD, both engines (needs OSCD — see README; engine2 also needs a trained checkpoint)
python scripts/evaluate.py oscd --engine spectral --ablation
python scripts/evaluate.py oscd --engine engine2 --ablation
```

or `make eval` runs all three (skipping any whose data isn't downloaded).
Results are upserted by `engine+dataset+stage` into `data/eval_results.json`
— re-running overwrites only the matching rows, which is how the table above
stays exactly in sync with the live `GET /api/metrics` the Accuracy page
reads from.

## 4. Synthetic test-pair acceptance result

`terrawatch-test-pair/` is a hand-built 512 m × 512 m UTM scene with five
planted real changes and four planted fakes, used to check the **geo
pipeline** end-to-end (not model quality — the buildings are deliberately
cartoon-like and out of TinyCD's domain). Current result, spectral engine
forced (reproduce: upload `before.tif` + `after.tif`, Engine = "Spectral
baseline", export GeoJSON, `python check_results.py export.geojson`):

```
PIXEL SCORES (real changes)
  precision 0.73   recall 0.96   F1 0.83

PLANTED REAL CHANGES
  FOUND  R1 new_building        covered 97% | area  795 m² vs  600 (+33%) | centroid off 3.6 m
  FOUND  R2 destroyed_building  covered 69% | area  624 m² vs  625  (-0%) | centroid off 4.8 m
  FOUND  R3 flooding            covered 99% | area 3915 m² vs 3909  (+0%) | centroid off 0.2 m
  FOUND  R4 landslide_bare_soil covered 98% | area 2638 m² vs 2635  (+0%) | centroid off 0.0 m
  MISSED R5 small_shed_16m2     covered  0% (OK — below the 30 m² minimum-area floor)

PLANTED FAKE CHANGES
  F1 seasonal_vegetation  flagged  0%  -> good (rejected as vegetation_seasonal)
  F2 shadow_shift         flagged 86% -> FALSE ALARM (known limitation)
  F3 cloud                flagged 93% -> FALSE ALARM (known limitation)
```

A naive "subtract the two images" baseline scores precision 0.38 / recall
0.97 on this pair — finds everything but falls for all three fakes. The
false-alarm filter raises precision to 0.73 while recall stays at 0.96,
and correctly reclassifies F1 (seasonal vegetation) — the headline result
the filter was built for.

## 5. Known failure cases (reported, not hidden)

**F2/F3 remain false alarms on RGB-only input — a real, fundamental
limitation, not an oversight.** A simple brightness/whiteness heuristic
cannot reliably separate a bright flat cloud from a bright flat rooftop: on
this test pair, R2 (a destroyed building → bright rubble, which must stay
*kept*) and F3 (a planted cloud, which should be *rejected*) produce nearly
identical brightness+saturation signatures at the pixel level. Three fixes
were tried and rejected: percentile-based (scene-relative) thresholds,
a local-texture requirement, and morphological erosion of small bright
spots — all just traded which of the two misclassifies. The shipped
tradeoff (`CLOUD_HEURISTIC_BRIGHTNESS_PERCENTILE=99.5`,
`CLOUD_HEURISTIC_SATURATION_PERCENTILE=3.0`,
`CLOUD_OVERLAP_FRAC_THRESHOLD_HEURISTIC=0.15`) deliberately protects real
changes (R2 stays kept) at the cost of sometimes missing real clouds on
RGB-only input (F3 stays kept too). **This does not affect real Sentinel-2
input** — Wayanad uses the actual SCL atmospheric-classification band
(`CLOUD_OVERLAP_FRAC_THRESHOLD_SCL=0.4`, a far more confident signal) and
correctly rejects its cloud polygon at 97% confidence (see the main
README's results table). A reliable RGB-only fix would need an actual
cloud-detection model, not a brightness heuristic — out of scope here.

**Seasonal vegetation vs. a real landslide share ΔNDVI *and* ΔNDWI.**
McFeeters' NDWI formula `(G−NIR)/(G+NIR)` rises on plain vegetation loss
(bare soil/dead vegetation drop NIR too), not just real water, so a
seasonal color shift and a landslide can look nearly identical on index
deltas alone. The discriminator that actually holds: **texture change** — a
landslide genuinely restructures the ground; a color-only seasonal shift
doesn't (`VEGETATION_SEASONAL_TEXTURE_CEILING` in `app/config.py`). This is
exactly the failure mode Wayanad's single `vegetation_seasonal` rejection
and its one real landslide polygon were used to verify by hand.

**Engine 2's ~20% precision ceiling** on OSCD is the model's main weak
point (see `docs/MODEL_CARD.md` Limitations) — recall is deliberately
prioritized via a positive-biased sampler and class-weighted loss, which
trades away some precision that the false-alarm filter only partially
recovers. This is a known, reported tradeoff, not a bug: on a hard,
imbalanced pixel task with ~2M parameters and 14 training scenes, this is
the honest ceiling of the current model, which is why the false-alarm
filter exists as an independent second stage rather than relying on model
confidence alone.
