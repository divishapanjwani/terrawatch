"""Tunable pipeline defaults. Kept in one place so the UI can display the
exact values used (e.g. the severity formula tooltip) and so they're easy
to change without hunting through the pipeline code."""

# Binary threshold applied to the engine's change-probability map.
DETECTION_THRESHOLD = 0.5

# Morphological opening/closing structuring element radius, in pixels.
# (Minimum-area removal happens later, in the false-alarm filter, as an
# explicit "too_small" rejection reason rather than silently vanishing.)
MORPH_RADIUS_PX = 1

# Polygon simplification tolerance, in meters (native projected CRS).
SIMPLIFY_TOLERANCE_M = 1.0

# Severity tiers: sev_score = 0.5 * norm(area_m2) + 0.5 * norm(change_magnitude)
SEVERITY_HIGH = 0.66
SEVERITY_MEDIUM = 0.33

PROGRESS_STEPS = ["validating", "quality_check", "detecting", "filtering", "vectorizing", "done"]

# ---------------------------------------------------------------------------
# Quality check (app/geo/quality.py)
# ---------------------------------------------------------------------------

# Phase-correlation shift above this many pixels triggers a misalignment warning.
MISALIGNMENT_WARNING_PX = 1.0

# Cloud-cover percentage (per image) above this triggers a quiet amber warning.
CLOUD_WARNING_PCT = 20.0

# RGB-brightness/whiteness cloud heuristic (used when no SCL band is present):
# a pixel counts as cloud-like if its brightness is above this percentile of
# the image AND its color saturation (max-min channel spread, as a fraction
# of its brightness) is below this percentile of the image's own saturation
# distribution -- bright AND flat-colored RELATIVE TO THIS SCENE. Both are
# percentiles (not absolute values) because raw reflectance/DN scale varies
# wildly between uint8 RGB and uint16 Sentinel-2 input. Bright rubble/
# concrete can still partially pass this (it's genuinely bright and fairly
# flat-colored) -- CLOUD_OVERLAP_FRAC_THRESHOLD below requires a polygon to
# be MOSTLY cloud-like, not just partially, to actually get rejected.
CLOUD_HEURISTIC_BRIGHTNESS_PERCENTILE = 99.5
CLOUD_HEURISTIC_SATURATION_PERCENTILE = 3.0

# Sentinel-2 SCL (Scene Classification Layer) class codes treated as cloud
# when a 6th (SCL) band is present -- see scripts/sentinel2_fetch.py.
SCL_CLOUD_CLASSES = (8, 9, 10)  # cloud medium probability, high probability, thin cirrus

# ---------------------------------------------------------------------------
# False-alarm filter (app/pipeline/false_alarm.py)
# ---------------------------------------------------------------------------

# A candidate polygon is rejected as "too_small" below this area.
TOO_SMALL_AREA_M2 = 30.0

# Fraction of a polygon's pixels overlapping a cloud mask (in EITHER image)
# above which it's rejected as "cloud". Two thresholds because the two
# cloud-detection methods have very different reliability: Sentinel-2's own
# SCL classification is a clean, confident per-pixel label, so a lower bar
# is fine. The RGB brightness/whiteness heuristic is fuzzy and -- as we
# found testing against terrawatch-test-pair -- partially fires on bright
# flat surfaces that aren't clouds at all (a white building rooftop looks
# a lot like a cloud to a simple brightness+saturation rule), so it needs a
# much more conservative bar to avoid rejecting real changes.
CLOUD_OVERLAP_FRAC_THRESHOLD_SCL = 0.4
CLOUD_OVERLAP_FRAC_THRESHOLD_HEURISTIC = 0.15

# Fraction of a polygon's pixels adjacent to the invalid/no-data boundary
# above which it's rejected as "misalignment_edge".
EDGE_TOUCH_FRAC_THRESHOLD = 0.5
EDGE_BUFFER_PX = 2

# vegetation_seasonal: |mean ΔNDVI| above this, with built-up (ΔNDBI) low
# and local texture/structure barely changed -- a uniform color shift
# across the same scene content, not a real structural change. Texture is
# the key discriminator from landslide_bare_soil: both share a large ΔNDVI
# (vegetation loss) and, as a side effect of the NDWI formula, a
# non-trivial ΔNDWI even with no real water -- but a landslide genuinely
# changes the ground's structure (debris, exposed terrain) while a
# seasonal color shift doesn't, which shows up clearly in texture_change_frac.
VEGETATION_SEASONAL_NDVI_THRESHOLD = 0.12
VEGETATION_SEASONAL_NDBI_CEILING = 0.08
VEGETATION_SEASONAL_NDWI_CEILING = 0.50
VEGETATION_SEASONAL_TEXTURE_CEILING = 0.30

# shadow_illumination: brightness changed by more than this fraction of the
# scene's overall dynamic range, while local texture (edge/gradient
# structure) changed by less than this fraction -- same objects, different
# lighting, not a structural change.
SHADOW_BRIGHTNESS_FRAC_THRESHOLD = 0.15
SHADOW_TEXTURE_FRAC_THRESHOLD = 0.30

# Mean in-polygon model probability below this -> needs_review.
CONFIDENCE_NEEDS_REVIEW_THRESHOLD = 0.6

# ---------------------------------------------------------------------------
# Change type (app/pipeline/change_type.py) -- applies to KEPT polygons only
# ---------------------------------------------------------------------------

# Above this AND the landslide/vegetation-loss NDWI side-effect (see
# vegetation_seasonal above) -- set comfortably above the ~0.25-0.3 NDWI
# bump that vegetation loss alone can cause, so only genuine water signals
# (observed ~0.5+ on a real flood) trigger this.
FLOODING_NDWI_THRESHOLD = 0.35
NEW_CONSTRUCTION_NDBI_THRESHOLD = 0.08
STRUCTURE_LOST_NDBI_THRESHOLD = -0.08
LANDSLIDE_NDVI_THRESHOLD = -0.15
LANDSLIDE_NDBI_CEILING = 0.05
LANDSLIDE_MIN_AREA_M2 = 500.0
VEGETATION_LOSS_NDVI_THRESHOLD = -0.08
