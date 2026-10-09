# TerraWatch — Claude Code prompts for Phases 3 to 8

Paste one phase at a time, each in a **fresh Claude Code session**, after the previous phase has been merged into `main`.

**Order and who can work in parallel**
- Phase 3 → must be merged first (everything later depends on working detection on real data).
- Phase 4 and Phase 6 can run **in parallel** on two machines (Phase 4 = detection/filter logic, Phase 6 = fetching + demo data; they touch different files).
- Phase 5 after Phase 4 is merged.
- Phase 7 after Phase 5. Phase 8 last.
- If time runs short, the priority is: 3 → 4 → 5 → 6. Phases 7 and 8 are extras; do the parts you can.

**Before every phase, on your machine:**
```
git checkout main
git pull
```

---

## Phase 3 — Engine 2 + accuracy (real Sentinel-2 support)

```
Read PROJECT_BRIEF.md and HANDOFF.md fully before doing anything. Phases 1 and 2 are done. I'm doing Phase 3.

SETUP:
1. git checkout main && git pull, then git checkout -b phase-3
2. If this machine isn't set up yet, follow HANDOFF.md (Python 3.11). Start backend and frontend, upload terrawatch-test-pair/before.tif + after.tif, run the unit tests, and tell me if anything fails before continuing.

PHASE 3 — make the app work on real Sentinel-2 data.
Current problem: Engine 1 (TinyCD) works on LEVIR-CD (F1 0.914) but finds 0 changes on Sentinel-2 imagery (10 m), so the map is empty on our real demo data.

1. Safety net: until Engine 2 is ready, auto-select the spectral baseline for any input coarser than ~2 m/pixel, so the app never shows an empty map on Sentinel-2 data.
2. Engine 2: train a lightweight U-Net on OSCD (Sentinel-2; input = stacked before/after bands + ΔNDVI/ΔNDWI/ΔNDBI/brightness). Small enough to train in reasonable time on this machine. Fetch OSCD by script if possible; if it needs a manual download, tell me exactly how. Save weights to models/ (gitignored) and add a train/download script so teammates can reproduce it.
3. Engine auto-selection by resolution and band count: ≤2 m RGB → TinyCD; multispectral or ≥5 m → Engine 2 (fallback: spectral baseline). Never run TinyCD on Sentinel-2.
4. "Engine" dropdown in the left panel: Auto (default), TinyCD, Engine 2, Spectral baseline. Show the engine used in the result status and in export attributes.
5. scripts/evaluate.py: precision, recall, F1, false-positive rate for TinyCD on the LEVIR-CD test split and Engine 2 on the OSCD test split. Save to JSON.
6. Accuracy page in the UI: a simple table that reads that JSON. Real numbers only.
7. Real tests:
   - Pune Sentinel-2 2019 vs 2024: show detected polygons.
   - Wayanad: lowest-cloud Sentinel-2 scenes before and after 30 July 2024, Mundakkai/Chooralmala area. Show whether the landslide path is detected.
   - One real high-res (≤1 m) georeferenced pair from OpenAerialMap or Maxar Open Data: show TinyCD producing polygons. Tell me the source.
8. Run check_results.py on the test pair with the Spectral baseline engine and show the output.
9. Update HANDOFF.md with what changed and any new setup steps.

Screenshots only at the end of the phase to save usage. Commit on phase-3, push, open a pull request to main, and stop for review.
```

---

## Phase 4 — Trust layer (fake-change filter)

This is your strongest technical differentiator. Do it carefully.

```
Read PROJECT_BRIEF.md and HANDOFF.md fully. Phases 1–3 are merged. I'm doing Phase 4.

SETUP: git checkout main && git pull, then git checkout -b phase-4. Start the app and confirm it works before changing anything.

PHASE 4 — trust layer. Every candidate change must be either KEPT or REJECTED with a reason.

1. Quality check, run before detection, saved with the analysis and shown in the UI as a "Quality report":
   - Cloud cover %: Sentinel-2 SCL band when available; for RGB, a brightness/whiteness heuristic.
   - Misalignment: estimate the pixel shift between before and after (phase correlation). Warn if > 1 pixel.
   - Resolution, band count, engine used.
   - Show warnings as a quiet amber banner. Test with terrawatch-test-pair/after_misaligned_3px.tif — it must trigger the alignment warning.
2. False-alarm filter. For each candidate polygon compute evidence and decide kept/rejected. Rejection reasons:
   - vegetation_seasonal: change dominated by ΔNDVI with no built-up or water change
   - shadow_illumination: brightness-only change with low texture/structure change
   - cloud: overlaps the cloud mask
   - too_small: below minimum area
   - misalignment_edge: thin slivers along edges consistent with a pixel shift
   For RGB-only input, use the rules that are possible and mark the rest "unavailable" (no NIR → no NDVI rule; say so).
   Thresholds in a config file, not hard-coded.
3. Confidence: mean model probability inside each polygon. Below a configurable threshold → needs_review = true.
4. Change type label for kept polygons: new_construction, structure_lost, flooding, landslide_bare_soil, vegetation_loss, other. Rule-based on index differences + model output. Store which rule fired (change_type_rule). Label in the UI as "estimated type".
5. Export: include ALL polygons with status kept|rejected, reject_reason, change_type, change_type_rule, confidence, needs_review.
6. Map:
   - Toggle "Show rejected changes": grey dashed outlines.
   - Needs-review polygons: dotted outline.
   - Clicking a rejected polygon shows the reason in plain language, e.g. "Rejected: vegetation change (NDVI dropped, no built-up change)".
7. Results summary line: "N candidates → K kept, R rejected (by reason: …)".
8. Evaluation: extend evaluate.py with an ablation table — raw model → + morphology → + false-alarm filter — with precision, recall, F1 for each step. Show it on the Accuracy page.
9. Test with terrawatch-test-pair (4-band before.tif/after.tif, Spectral baseline engine): run check_results.py. Target: F1 seasonal_vegetation, F2 shadow_shift, F3 cloud all "good" (<10% flagged) and appearing as rejected with the correct reason, while R1–R4 are still FOUND. Do NOT tune thresholds only for this synthetic pair — also check the Pune and Wayanad results don't lose their real changes. Report before/after numbers honestly.
10. Unit tests for each rejection rule and the change-type rules.
11. Update HANDOFF.md.

Screenshots only at the end. Commit on phase-4, push, open a PR to main, and stop for review.
```

---

## Phase 5 — Impact layer (social impact)

```
Read PROJECT_BRIEF.md and HANDOFF.md fully. Phases 1–4 are merged. I'm doing Phase 5.

SETUP: git checkout main && git pull, then git checkout -b phase-5. Start the app and confirm it works first.

PHASE 5 — who is affected and where to look first. Only KEPT polygons get impact analysis.

1. Population: use a WorldPop (or GHSL) population GeoTIFF for India. Script the download if possible; otherwise tell me exactly how and where to put it (data/population/). For each polygon compute population_est (inside polygon) and population_buffer_est (within a configurable buffer, default 250 m). Always label as "estimate". If no population file is present, skip gracefully and say so in the UI.
2. Facilities from OpenStreetMap (osmnx/Overpass) for the analysis bounding box: hospitals, clinics, schools, main roads, shelters if tagged. Cache to disk per bbox. For each polygon: nearest_hospital_m, nearest_school_m, nearest_main_road_m, and a list of facilities within a configurable distance.
3. Severity stays as is (change strength). Add the priority score (Disaster mode):
   priority = w1·sev_score + w2·norm(population_est) + w3·facility_proximity + w4·confidence
   (route impact comes in Phase 7 — leave a slot for it with weight 0). Weights in config and editable in a Settings panel.
   priority_reason: a plain sentence with the top 2–3 factors, e.g. "High severity; ~420 people estimated nearby; 180 m from a hospital."
4. Priority queue panel (right side): ranked list of kept polygons with rank, type, area, people estimate, nearest facility, reason. Clicking a row zooms the map to it and opens details; hovering highlights the polygon (two-way linking).
5. Map layers toggles (left panel): Population (heatmap or graduated), Facilities (small icons, no emoji), Roads.
6. Modes:
   - Disaster: priority as above.
   - Prevention: user can upload a hazard-zone GeoJSON or draw a polygon on the map (label "user-provided zone"). Highlight new_construction polygons inside a zone (in_hazard_zone = true) and rank those first. Wording: "New structure detected in hazard zone — verify". Never "illegal".
7. Summary strip: total people estimated in affected areas, number of priority areas near critical facilities. Real computed numbers only.
8. Export: add population_est, population_buffer_est, nearest_*_m, priority_score, priority_rank, priority_reason, in_hazard_zone.
9. Test on Wayanad (Disaster) and Pune 2019 vs 2024 (Prevention with a drawn zone near the river). Screenshots of the priority queue and a selected polygon's details.
10. Unit tests for the priority score and population sum.
11. Update HANDOFF.md.

Commit on phase-5, push, open a PR to main, and stop for review.
```

---

## Phase 6 — Auto-fetch imagery + Wayanad demo

```
Read PROJECT_BRIEF.md and HANDOFF.md fully. I'm doing Phase 6. (This can run in parallel with Phase 4 — avoid editing the detection/filter code.)

SETUP: git checkout main && git pull, then git checkout -b phase-6. Start the app and confirm it works first.

PHASE 6 — fetch real satellite images from the app, plus a one-click demo.

1. Backend: POST /api/analyses/fetch with place name OR bbox, before date range, after date range, max cloud %, mode, engine.
   - Geocode place names with Nominatim (respect its usage policy: user agent, rate limit).
   - Search Sentinel-2 L2A on Microsoft Planetary Computer (pystac-client + planetary-computer). Pick the lowest-cloud scene in each range that covers the bbox.
   - Clip both to the bbox, keep needed bands (B2,B3,B4,B8,B11 + SCL), save as co-registered GeoTIFFs, then run the normal pipeline.
   - Reuse any fetch code already written in Phases 2–3 instead of duplicating it.
2. Frontend: an "Auto-fetch" tab next to "Upload" in New Analysis: place search box, option to draw a box on the map, two date-range pickers, max cloud slider. Show which scenes were chosen (date, cloud %) in the quality report.
3. Clear errors: no scenes found, too cloudy, area too large (set a sensible max bbox size), network failure.
4. Demo presets (cache the fetched files so the demo works offline / without waiting):
   - "Wayanad landslide 2024" (Disaster mode)
   - "Pune urban growth 2019–2024" (Prevention mode)
   Add a "Load demo" button in the empty state and a dropdown of presets. Write scripts/fetch_demo_data.py to prepare the cache.
5. Make sure the demo runs end to end in under ~1 minute on this machine once cached; tell me the actual time.
6. Update HANDOFF.md (including how to prepare demo data on a fresh clone).

Commit on phase-6, push, open a PR to main, and stop for review.
```

---

## Phase 7 — Smart features (routes, AI summary, ask-the-map, field feedback)

```
Read PROJECT_BRIEF.md and HANDOFF.md fully. Phases 1–6 are merged. I'm doing Phase 7.

SETUP: git checkout main && git pull, then git checkout -b phase-7. Start the app and confirm it works first. Check .env.example — I need ANTHROPIC_API_KEY for steps 2–3; if it's missing, build those features to degrade gracefully and tell me.

PHASE 7:
1. Blocked-route checker: for each kept polygon intersecting a road, build the OSM road graph (osmnx, cached), remove the intersected segments, and check whether settlements/buildings within a radius can still reach the nearest hospital. Store route_impact (none | detour | no_alternative | unknown) and detour_m. Show it in details with the wording "Possible blockage — verify on ground". Plug route impact into the priority score (the w4 slot from Phase 5) with a configurable weight. Draw the original and detour routes on the map when a polygon is selected.
2. AI situation summary: a panel with a language toggle EN / हिंदी / मराठी. Send the LLM ONLY a JSON of computed facts (counts, areas, top 5 priorities with reasons, population estimates, quality warnings). System prompt must forbid adding any facts not in the JSON. Show the note: "AI-generated summary from computed results — verify before official use." Model from env LLM_MODEL (default claude-sonnet-5-5), key from ANTHROPIC_API_KEY.
3. Ask the map: an input on the map ("show high-severity changes near schools", "changes bigger than 1000 m²"). The LLM converts the question into a structured filter JSON (define a schema: severity, change_type, status, min_area, max_area, near_facility_type, max_distance_m, needs_review, in_hazard_zone). Validate it, apply it on the frontend to the map and priority queue, and show active filters as removable chips. The LLM never answers with data itself. If the question can't be mapped, say so.
4. Field feedback: on each polygon, buttons Confirmed / False alarm / Unsure + optional note, stored in SQLite with timestamp. Show feedback status on the map (small marker) and in the queue. Accuracy page: add "field-verified precision" (confirmed / (confirmed + false alarm)) with the count, only when there's feedback. Document in HANDOFF.md how feedback can be used to tune thresholds.
5. Tests: route-impact logic on a tiny synthetic graph; filter-schema validation; feedback API.
6. Update HANDOFF.md.

Commit on phase-7, push, open a PR to main, and stop for review.
```

---

## Phase 8 — Reports, alerts, speed counter, polish, demo-ready

```
Read PROJECT_BRIEF.md and HANDOFF.md fully. Phases 1–7 are merged. I'm doing Phase 8, the final phase.

SETUP: git checkout main && git pull, then git checkout -b phase-8. Start the app and confirm it works first.

PHASE 8:
1. Field report:
   - PDF (WeasyPrint or ReportLab): title, date, area, engine, quality warnings, map snapshot with polygons, summary numbers, table of priority polygons (rank, type, area, confidence, people estimate, nearest facility, route impact, reason, Google Maps link), honesty notes.
   - Mobile-friendly HTML report page: single column, readable at 375 px wide, light enough to share on WhatsApp.
   - "Generate report" button with both options.
2. Telegram alerts: when an analysis has High-priority items, send one message per analysis (top 3 items: type, area, people estimate, reason, Google Maps link). Uses TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID; skip gracefully if missing. A "Send test alert" button in Settings.
3. Speed counter: show area analysed (km²) and processing time from real timings. Optional comparison to manual inspection only with a stated, editable assumption in config (e.g. "assuming X km²/hour for an analyst").
4. UI polish against Section 10 of PROJECT_BRIEF.md:
   - Navigation rail: New Analysis, Map & Results, Priority Queue, Reports, Accuracy, Settings.
   - Designed states: processing steps, warnings, empty state with "Load demo", errors with what to do next.
   - Consistent tokens, Inter/IBM Plex Sans + mono for numbers, tabular numerals, colour-blind-safe severity (labels/patterns, not just colour), keyboard focus states.
   - Coordinate readout under cursor, scale bar, date labels on each side of the swipe.
   - Remove any leftover placeholders, console errors and dead buttons.
5. Honesty notes (Section 11 of the brief) visible in the app (an info popover) and in reports.
6. Demo hardening:
   - Run the full demo flow from Section 12 of the brief end to end on a fresh browser session and fix anything that breaks.
   - Make sure the demo works without internet using the cached demo data (except LLM/Telegram, which should fail gracefully).
   - Write DEMO_SCRIPT.md: a 5-minute walkthrough with what to click and what to say at each step.
7. README.md final pass: what it is, features, architecture diagram (simple text/mermaid), setup, demo, accuracy numbers (from evaluate.py JSON), limitations.
8. Run all tests and the evaluation script one last time; report the results.

Screenshots of every main screen at the end. Commit on phase-8, push, open a PR to main, and stop for review.
```

---

## After each phase

1. Read the summary and check the screenshots.
2. Merge the pull request on GitHub (or ask Claude Code to merge it).
3. Check your weekly usage.
4. Start the next phase in a fresh session.
