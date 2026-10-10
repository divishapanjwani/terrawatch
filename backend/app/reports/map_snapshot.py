"""A static map snapshot for the field report: the after-image preview
PNG with kept-polygon outlines drawn on top, colored by severity --
matches the same severity palette the live map/UI use
(frontend/src/styles/tokens.css: High #E5484D, Medium #F5A524, Low
#F2D45C), so the PDF/HTML report looks like a still frame of the app,
not a separately-invented graphic.
"""

from pathlib import Path

from PIL import Image, ImageDraw

SEVERITY_COLOR = {
    "High": (229, 72, 77),
    "Medium": (245, 165, 36),
    "Low": (242, 212, 92),
}
DEFAULT_COLOR = (143, 163, 168)


def _lonlat_to_px(lon: float, lat: float, bounds: dict, width: int, height: int) -> tuple:
    x = (lon - bounds["west"]) / (bounds["east"] - bounds["west"]) * width
    y = (bounds["north"] - lat) / (bounds["north"] - bounds["south"]) * height
    return x, y


def _rings(geom: dict) -> list:
    if geom["type"] == "Polygon":
        return geom["coordinates"]
    if geom["type"] == "MultiPolygon":
        return [ring for poly in geom["coordinates"] for ring in poly]
    return []


def generate_map_snapshot(after_png_path: str, bounds: dict, kept_features: list, out_path: str) -> None:
    """kept_features: GeoJSON Feature dicts (EPSG:4326) with
    properties.severity, for status == "kept" only."""
    img = Image.open(after_png_path).convert("RGB")
    width, height = img.size
    draw = ImageDraw.Draw(img)

    for feat in kept_features:
        color = SEVERITY_COLOR.get(feat["properties"].get("severity"), DEFAULT_COLOR)
        for ring in _rings(feat["geometry"]):
            pts = [_lonlat_to_px(lon, lat, bounds, width, height) for lon, lat in ring]
            if len(pts) >= 2:
                draw.line(pts + [pts[0]], fill=color, width=2)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
