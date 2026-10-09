"""Evaluate detection engines against their held-out test splits.

- TinyCD (Engine 1) on the official LEVIR-CD test split.
- Engine 2 (U-Net/OSCD) and the spectral baseline on the OSCD test split.

Both datasets ship as plain images with no georeferencing, so this
evaluates pixel-level precision/recall/F1/FPR directly — NOT through the
geo pipeline (no CRS, no alignment, no polygon vectorization). That
pipeline is exercised separately by terrawatch-test-pair/.

Usage:
    source venv/bin/activate
    python scripts/evaluate.py levircd [--dir data/levir_cd] [--limit N] [--threshold 0.5] [--ablation]
    python scripts/evaluate.py oscd --engine engine2 [--dir data/oscd_raw] [--limit N] [--threshold 0.5] [--ablation]
    python scripts/evaluate.py oscd --engine spectral [--dir data/oscd_raw] [--limit N] [--threshold 0.5] [--ablation]

--ablation runs three stages per image (raw model -> +morphology ->
+false-alarm filter) instead of one, so you can see how much each stage
actually helps/hurts precision and recall.

Results are upserted (by engine+dataset+stage) into data/eval_results.json,
read by GET /api/metrics and the frontend Accuracy page.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engines import siamese, engine2, spectral  # noqa: E402
from app.pipeline.ablation import ablation_masks  # noqa: E402

RESULTS_PATH = Path(__file__).resolve().parent.parent / "data" / "eval_results.json"
ABLATION_STAGES = ["raw", "morphology", "false_alarm_filter"]
STAGE_LABELS = {"raw": "raw model", "morphology": "+ morphology", "false_alarm_filter": "+ false-alarm filter"}


def load_rgb(path: Path) -> np.ndarray:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    return np.moveaxis(np.array(img), -1, 0)  # (3, H, W)


def load_label(path: Path) -> np.ndarray:
    from PIL import Image

    return np.array(Image.open(path).convert("L")) > 127


def pixel_metrics(pred: np.ndarray, label: np.ndarray) -> dict:
    tp = int((pred & label).sum())
    fp = int((pred & ~label).sum())
    fn = int((~pred & label).sum())
    tn = int((~pred & ~label).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1}


def _upsert_result(record: dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results = []
    if RESULTS_PATH.exists():
        results = json.loads(RESULTS_PATH.read_text()).get("results", [])
    stage = record.get("stage", "full")
    results = [
        r for r in results
        if not (r["engine"] == record["engine"] and r["dataset"] == record["dataset"] and r.get("stage", "full") == stage)
    ]
    results.append(record)
    RESULTS_PATH.write_text(json.dumps({"results": results}, indent=2))


def _aggregate(per_image_metrics: list[dict]) -> dict:
    total_tp = sum(m["tp"] for m in per_image_metrics)
    total_fp = sum(m["fp"] for m in per_image_metrics)
    total_fn = sum(m["fn"] for m in per_image_metrics)
    total_tn = sum(m["tn"] for m in per_image_metrics)
    precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (total_tp + total_tn) / max(1, total_tp + total_tn + total_fp + total_fn)
    fpr = total_fp / (total_fp + total_tn) if total_fp + total_tn else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "accuracy": accuracy, "false_positive_rate": fpr}


LEVIRCD_PIXEL_SIZE_M = 0.5


def run_levircd(args) -> None:
    base = Path(args.dir)
    a_dir, b_dir, label_dir = base / "A", base / "B", base / "label"
    if not a_dir.exists():
        print(f"LEVIR-CD test split not found at {base}. See HANDOFF.md for the download step.")
        sys.exit(1)
    names = sorted(p.name for p in a_dir.glob("*.png"))
    if args.limit:
        names = names[: args.limit]
    if not siamese.is_available():
        print("Engine 1 (TinyCD) weights are not available — see HANDOFF.md for the download step.")
        sys.exit(1)

    stages = ABLATION_STAGES if args.ablation else ["full"]
    per_image = {s: [] for s in stages}
    t0 = time.time()
    for i, name in enumerate(names):
        before, after, label = load_rgb(a_dir / name), load_rgb(b_dir / name), load_label(label_dir / name)
        prob = siamese.predict_arrays(before, after, "uint8")
        if args.ablation:
            masks = ablation_masks(prob, before, after, args.threshold, LEVIRCD_PIXEL_SIZE_M)
            for s in stages:
                m = pixel_metrics(masks[s], label)
                m["name"] = name
                per_image[s].append(m)
        else:
            pred = prob >= args.threshold
            m = pixel_metrics(pred, label)
            m["name"] = name
            per_image["full"].append(m)
        if (i + 1) % 20 == 0 or i == len(names) - 1:
            print(f"  {i + 1}/{len(names)} images...")
    elapsed = time.time() - t0

    for s in stages:
        agg = _aggregate(per_image[s])
        record = {
            "engine": siamese.ENGINE_NAME,
            "dataset": "LEVIR-CD test split",
            "stage": s,
            "n_images": len(names),
            "threshold": args.threshold,
            "elapsed_seconds": elapsed,
            **agg,
        }
        _upsert_result(record)
        label_str = STAGE_LABELS.get(s, s)
        print(f"{siamese.ENGINE_NAME} [{label_str}] on {len(names)} LEVIR-CD test images:")
        print(f"  precision {agg['precision']:.3f}  recall {agg['recall']:.3f}  F1 {agg['f1']:.3f}  "
              f"accuracy {agg['accuracy']:.3f}  FPR {agg['false_positive_rate']:.3f}")
    print(f"\n({elapsed:.1f}s total) Results written to {RESULTS_PATH}")


OSCD_PIXEL_SIZE_M = 10.0  # Sentinel-2 10m bands (R,G,B,NIR); see scripts/oscd_data.py


def run_oscd(args) -> None:
    from scripts.oscd_data import load_oscd_test_pairs  # local import, see that module for format notes

    base = Path(args.dir)
    pairs = load_oscd_test_pairs(base, limit=args.limit)
    if not pairs:
        print(f"No OSCD test pairs found at {base}. See HANDOFF.md for the download step.")
        sys.exit(1)

    engine_module = {"engine2": engine2, "spectral": spectral}[args.engine]
    if args.engine == "engine2" and not engine2.is_available():
        print("Engine 2 weights are not available — see HANDOFF.md for the training/download step.")
        sys.exit(1)

    stages = ABLATION_STAGES if args.ablation else ["full"]
    per_image = {s: [] for s in stages}
    t0 = time.time()
    for i, (before, after, label, name) in enumerate(pairs):
        if args.engine == "engine2":
            prob = engine2.predict_arrays(before, after)
        else:
            prob = spectral.predict_arrays(before, after)
        if args.ablation:
            masks = ablation_masks(prob, before, after, args.threshold, OSCD_PIXEL_SIZE_M)
            for s in stages:
                m = pixel_metrics(masks[s], label)
                m["name"] = name
                per_image[s].append(m)
        else:
            pred = prob >= args.threshold
            m = pixel_metrics(pred, label)
            m["name"] = name
            per_image["full"].append(m)
        if (i + 1) % 10 == 0 or i == len(pairs) - 1:
            print(f"  {i + 1}/{len(pairs)} pairs...")
    elapsed = time.time() - t0

    for s in stages:
        agg = _aggregate(per_image[s])
        record = {
            "engine": engine_module.ENGINE_NAME,
            "dataset": "OSCD test split",
            "stage": s,
            "n_images": len(pairs),
            "threshold": args.threshold,
            "elapsed_seconds": elapsed,
            **agg,
        }
        _upsert_result(record)
        label_str = STAGE_LABELS.get(s, s)
        print(f"{engine_module.ENGINE_NAME} [{label_str}] on {len(pairs)} OSCD test pairs:")
        print(f"  precision {agg['precision']:.3f}  recall {agg['recall']:.3f}  F1 {agg['f1']:.3f}  "
              f"accuracy {agg['accuracy']:.3f}  FPR {agg['false_positive_rate']:.3f}")
    print(f"\n({elapsed:.1f}s total) Results written to {RESULTS_PATH}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_levir = sub.add_parser("levircd", help="Evaluate TinyCD on the LEVIR-CD test split")
    p_levir.add_argument("--dir", default="data/levir_cd")
    p_levir.add_argument("--limit", type=int, default=None)
    p_levir.add_argument("--threshold", type=float, default=0.5)
    p_levir.add_argument("--ablation", action="store_true", help="raw -> +morphology -> +false-alarm filter")
    p_levir.set_defaults(func=run_levircd)

    p_oscd = sub.add_parser("oscd", help="Evaluate Engine 2 or the spectral baseline on the OSCD test split")
    p_oscd.add_argument("--engine", choices=["engine2", "spectral"], required=True)
    p_oscd.add_argument("--dir", default="data/oscd_raw")
    p_oscd.add_argument("--limit", type=int, default=None)
    p_oscd.add_argument("--threshold", type=float, default=0.5)
    p_oscd.add_argument("--ablation", action="store_true", help="raw -> +morphology -> +false-alarm filter")
    p_oscd.set_defaults(func=run_oscd)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
