# TerraWatch test pair — planted changes with an answer key

A synthetic 512 m × 512 m scene near Pune (1 m/pixel, EPSG:32643 / UTM 43N) where every change is planted on purpose, so you know exactly what the system *should* find.

`preview_before_after_answers.png` shows before | after | answers (red = real change, grey = fake change, dark grey = ignored shadow of a changed building).

## Files to upload

| File | Use |
|---|---|
| `before.tif` + `after.tif` | Main test. 4 bands: Red, Green, Blue, NIR (uint8). |
| `before_rgb.tif` + `after_rgb.tif` | Same scene, RGB only — use if your upload expects 3 bands. |
| `before.tif` + `after_misaligned_3px.tif` | After image shifted 3 m east. Should trigger the alignment warning (Phase 4). |

## What the system should find

**Real changes (should be detected)**

| ID | What | True area |
|---|---|---|
| R1 | New building (20 × 30 m) | 600 m² |
| R2 | Destroyed building → rubble | 625 m² |
| R3 | Flooding over grassland | 3,909 m² |
| R4 | Landslide / bare-soil strip | 2,635 m² |
| R5 | Tiny shed (4 × 4 m) | 16 m² — fine to drop if your minimum-area filter is above 16 m² |

**Fake changes (should NOT end up as real changes)**

| ID | What | Should be rejected as |
|---|---|---|
| F1 | Crop field turns green → brown | seasonal vegetation |
| F2 | Building shadows flip direction | shadow / sun angle |
| F3 | Small soft cloud in after image | cloud |
| F4 | Whole after image ~6% brighter + noise | should not trigger anywhere |

Exact centroids (lat/lon) and polygon shapes are in `answer_key.geojson` / `answer_key.json`.

## How to check your results

1. Upload `before.tif` + `after.tif` in TerraWatch and run the analysis.
2. Export the result as GeoJSON (or GeoPackage).
3. Run:
   ```
   pip install rasterio shapely numpy
   python check_results.py path/to/your_export.geojson
   ```
4. It prints precision / recall / F1, which planted changes were found or missed, your area vs the true area, how far off each centroid is, and whether each fake change was wrongly flagged.

### What good looks like

- **After Phase 2:** R1–R4 FOUND, areas within roughly ±15%, centroids within a few metres. Fakes F1–F3 may still be flagged — that's expected before the false-alarm filter.
- **After Phase 4:** F1–F3 should show "good" (0–10% flagged) and appear in the export as `status: rejected` with the right reason. Precision should rise clearly while recall stays high.

For reference, a naive "subtract the two images" detector scores precision 0.38 / recall 0.97 on this pair — it finds everything but falls for all three fakes. Beating that is your demo moment.

### Important limits

- This pair is synthetic. It is great for checking the **geo pipeline** (polygons, m² areas, centroids, severity, export, false-alarm filter) because the answers are exact.
- A model trained on real LEVIR-CD photos may not recognise these cartoon-like buildings well. Check **model quality** on the LEVIR-CD test split instead, and test on at least one real georeferenced pair before the demo.

`make_test_pair.py` regenerates everything.
