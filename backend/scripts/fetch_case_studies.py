"""Fetches (or re-fetches) the Sentinel-2 pairs for every non-Wayanad
Case Studies gallery entry in app/case_studies.py, and generates the
committed gallery thumbnails under frontend/public/case_studies/.

Run once (or whenever a case study's bbox/dates change):
    python scripts/fetch_case_studies.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app.case_studies import CASE_STUDIES, cached_tif_paths  # noqa: E402
from app.geo.align import load_aligned_pair  # noqa: E402
from app.geo.fetch import fetch_scene_pair  # noqa: E402
from app.geo.preview import generate_preview_pair  # noqa: E402

THUMB_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "case_studies"
THUMB_WIDTH = 480


def make_thumbnail(before_tif: Path, after_tif: Path, slug: str) -> None:
    aligned = load_aligned_pair(str(before_tif), str(after_tif))
    tmp_before = THUMB_DIR / f"_{slug}_before_tmp.png"
    tmp_after = THUMB_DIR / f"_{slug}_after_tmp.png"
    generate_preview_pair(aligned, str(tmp_before), str(tmp_after))
    img = Image.open(tmp_after).convert("RGB")
    w, h = img.size
    scale = THUMB_WIDTH / w
    img = img.resize((THUMB_WIDTH, max(1, int(h * scale))), Image.LANCZOS)
    out_path = THUMB_DIR / f"{slug}.jpg"
    img.save(out_path, "JPEG", quality=82)
    tmp_before.unlink(missing_ok=True)
    tmp_after.unlink(missing_ok=True)
    print(f"  wrote thumbnail {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")


def main():
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    for cs in CASE_STUDIES:
        slug = cs["slug"]
        print(f"=== {slug} ===")
        before_tif, after_tif = cached_tif_paths(cs)
        if cs.get("cached_tif_override"):
            print(f"  reusing existing cached pair at {cs['cached_tif_override']}")
        elif cs["bbox"] is None:
            print("  SKIPPED -- bbox not finalized yet")
            continue
        else:
            tif_dir = cs["tif_dir"]
            if before_tif.exists() and after_tif.exists():
                print(f"  already cached at {tif_dir}, skipping fetch")
            else:
                result = fetch_scene_pair(
                    cs["bbox"], cs["before_date_range"], cs["after_date_range"], cs["max_cloud"], tif_dir
                )
                print(f"  before: {result['before_scene']}")
                print(f"  after:  {result['after_scene']}")
        make_thumbnail(before_tif, after_tif, slug)


if __name__ == "__main__":
    sys.exit(main())
