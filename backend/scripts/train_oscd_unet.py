"""Train Engine 2 (SmallUNet) on OSCD.

Loads all 14 OSCD train-split cities into memory (small dataset — full
13-band scenes are ~600x600, we use 5 bands), trains on random patches
with light augmentation and a positive-class-aware sampler (OSCD change
pixels are a small minority), and saves weights to models/engine2/.

Usage:
    source venv/bin/activate
    python scripts/train_oscd_unet.py [--steps 3000] [--batch-size 16] [--patch-size 96]

Requires OSCD downloaded first — see HANDOFF.md.
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.oscd_data import TRAIN_CITIES, TEST_CITIES, load_oscd_city, available  # noqa: E402
from app.engines.engine2 import compute_features, IN_CHANNELS, BASE_WIDTH, WEIGHTS_PATH  # noqa: E402
from app.engines.unet_model import SmallUNet, count_params  # noqa: E402


def pick_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_scenes(base_dir: Path, cities: list[str], split: str):
    scenes = []
    for city in cities:
        before, after, label = load_oscd_city(base_dir, city, split)
        features = compute_features(before, after)  # (14, H, W)
        scenes.append({"city": city, "features": features, "label": label.astype(np.float32)})
        print(f"  loaded {city}: {features.shape[1]}x{features.shape[2]}, "
              f"{label.mean() * 100:.2f}% change pixels")
    return scenes


def sample_patch(scenes, patch_size: int, positive_bias: float, rng: np.random.Generator):
    scene = scenes[rng.integers(len(scenes))]
    feats, label = scene["features"], scene["label"]
    _, h, w = feats.shape
    ph = pw = patch_size
    if h < ph or w < pw:
        ph, pw = min(h, ph), min(w, pw)

    if rng.random() < positive_bias and label.sum() > 0:
        ys, xs = np.nonzero(label)
        idx = rng.integers(len(ys))
        cy, cx = ys[idx], xs[idx]
        y0 = int(np.clip(cy - ph // 2, 0, h - ph))
        x0 = int(np.clip(cx - pw // 2, 0, w - pw))
    else:
        y0 = int(rng.integers(0, h - ph + 1))
        x0 = int(rng.integers(0, w - pw + 1))

    f_patch = feats[:, y0 : y0 + ph, x0 : x0 + pw]
    l_patch = label[y0 : y0 + ph, x0 : x0 + pw]

    # augmentation: random flips / 90-degree rotations
    if rng.random() < 0.5:
        f_patch = f_patch[:, :, ::-1]
        l_patch = l_patch[:, ::-1]
    if rng.random() < 0.5:
        f_patch = f_patch[:, ::-1, :]
        l_patch = l_patch[::-1, :]
    k = rng.integers(4)
    if k:
        f_patch = np.rot90(f_patch, k, axes=(1, 2))
        l_patch = np.rot90(l_patch, k, axes=(0, 1))

    return np.ascontiguousarray(f_patch), np.ascontiguousarray(l_patch)


def make_batch(scenes, batch_size, patch_size, positive_bias, rng):
    fs, ls = [], []
    for _ in range(batch_size):
        f, l = sample_patch(scenes, patch_size, positive_bias, rng)
        fs.append(f)
        ls.append(l)
    return np.stack(fs), np.stack(ls)


def evaluate_quick(model, scenes, device, threshold=0.5):
    """Whole-scene inference on a handful of held-out scenes, for progress
    monitoring during training (NOT the final scripts/evaluate.py number)."""
    model.eval()
    tp = fp = fn = 0
    with torch.no_grad():
        for scene in scenes:
            feats = scene["features"]
            _, h, w = feats.shape
            pad_h, pad_w = (-h) % 16, (-w) % 16
            fp_arr = np.pad(feats, ((0, 0), (0, pad_h), (0, pad_w)), mode="reflect")
            x = torch.from_numpy(fp_arr).unsqueeze(0).float().to(device)
            prob = model(x).squeeze(0).squeeze(0).cpu().numpy()[:h, :w]
            pred = prob >= threshold
            label = scene["label"] > 0.5
            tp += int((pred & label).sum())
            fp += int((pred & ~label).sum())
            fn += int((~pred & label).sum())
    model.train()
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="data/oscd_raw")
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--patch-size", type=int, default=96)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--positive-bias", type=float, default=0.7,
                         help="fraction of patches sampled centered on a change pixel")
    parser.add_argument("--eval-every", type=int, default=500)
    parser.add_argument("--eval-cities", type=int, default=3,
                         help="how many OSCD test cities to use for in-training progress checks")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    base_dir = Path(args.dir)
    if not available(base_dir):
        print(f"OSCD not found at {base_dir}. See HANDOFF.md for the download step.")
        sys.exit(1)

    device = pick_device()
    print(f"Device: {device}")

    print("Loading OSCD train cities...")
    train_scenes = load_scenes(base_dir, TRAIN_CITIES, "train")
    print("Loading a few OSCD test cities for in-training progress checks...")
    eval_scenes = load_scenes(base_dir, TEST_CITIES[: args.eval_cities], "test")

    model = SmallUNet(in_channels=IN_CHANNELS, base_width=BASE_WIDTH).to(device)
    print(f"Model params: {count_params(model):,}")

    # OSCD change pixels are a small minority of each scene; weight the
    # positive class in the loss in addition to the positive-biased sampler.
    overall_pos_frac = np.mean([s["label"].mean() for s in train_scenes])
    pos_weight = torch.tensor([(1 - overall_pos_frac) / max(overall_pos_frac, 1e-3)], device=device)
    print(f"Overall positive pixel fraction: {overall_pos_frac:.4f}  pos_weight: {pos_weight.item():.2f}")

    criterion = nn.BCELoss(reduction="none")
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    rng = np.random.default_rng(args.seed)

    best_f1 = -1.0
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    for step in range(1, args.steps + 1):
        feats, labels = make_batch(train_scenes, args.batch_size, args.patch_size, args.positive_bias, rng)
        x = torch.from_numpy(feats).float().to(device)
        y = torch.from_numpy(labels).float().to(device).unsqueeze(1)

        pred = model(x)
        weight = 1.0 + y * (pos_weight - 1.0)  # weight=pos_weight where y=1, weight=1 where y=0
        loss = (criterion(pred, y) * weight).mean()

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if step % 100 == 0:
            print(f"  step {step}/{args.steps}  loss {loss.item():.4f}  ({time.time() - t0:.0f}s)")

        if step % args.eval_every == 0 or step == args.steps:
            precision, recall, f1 = evaluate_quick(model, eval_scenes, device)
            print(f"  [eval @ step {step}] precision {precision:.3f}  recall {recall:.3f}  F1 {f1:.3f}")
            if f1 > best_f1:
                best_f1 = f1
                torch.save(model.state_dict(), str(WEIGHTS_PATH))
                print(f"  -> saved new best (F1 {f1:.3f}) to {WEIGHTS_PATH}")

    elapsed = time.time() - t0
    print(f"\nTraining done in {elapsed:.0f}s. Best in-training eval F1: {best_f1:.3f}")
    print(f"Weights saved to {WEIGHTS_PATH}")
    print("Run `python scripts/evaluate.py oscd --engine engine2` for the real held-out numbers.")


if __name__ == "__main__":
    main()
