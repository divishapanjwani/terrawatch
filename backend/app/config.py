"""Tunable pipeline defaults. Kept in one place so the UI can display the
exact values used (e.g. the severity formula tooltip) and so they're easy
to change without hunting through the pipeline code."""

from pathlib import Path

# Binary threshold applied to the engine's change-probability map.
DETECTION_THRESHOLD = 0.5

# Morphological opening/closing structuring element radius, in pixels.
# (Minimum-area removal happens later, in the false-alarm filter, as an
# explicit "too_small" rejection reason rather than silently vanishing.)
MORPH_RADIUS_PX = 1

# Polygon simplification tolerance, in meters (native projected CRS).
SIMPLIFY_TOLERANCE_M = 1.0

# Severity tiers: sev_score = max(norm(log1p(area_m2)), norm(log1p(change_magnitude)))
# -- see app/pipeline/severity.py for the full rationale.
SEVERITY_HIGH = 0.66
SEVERITY_MEDIUM = 0.33

PROGRESS_STEPS = [
    "validating",
    "quality_check",
    "detecting",
    "filtering",
    "vectorizing",
    "impact_analysis",
    "done",
]

# "fetching" only appears in progress_steps for analyses started via
# POST /api/analyses/fetch (place/bbox auto-fetch) -- it runs before
# "validating" since there's nothing to validate until the scenes land.
FETCH_PROGRESS_STEPS = ["fetching"] + PROGRESS_STEPS

# ---------------------------------------------------------------------------
# Auto-fetch (app/geo/fetch.py) -- place name or drawn bbox -> Sentinel-2 L2A
# ---------------------------------------------------------------------------
FETCH_DEFAULT_BBOX_HALF_SIZE_DEG = 0.03  # ~6-7 km square, matches the Wayanad demo's scale
FETCH_DEFAULT_MAX_CLOUD = 20.0
NOMINATIM_MIN_INTERVAL_S = 1.0  # Nominatim usage policy: max 1 request/second

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

# Loose landslide path: bare soil/rock/debris exposed by a real landslide
# can raise NDBI into new-construction range (a known remote-sensing
# confusion -- SWIR/NIR ratio doesn't cleanly separate "bare ground" from
# "built-up"; see Gotcha #11 in HANDOFF.md) and the NDVI drop can land
# short of LANDSLIDE_NDVI_THRESHOLD if some ground cover remains amid the
# debris. Verified against the real Wayanad landslide polygon (ΔNDVI
# -0.13, ΔNDBI +0.085, texture_change_frac 0.47, 1.56M m²), which the
# strict rule above misses and new_construction's looser ΔNDBI-only check
# then wrongly claims. The tell that actually holds here: genuine ground
# restructuring (high texture_change_frac) across a large contiguous
# area -- a freshly built structure is small and local, never a sprawling
# high-texture scar -- so this path requires BOTH, at a much larger area
# floor than the strict rule, to stay a high-confidence signal rather
# than a construction-detector loophole.
LANDSLIDE_NDVI_LOOSE_THRESHOLD = -0.10
LANDSLIDE_NDBI_LOOSE_CEILING = 0.10
LANDSLIDE_TEXTURE_FLOOR = 0.35
LANDSLIDE_LARGE_AREA_M2 = 50000.0

# A real new-construction footprint (a building, a cluster of buildings)
# is small and local -- it never legitimately spans this much contiguous
# area in one polygon. Above this, a ΔNDBI-only signal is more likely
# bare soil/debris (see LANDSLIDE_* loose path above) than construction.
NEW_CONSTRUCTION_MAX_AREA_M2 = 50000.0

VEGETATION_LOSS_NDVI_THRESHOLD = -0.08

# ---------------------------------------------------------------------------
# Impact: OSM facilities + priority score (KEPT polygons only, Disaster mode)
# app/impact/facilities.py, app/pipeline/priority.py
# ---------------------------------------------------------------------------

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_TIMEOUT_S = 25

# Degrees added around the analysis bbox before querying OSM for hospitals/
# clinics/schools -- a small rural scene often has none inside its own tight
# bbox, but a real nearest hospital a few km outside it. ~0.15 deg ~ 16 km.
OSM_FACILITY_BUFFER_DEG = 0.15

# priority_score = w_severity * sev_score + w_confidence * confidence
#                 + w_hospital * closeness(nearest_hospital_m)
#                 + w_school * closeness(nearest_school_m)
# closeness(d) = clamp(1 - d / PRIORITY_PROXIMITY_MAX_M, 0, 1): 1.0 right next
# to a facility, 0 at or beyond PRIORITY_PROXIMITY_MAX_M.
PRIORITY_PROXIMITY_MAX_M = 2000.0

# ---------------------------------------------------------------------------
# Population (app/impact/population.py) -- WorldPop raster, India-wide,
# covers both demo scenes. Gitignored; see scripts/download_population.py.
# ---------------------------------------------------------------------------
POPULATION_RASTER_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "population" / "ind_ppp_2020_1km_Aggregated_UNadj.tif"
)
POPULATION_BUFFER_M = 250.0

# ---------------------------------------------------------------------------
# OSM roads + shelters (app/impact/facilities.py)
# ---------------------------------------------------------------------------

# Main road classes queried alongside hospitals/clinics/schools/shelters.
OSM_MAIN_ROAD_HIGHWAY_TYPES = ["motorway", "trunk", "primary", "secondary"]

# Radius for the "nearby facilities" list shown in polygon details.
FACILITY_LIST_MAX_DISTANCE_M = 1000.0
FACILITY_LIST_MAX_ITEMS = 5

# ---------------------------------------------------------------------------
# Priority score v2 (app/pipeline/priority.py) -- full Phase 5 formula:
# priority = w1*sev_score + w2*norm(population_est) + w3*facility_proximity
#            + w4*confidence + w5*route_impact_score
# facility_proximity = closer of hospital/school closeness (see
# PRIORITY_PROXIMITY_MAX_M above). route_impact_score (Round 3, app/impact/
# routes.py): none=0.0, unknown=0.0 (no signal either way), detour=0.6,
# no_alternative=1.0 -- a confirmed-unreachable hospital route outweighs a
# mere detour. Editable via scripts/settings -- see app/settings.py; these
# are the defaults for new analyses. Rebalanced from the Phase 5 weights
# (0.35/0.25/0.2/0.2/0.0) to make room for a real w5 while keeping the
# relative order severity > population > facility/confidence > route.
# ---------------------------------------------------------------------------
PRIORITY_W1_SEVERITY = 0.30
PRIORITY_W2_POPULATION = 0.20
PRIORITY_W3_FACILITY_PROXIMITY = 0.15
PRIORITY_W4_CONFIDENCE = 0.15
PRIORITY_W5_ROUTE_IMPACT = 0.20

# ---------------------------------------------------------------------------
# Blocked-route checker (app/impact/routes.py) -- osmnx drive-network graph,
# cached to disk like facilities (same buffer, same catchment a hospital
# trip would realistically use).
# ---------------------------------------------------------------------------
ROUTE_GRAPH_BUFFER_DEG = OSM_FACILITY_BUFFER_DEG
ROUTE_IMPACT_SCORE = {"none": 0.0, "unknown": 0.0, "detour": 0.6, "no_alternative": 1.0}
ROUTE_BLOCKAGE_WORDING = "possible blockage — verify on ground"

# ---------------------------------------------------------------------------
# Prevention mode: hazard zones (app/pipeline/priority.py, app/api/analyses.py)
# ---------------------------------------------------------------------------
HAZARD_ZONE_WORDING = "New structure detected in hazard zone — verify"

# ---------------------------------------------------------------------------
# Quality safeguard (app/pipeline/run.py): one candidate polygon covering an
# implausibly large share of the whole scene is more likely a systematic
# radiometric mismatch between the before/after dates (e.g. an uncorrected
# Sentinel-2 processing-baseline offset -- see scripts/sentinel2_fetch.py's
# needs_boa_offset_correction) than one real contiguous change. Flagged as a
# quality-report warning, not silently presented as a normal detection.
# ---------------------------------------------------------------------------
RADIOMETRIC_MISMATCH_AREA_FRACTION = 0.25
RADIOMETRIC_MISMATCH_WARNING = "possible radiometric mismatch between dates — check imagery"
