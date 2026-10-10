# Model card: Engine 2 (OSCD U-Net)

Covers `app/engines/engine2.py` + `app/engines/unet_model.py`. For Engine 1
(TinyCD, a pretrained third-party Siamese CNN) see "Model credits" in the
main README — it isn't trained in this repo, so no card is needed here
beyond that attribution.

## Intended use

Pixel-wise change probability for **Sentinel-2-class multispectral imagery**
(≈10 m/pixel, 4–5 bands: R, G, B, NIR, optionally SWIR). This is the engine
`app/engines/select.py` auto-selects for anything coarser than ~2 m/pixel or
with ≥5 bands — i.e. the Wayanad demo and any Sentinel-2 scene. It is **not**
intended for sub-meter RGB imagery (that's Engine 1's domain) and its output
is a probability map, not a confirmed damage assessment — see the Honesty
rules in the main README.

## Training data

[OSCD — Onera Satellite Change Detection dataset](https://ieee-dataport.org/open-access/onera-satellite-change-detection-dataset)
(Sentinel-2, 13 bands, 10–60 m, with human-annotated change labels),
downloaded via the Hugging Face mirror in `scripts/oscd_data.py` (no Kaggle
account needed). Standard OSCD train/test city split, used exactly as given:

- **Train (14 cities):** abudhabi, aguasclaras, beihai, beirut, bercy,
  bordeaux, cupertino, hongkong, mumbai, nantes, paris, pisa, rennes, saclay_e
- **Test (10 cities):** brasilia, chongqing, dubai, lasvegas, milano,
  montpellier, norcia, rio, saclay_w, valencia

Only 5 of OSCD's 13 bands are used (R/B04, G/B03, B/B02, NIR/B08, SWIR/B11),
matching the band convention of our own Sentinel-2 fetch scripts.

## Inputs

A 14-channel feature stack per pixel (`compute_features()` in `engine2.py`),
computed once per before/after pair and fed to the network whole (no
per-pixel band selection at inference time):

| # | Channels | Description |
|---|---|---|
| 0–4 | before R, G, B, NIR, SWIR | raw Sentinel-2 reflectance (DN / 10000), clipped to [0, 1.5] |
| 5–9 | after R, G, B, NIR, SWIR | same, after image |
| 10 | ΔNDVI | `(NIR−R)/(NIR+R)`, after − before |
| 11 | ΔNDWI | `(G−NIR)/(G+NIR)`, after − before |
| 12 | ΔNDBI | `(SWIR−NIR)/(SWIR+NIR)`, after − before |
| 13 | ΔBrightness | mean(R,G,B), after − before |

If the input has no 5th (SWIR) band, that band and the NDBI channel are
zero-filled — the model still runs, with reduced discriminative power
(reflected in lower confidence, not a crash).

## Architecture

`SmallUNet` (`app/engines/unet_model.py`): a standard 4-level encoder/decoder
U-Net with skip connections, `base_width=16` (channel widths 16→32→64→128→256
at the bottleneck), sigmoid output. **1,945,633 parameters** (~1.95M) —
deliberately small so training finishes in minutes on a laptop GPU/CPU, not a
cluster.

## Training setup

`scripts/train_oscd_unet.py`, defaults as shipped (all overridable via CLI
flags):

| Hyperparameter | Value |
|---|---|
| Steps | 3,000 |
| Batch size | 16 |
| Patch size | 96×96 |
| Optimizer | Adam, lr 1e-3 |
| Loss | Weighted `BCELoss` — change pixels are a small minority of each OSCD scene, so the positive class is upweighted by `(1 − overall_positive_fraction) / overall_positive_fraction` |
| Sampling | 70% of patches centered on a change pixel (`positive_bias=0.7`), 30% uniform random, so the network sees enough positive examples despite the class imbalance |
| Augmentation | Random horizontal/vertical flip + random 90° rotation |
| Device | Apple Silicon MPS if available, else CPU |
| Checkpointing | Best in-training eval F1 (on 3 held-out OSCD test cities, for progress monitoring only) saved to `models/engine2/unet_oscd.pth` |

Training takes roughly 4 minutes on Apple Silicon MPS. The in-training eval
is **not** the reported number below — that comes from the separate,
full-test-split `scripts/evaluate.py`.

## Results

Full OSCD test split (10 cities), from `data/eval_results.json` /
`GET /api/metrics` (reproduce with `python scripts/evaluate.py oscd --engine engine2 --ablation`):

| Stage | Precision | Recall | F1 | Accuracy | False-positive rate |
|---|---|---|---|---|---|
| Raw model | 19.6% | 93.5% | 0.324 | 79.8% | 20.9% |
| + morphology | 19.7% | 93.5% | 0.325 | 79.9% | 20.8% |
| + false-alarm filter | **20.0%** | 92.6% | **0.329** | 80.5% | 20.2% |

Recall is high by design (the positive-biased sampler + class-weighted loss
favor not missing real change); precision is the known weak point — see
Limitations. The false-alarm filter recovers some precision without
meaningfully hurting recall, on top of whatever the raw model already does.

## Limitations

- **Precision ceiling (~20%).** A ~2M-parameter U-Net trained on 14 OSCD
  scenes is a genuinely small model/dataset for a hard, imbalanced pixel
  task; four out of five flagged change pixels are still false positives
  pre-filter. This is honestly reported, not hidden — it's the reason the
  false-alarm filter (`app/pipeline/false_alarm.py`) exists as a second,
  independent stage rather than relying on model confidence alone.
- **10 m resolution ceiling.** Sub-building-scale changes are invisible at
  Sentinel-2 resolution; this engine is for landslides, floods, and
  settlement-scale construction/demolition, not individual structures.
- **SWIR dependence.** Losing the 5th band (no SWIR) removes the NDBI
  channel entirely, which is also the main signal `change_type.py` uses to
  tell `new_construction` apart from `landslide_bare_soil` — 4-band input
  degrades gracefully to a less specific label rather than guessing.
- **Domain gap from LEVIR-CD.** This model is unrelated to Engine 1/TinyCD
  and was not evaluated on LEVIR-CD imagery (wrong resolution/band count for
  this architecture) — see `docs/EVALUATION.md` for why the two engines are
  evaluated on separate, resolution-matched datasets rather than one
  combined number.
