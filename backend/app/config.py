"""Tunable pipeline defaults. Kept in one place so the UI can display the
exact values used (e.g. the severity formula tooltip) and so they're easy
to change without hunting through the pipeline code."""

# Binary threshold applied to the engine's change-probability map.
DETECTION_THRESHOLD = 0.5

# Morphological opening/closing structuring element radius, in pixels.
MORPH_RADIUS_PX = 1

# Polygons smaller than this (in m^2) are dropped as noise.
MIN_AREA_M2 = 30.0

# Polygon simplification tolerance, in meters (native projected CRS).
SIMPLIFY_TOLERANCE_M = 1.0

# Severity tiers: sev_score = 0.5 * norm(area_m2) + 0.5 * norm(change_magnitude)
SEVERITY_HIGH = 0.66
SEVERITY_MEDIUM = 0.33

PROGRESS_STEPS = ["validating", "detecting", "filtering", "vectorizing", "done"]
