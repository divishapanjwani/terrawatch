"""Evaluate Engine 1 (TinyCD) against the LEVIR-CD test split.

LEVIR-CD ships as plain PNGs with no georeferencing, so this evaluates the
model directly as images — NOT through the geo pipeline (no CRS, no
alignment, no polygon vectorization). That pipeline is exercised separately
by the synthetic georeferenced test pair (see terrawatch-test-pair/).

Usage:
    source venv/bin/activate
    python scripts/evaluate.py [--dir data/levir_cd] [--limit N] [--threshold 0.5]

Writes results to data/levir_cd/eval_results.json.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engines import siamese  # noqa: E402


def load_rgb(path: Path) -> np.ndarray:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    arr = np.array(img)  # (H, W, 3)
    return np.moveaxis(arr, -1, 0)  # (3, H, W)


def load_label(path: Path) -> np.ndarray:
    from PIL import Image

    arr = np.array(Image.open(path).convert("L"))
    return arr > 127


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="data/levir_cd")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    base = Path(args.dir)
    a_dir, b_dir, label_dir = base / "A", base / "B", base / "label"
    names = sorted(p.name for p in a_dir.glob("*.png"))
    if args.limit:
        names = names[: args.limit]

    if not siamese.is_available():
        print("Engine 1 (TinyCD) weights are not available — see README for the download step.")
        sys.exit(1)

    total_tp = total_fp = total_fn = total_tn = 0
    per_image = []
    t0 = time.time()

    for i, name in enumerate(names):
        before = load_rgb(a_dir / name)
        after = load_rgb(b_dir / name)
        label = load_label(label_dir / name)

        prob = siamese.predict_arrays(before, after, "uint8")
        pred = prob >= args.threshold

        tp = int((pred & label).sum())
        fp = int((pred & ~label).sum())
        fn = int((~pred & label).sum())
        tn = int((~pred & ~label).sum())
        total_tp += tp
        total_fp += fp
        total_fn += fn
        total_tn += tn

        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_image.append({"name": name, "precision": prec, "recall": rec, "f1": f1})

        if (i + 1) % 20 == 0 or i == len(names) - 1:
            print(f"  {i + 1}/{len(names)} images...")

    elapsed = time.time() - t0

    precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (total_tp + total_tn) / (total_tp + total_tn + total_fp + total_fn)
    fpr = total_fp / (total_fp + total_tn) if total_fp + total_tn else 0.0

    results = {
        "engine": siamese.ENGINE_NAME,
        "dataset": "LEVIR-CD test split (pixel-level, as plain images)",
        "n_images": len(names),
        "threshold": args.threshold,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "false_positive_rate": fpr,
        "elapsed_seconds": elapsed,
        "per_image": per_image,
    }

    out_path = base / "eval_results.json"
    out_path.write_text(json.dumps(results, indent=2))

    print(f"\n{siamese.ENGINE_NAME} on {len(names)} LEVIR-CD test images ({elapsed:.1f}s):")
    print(f"  precision {precision:.3f}  recall {recall:.3f}  F1 {f1:.3f}  accuracy {accuracy:.3f}  FPR {fpr:.3f}")
    print(f"Results written to {out_path}")


if __name__ == "__main__":
    main()
