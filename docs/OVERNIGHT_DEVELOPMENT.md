# Overnight Development (after Round 2, 9–10 Oct 2026)

This log covers everything built **after 8:00 PM IST on 9 Oct 2026**, in two
sessions: the overnight push that produced the Round 2 submission (dark UI
redesign, ranking/severity fixes, the README/docs/CI package in PR #4), and
the Round-2-to-Round-3 push on top of it (this document's later sections,
appended as each item ships). Every number below is read from a real git
commit, test run, or live export — nothing here is a target or an estimate
unless explicitly labeled one, matching the project's own honesty rule (see
`README.md`'s "Honesty rules" section).

Timestamps are from `git log --date=iso` (IST, `+0530`). The cutoff commit
is `d5c8a7b` (04:18:15, 10 Oct) — the last commit before 20:00 on 9 Oct is
`d05bbca` (19:42:27, 9 Oct).

## Session 1: overnight push to the Round 2 submission (branch `ui-redesign` → `submission`, merged as PR #4)

### 1. Dark UI redesign (`ui-redesign` branch, 11 commits, 04:30–05:03 IST)

Frontend-only redesign replacing `PROJECT_BRIEF.md` Section 10's light
design brief with a dark one — no backend, detection, filter, or priority
logic touched; same component state and handlers throughout, just
restyled, plus a few genuinely new additive pieces.

- Dark palette (`#0B1215` / `#111B1F` / `#18252A` surfaces, `#2FD3C1` teal
  accent, fixed severity colors), Inter + JetBrains Mono, `lucide-react`
  icons — `frontend/src/styles/tokens.css` + `design-system.css`.
- New: explicit Priority queue / Change details tabs, a KPI strip, a
  one-click "Load Wayanad demo" landing button, a Settings "Reset to
  defaults" action.
- Commits: `d795362` (design system + app shell + landing + processing +
  KPIs), `3e31fba` (map overlays, dark theme, scale bar, cursor coords),
  `1fe3227` (right-panel Priority/Details tabs), `ca2a0eb` (Accuracy +
  Settings pages), `a3c9669` (two cursor/event bugs — see §3 below),
  `2d08402` (severity/ranking/KPI/accuracy fixes — see §2 below).

**After** (current `main`, this repo): see `docs/screenshots/landing.png`,
`results_map.png`, `priority_queue.png`, `accuracy.png` (committed in PR
#4) and the fresh `00_baseline_wayanad.png` captured below in "Setup
verification". No "before" screenshot of the light design exists in this
repo — Phase 1–5 development didn't commit UI screenshots, only this
overnight session started doing so.

### 2. Severity/ranking fix — the headline numbers

**Problem found** (commit `2d08402`, 05:02:24 IST): on the real Wayanad
pair, `app/pipeline/severity.py` produced **0 High / 2 Medium / 177 Low**
kept polygons, with the landslide itself (1,556,600 m², 94% confidence)
scored only "Medium" — and consequently ranked outside the top of the
priority queue, behind polygons with near-zero population nearby.

**Root cause:** plain min–max normalization of `area_m2` averaged with
`change_magnitude`. The landslide's area (1.56M m²) is such an outlier
against the next-largest kept polygon (141,200 m²) that it stretched the
0–1 normalization range so far that nearly every other real polygon
compressed toward zero — and even the landslide itself got pulled down by
averaging with a middling `change_magnitude`.

**Fix:** `sev_score = max(norm(log1p(area_m2)), norm(log1p(change_magnitude)))`
— log-scaling keeps normalization meaningful across orders of magnitude,
and `max()` (not an average) means a polygon is severe if it's either very
large *or* very intense, without one weak factor capping the other.

**Result:**

| | Before | After |
|---|---|---|
| Severity distribution (kept, Wayanad) | 0 High / 2 Medium / 177 Low | **19 High / 79 Medium / 81 Low** |
| Landslide severity | Medium | **High (sev_score 1.000)** |
| Landslide priority rank | outside the top ranks (as low as **#3** observed in testing before this fix) | **#1**, robustly (priority_score 0.680 vs. #2's 0.624 — not a knife-edge result) |

New real top 5 on Wayanad (Disaster mode, Auto engine) after the fix:
#1 `landslide_bare_soil` 1,556,600 m² High (0.680), #2 `structure_lost`
21,200 m² Medium (0.624), #3 `other` 126,500 m² High (0.620), #4 `other`
141,000 m² High (0.527), #5 `other` 45,900 m² Medium (0.482).

6 new/updated regression tests in `backend/tests/test_severity.py` encode
both the severity formula and the ranking outcome. UI tooltips (map legend
+ polygon details) updated to show the new formula. No "before" screenshot
exists — this was caught and verified through the live app and the test
suite, not a screenshot comparison; the current state is the same
`results_map.png` / `priority_queue.png` referenced above.

### 3. KPI and Accuracy-page fixes (commit `2d08402`)

- **KPI strip:** "People affected" showed a raw, unrounded float with no
  thousands separator (`6695.3`). `KpiStrip` now takes an explicit
  `decimals` prop instead of inferring formatting from
  `Number.isInteger`; the people card uses `decimals=0` with a `~` prefix
  and `(estimate)` suffix → **`~6,695 (estimate)`**. Relabeled "People in
  changed areas". Count cards (changes kept, rejected, priority areas)
  already had no decimals; area (a continuous km² measurement) keeps 1
  decimal place. Confirmed live in the current app (see "Setup
  verification" below) and in `README.md`'s case-study table, which
  already reads `~6,695`, not `6,695.3`.
- **Accuracy page:** metric cards now show `raw X → with filter Y` under
  the headline F1 (e.g. TinyCD: `raw 0.914 → with filter 0.903`), matching
  what the detailed ablation table already presented, so raw-vs-filtered
  is never ambiguous at a glance.

### 4. The 4 UI bugs found and fixed

Found via Playwright click/hover/build testing against the real running
app — not just eyeballing screenshots. Documented here because they're the
kind of bug a screenshot alone would miss (the page renders fine; the
interaction is broken).

1. **Reactive layer-sync effects checked a hardcoded source name.** The
   before/after split view uses two independent MapLibre instances whose
   image sources are named `"before-img"` and `"after-img"` respectively.
   An effect gating Population/Facilities/Roads layers on
   `map.getSource("before-img")` for *both* maps was always false on the
   after-map, so those layers silently never attached there — a
   screenshot of the rendered map looked completely plausible. Fixed with
   a `mapHasImage()` helper that checks either source name, and dropped a
   flaky `isStyleLoaded()` gate (`frontend/src/map/CompareMap.tsx`).
   Caught by instrumenting a test script with `queryRenderedFeatures`, not
   by looking at a screenshot.
2. **A custom `Switch` component rooted in `<span>` instead of `<label>`.**
   Clicking the visible toggle never reached the visually-hidden
   `<input>` underneath — every toggle in the app was unclickable despite
   looking and rendering correctly.
3. **`tsc --noEmit` doesn't catch everything the real build does.** `tsc
   -b` (what `npm run build` actually runs) caught a MapLibre event-type
   error on `"mouseleave"` at the whole-map level (that event needs a
   layer id; the whole-map case needs `"mouseout"` instead) that
   `--noEmit` alone missed.
4. **A mousemove/click handler added to one side of the swipe map must be
   added to *both* `MLMap` instances**, since the swipe divider means
   either side can be under the cursor. This one recurred three separate
   times — across the hover-glow, hazard-zone draw, and cursor-coordinate
   features — before being treated as a standing rule rather than a
   one-off fix.

### 5. README/docs/CI/model-card submission package (PR #4, `submission` branch, 05:10–05:19 IST, merged as `ca033d4`)

- Rewrote `README.md` as the main entry point: pitch, CI/Python/license
  badges, a problem-statement-requirements → implementation table (exact
  brief wording, file paths, verification steps), a "beyond the brief"
  table, a Mermaid architecture diagram, and real results tables.
- Added `docs/ARCHITECTURE.md`, `docs/EVALUATION.md`, `docs/MODEL_CARD.md`.
- Added CI (`.github/workflows/ci.yml`: backend pytest + ruff/black,
  frontend `tsc -b` build + prettier check) and a `Makefile`
  (`setup`/`demo`/`test`/`eval`/`lint`/`format`).
- Committed `sample_data/wayanad/` (~11.8 MB) so a fresh clone can run the
  demo with no live Planetary Computer access.
- Code hygiene: black + ruff across the backend, prettier across the
  frontend, MIT `LICENSE`.
- Verified behavior-neutral: 71/71 backend tests pass before and after,
  `check_results.py` scores identically (precision 0.73 / recall 0.96 /
  F1 0.83), frontend builds clean before and after.
- Merged into `main` as PR #4 (`https://github.com/divishapanjwani/terrawatch/pull/4`), `ca033d4`.

## Setup verification (this session, before starting Round 3 work)

- `git checkout main && git pull && gh pr merge 4 --merge` → PR #4 merged
  (`ca033d4`), `git checkout -b overnight-v2`.
- `cd backend && python -m pytest tests/ -v` → **71 passed**.
- Wired up the Wayanad demo pair (`sample_data/wayanad/{before,after}.tif`
  → `frontend/public/demo/wayanad_*.tif` + `backend/data/wayanad/*.tif`,
  gitignored, per `HANDOFF.md`'s documented setup step).
- Started backend (`:8000`) + frontend (`:5173`), drove the app headlessly
  with Playwright, clicked "Load Wayanad demo", and confirmed the full
  pipeline end to end with **no console errors**:
  - 187 candidates → **179 kept, 8 rejected** (cloud: 7, vegetation_seasonal: 1)
  - Severity: **19 High / 79 Medium / 81 Low**
  - Area changed: **3.7 km²**
  - People in changed areas: **~6,695 (estimate)**
  - Priority areas within 2 km of a hospital/school: **74**
  - Quality report: cloud (before) 10.3%, cloud (after) 0.0%, SCL method,
    misalignment 0.1 px, resolution 10.0 m, 6 bands.

Screenshot: `~/Desktop/screenshots/overnight/00_baseline_wayanad.png`.

---

## Round 3 items (this session)

Each item below is appended only once it's implemented, tested, and merged
into `main` — see the per-item entries that follow for real numbers and
screenshots.

### Item 1: any place in India + Case Studies gallery — DONE

**Auto-fetch** (`backend/app/geo/fetch.py`, `POST /api/analyses/fetch`):
a place name is geocoded via Nominatim (OpenStreetMap, India-scoped,
1 req/s per its usage policy) into a ~6-7 km bbox, or a bbox can be
passed directly (`bbox=west,south,east,north` — supported and tested via
curl, but **not yet wired to a draw-on-map control in the frontend**,
only place-name search; noted here rather than silently dropped). The
lowest-cloud Sentinel-2 L2A scene in each of the given before/after date
ranges is fetched from Planetary Computer, clipped, and run through the
unmodified pipeline. The chosen scene dates and cloud % are shown in the
UI ("Auto-fetched: before 2023-01-09 (0.0% cloud) → after 2023-11-15
(1.4% cloud)").

Verified end-to-end through the real browser UI (Playwright, not just
curl): searched "Chungthang, Sikkim, India" → geocoded, fetched, and
analyzed → **169 kept, 45 rejected** (214 candidates), 51 High / 75
Medium / 43 Low, ~1,251 people estimate, no console errors. Screenshot:
`03_fetch_by_place.png`.

**Case Studies gallery** (`backend/app/case_studies.py`,
`GET /api/case_studies`, `POST /api/case_studies/{slug}/load`,
`frontend/src/pages/CaseStudiesPage.tsx`): 4 real Indian events, each
with a pre-fetched, cached Sentinel-2 pair (`backend/data/case_studies/`,
gitignored, regenerate via `scripts/fetch_case_studies.py`) and a
committed thumbnail (`frontend/public/case_studies/<slug>.jpg`) — no
live Planetary Computer call needed to demo it:

| Case study | Location | Event | Result (real pipeline run) |
|---|---|---|---|
| Wayanad landslide | Mundakkai/Chooralmala, Kerala | 30 Jul 2024 | 179 kept / 8 rejected (existing demo pair) |
| Sikkim GLOF / Teesta valley | Chungthang, Sikkim | 4 Oct 2023 dam breach | **347 kept / 72 rejected**, 92 High/166 Med/89 Low, ~1,714 people est. |
| Himachal Pradesh floods | Manali, Kullu valley, HP | 7-10 Jul 2023 | cached and loadable; see caveat below |
| Pune urban growth | Punawale/Ravet, Pimpri-Chinchwad | 2019→2024 | 7 kept incl. 2 genuine `new_construction` (see verification below) |

Coordinates/dates were verified, not guessed — against Nominatim (place
→ precise lat/lon, e.g. Teesta Stage III Dam 27.5975°N/88.6508°E),
Nature Scientific Reports (Wayanad), and Wikipedia (Himachal/Sikkim
event pages). Two verification failures are documented honestly rather
than hidden: the original Kullu-town bbox straddled the edge of
Sentinel-2 tile T43SGR and produced mismatched band shapes on fetch —
shifted to Manali, fully inside the tile (see
`app/case_studies.py`'s `source` field for the Himachal entry); and 2 of
3 candidate Pune bboxes (Kharadi, the original Phase-5 Hinjewadi bbox)
were tested via `scripts/_test_pune_candidates.py` and rejected because
they yielded zero real `new_construction` detections under the current
engine/thresholds — only Punawale/Ravet did.

**Caveat, stated honestly:** the Sikkim GLOF and Pune change-type labels
are weaker than Wayanad's — `change_type` rules were tuned against
Wayanad's landslide signature, and on Sikkim most kept polygons
(mostly river-channel/shoreline change from a lake-level/seasonal shift)
label as `other` or `structure_lost` rather than a GLOF-specific type,
and Pune's debris/construction ambiguity (documented in `HANDOFF.md`'s
change-type gotcha) still produces some `landslide_bare_soil` labels on
what's actually a construction site. This is a known, reported
limitation of the rule-based classifier, not a new bug.

Screenshots: `01_case_studies_gallery.png` (all 4 thumbnails), `02_case_study_loaded.png` (Sikkim GLOF loaded, real severity-colored polygons along the Teesta valley).

Backend: 71/71 tests still pass. Frontend: `tsc -b` + `vite build` clean.

## Session 3 (10 Oct 2026 morning, branch `overnight-v3`)

Resumed with PR #4 and Item 1 already on `main`. Setup: fixed a local
Makefile bug (`$(VENV_BIN)` resolved to `backend/backend/venv/bin/...`
after the `cd backend &&` targets already changed directory — fixed to a
plain `venv/bin/...`), merged teammates' new `docs/IMPACT_AND_DEPLOYMENT.md`
/ `docs/USER_GUIDE.md` / `docs/CASE_STUDY_WAYANAD.md` (added directly to
`main` by teammates, pulled and merged cleanly, now linked from the
README's new "Documentation" table), reconfirmed the Wayanad demo and a
live "Pune, Maharashtra" place-fetch both work end to end (41 kept / 60
rejected on the geocoded Pune city-center bbox — a different, wider area
than the curated Punawale/Ravet case study, which is the point: it's the
generic "any place" path, not a special case).

### Item A, part 1: blocked-route checker — DONE

**What it does:** for every kept polygon that intersects an OSM road, an
osmnx drive-network graph (cached to disk like `facilities.py`'s Overpass
cache, same ~15 km buffer) is used to check whether the nearest hospital
is still reachable with that road's edges removed. Sets `route_impact`
(`none` / `detour` / `no_alternative` / `unknown`) and `detour_m` per
polygon — `None` (not `"none"`) for polygons that don't touch a road at
all, so "checked, no impact" is never confused with "not applicable."

**Priority score:** `route_impact` now has a real weight — the w5 slot
was reserved at 0.0 since Phase 5. Weights rebalanced from
0.35/0.25/0.2/0.2/0.0 to **0.30/0.20/0.15/0.15/0.20** (severity still
weighted highest). `priority_reason` cites a blockage with the exact
required wording, e.g. *"High severity; ~936 people estimated nearby;
576 m from a school; nearest hospital route may be cut off (possible
blockage — verify on ground)."*

**Real numbers, Wayanad (Disaster mode, Auto engine), 179 kept polygons:**

| route_impact | count |
|---|---|
| not applicable (no road touched) | 146 |
| `none` (touches a road, but unaffected) | 19 |
| `no_alternative` | **10** |
| `detour` | 4 |

The #1 priority item — the landslide itself — is `route_impact:
no_alternative`: the road through Mundakkai/Chooralmala is genuinely a
single mountain road with no alternate path to the nearest hospital once
blocked, which matches real reporting on this landslide (the access road
was destroyed, isolating the area). This is a real, honest signal, not
tuned to look good — 10 isolated segments out of 179 kept polygons in a
sparse hill road network is a plausible, checkable number.

**On-demand route geometry** (`GET /api/analyses/{id}/polygons/{id}/route`):
returns the original and (if one exists) detour path node coordinates
for the map to draw when a polygon is selected — not precomputed/stored
for all 179 polygons, which would bloat the export. Caught and fixed a
real bug here during testing: the bulk pipeline step and this endpoint
initially used two different edge-intersection implementations (a
geopandas spatial join vs. a manual bbox-filtered Python loop), which
disagreed on a borderline/boundary-touching polygon (bulk said `detour`,
on-demand said `none` for the same polygon). Fixed by sharing one
edge-lookup helper; reverified identical results on one sample polygon
per `route_impact` value via curl.

**New system dependencies** (not in `requirements.txt` before):
`osmnx` + `networkx` (route graph) and `scikit-learn` (required by
`osmnx.distance.nearest_nodes` on an unprojected lat/lon graph — this
wasn't obvious until it failed at runtime with `ImportError: scikit-learn
must be installed`, not at `pip install` time).

**Frontend:** `CompareMap` draws the route on both before/after maps
(Gotcha #4 from `HANDOFF.md` applies here too — had to add the layer/
effect to both `MLMap` instances) — teal when unaffected, amber dashed
for a detour, red dashed for no alternative. `PolygonPanel` shows a
"Route impact" row and an amber/red banner with the required wording.

**Verified end-to-end via Playwright** (not just curl): loaded the
Wayanad demo, selected the #1 priority item (the landslide), confirmed
the "Nearest-hospital route may be cut off — possible blockage — verify
on ground" banner, the "Route impact: no alternative" detail row, and
the red dashed route line all render with no console errors. Screenshot:
`04_blocked_route.png`.

6 new unit tests (`backend/tests/test_routes.py`, pure graph logic on a
small synthetic graph, no network calls — runs in CI). 77/77 backend
tests pass (71 existing + 6 new). Frontend: `tsc -b` + `vite build`
clean. Merged into `main`.

### Item A, part 2: PDF/HTML field report, English/Hindi/Marathi — DONE

**What it does:** `GET /api/analyses/{id}/report?format=pdf|html&lang=en|hi|mr`
builds a one-page field report straight from already-computed results —
no LLM call, nothing invented. KPI strip (kept/rejected counts, area
changed, people estimate), a map snapshot (the after-image preview with
severity-colored polygon outlines drawn on top, same palette as the live
map), the top 10 priority areas as a table (type, area, people estimate,
nearest hospital + distance, route impact, the full priority reason,
a Google Maps link), and the same 4 honesty notes as this README's
"Honesty rules" section. `format=html` is the mobile-friendly page
(single column, readable at 375px, ~130 KB self-contained with an
embedded/downscaled snapshot image — light enough for WhatsApp);
`format=pdf` renders the identical content via WeasyPrint.

**A real bug found during testing, not just "looks fine":** the first
version reused `priority_reason` — a pre-built English sentence from
`app/pipeline/priority.py` — directly in the Hindi/Marathi reports, so
every row's "Reason" column stayed in English regardless of the
language picked. Fixed by adding `_localized_reason()`
(`app/reports/field_report.py`), which rebuilds the same sentence from
the underlying computed values (severity, population estimate, nearest
facility distance, route impact) using per-language phrase templates
(`app/reports/i18n.py`) instead of reusing the English string — verified
by checking the literal word "severity" doesn't appear in the Hindi/
Marathi output (`tests/test_field_report.py`).

**Hindi and Marathi template text — for native-speaker review.** These
are AI-drafted first-draft translations, not yet reviewed by a native
speaker; flagged here and in the README rather than presented as final.
Full source: `backend/app/reports/i18n.py`.

Static UI chrome (a sample, English → Hindi → Marathi):

| English | Hindi | Marathi |
|---|---|---|
| TerraWatch Field Report | टेरावॉच फ़ील्ड रिपोर्ट | टेरावॉच फील्ड अहवाल |
| Automated analysis — verify before official use. | स्वचालित विश्लेषण — आधिकारिक उपयोग से पहले सत्यापित करें। | स्वयंचलित विश्लेषण — अधिकृत वापरापूर्वी पडताळणी करा. |
| Changes kept / False alarms rejected | पुष्ट परिवर्तन / अस्वीकृत झूठे अलार्म | निश्चित बदल / नाकारलेले खोटे इशारे |
| People in changed areas (estimate) | प्रभावित क्षेत्रों में अनुमानित लोग | प्रभावित भागातील अंदाजे लोक |
| Top priority areas | शीर्ष प्राथमिकता वाले क्षेत्र | सर्वोच्च प्राधान्य क्षेत्रे |
| No alternative route | कोई वैकल्पिक मार्ग नहीं | पर्यायी मार्ग नाही |
| What this report does and doesn't say | यह रिपोर्ट क्या कहती है और क्या नहीं | हा अहवाल काय सांगतो आणि काय सांगत नाही |

The 4 honesty notes:

| # | English | Hindi | Marathi |
|---|---|---|---|
| 1 | Change detection is not damage assessment — severity measures how much change occurred, not confirmed damage. | परिवर्तन का पता लगाना क्षति आकलन नहीं है — गंभीरता परिवर्तन की मात्रा मापती है, पुष्ट क्षति नहीं। | बदल शोधणे म्हणजे नुकसानीचे मूल्यांकन नाही — तीव्रता बदलाचे प्रमाण मोजते, निश्चित नुकसान नाही. |
| 2 | Every people-affected number is an estimate from a population grid, not a headcount. | प्रभावित लोगों की हर संख्या जनसंख्या ग्रिड से एक अनुमान है, वास्तविक गिनती नहीं। | प्रभावित लोकांची प्रत्येक संख्या लोकसंख्या ग्रिडवरून केलेला अंदाज आहे, प्रत्यक्ष मोजणी नाही. |
| 3 | Road blockages are a graph-reachability signal only — "possible blockage, verify on ground," never a confirmed closure. | सड़क अवरोध केवल एक मार्ग-संपर्क संकेत है — "संभावित अवरोध, ज़मीन पर सत्यापित करें," कभी भी पुष्ट बंद नहीं। | रस्ता अडथळा हा केवळ मार्ग-संपर्क सूचक आहे — "संभाव्य अडथळा, जागेवर पडताळणी करा," कधीही निश्चित बंद नाही. |
| 4 | This report is generated directly from computed analysis results. No AI-generated facts are included. | यह रिपोर्ट सीधे गणना किए गए विश्लेषण परिणामों से तैयार की गई है। इसमें कोई AI-जनित तथ्य शामिल नहीं हैं। | हा अहवाल थेट मोजलेल्या विश्लेषण निकालांमधून तयार केला आहे. यात कोणतीही AI-निर्मित माहिती समाविष्ट नाही. |

Per-row reason sentence, reconstructed (not translated verbatim) from
computed values — real Wayanad #1 priority row:

- **EN:** "High severity; ~936 people estimated nearby; 576 m from a school; nearest hospital route may be cut off (possible blockage — verify on ground)."
- **HI:** "उच्च गंभीरता; आसपास ~936 लोगों के प्रभावित होने का अनुमान; स्कूल से 576 मी; निकटतम अस्पताल तक का मार्ग अवरुद्ध हो सकता है (संभावित अवरोध — ज़मीन पर सत्यापित करें)."
- **MR:** "उच्च तीव्रता; जवळपास अंदाजे ~936 लोक प्रभावित; शाळेपासून 576 मी; जवळच्या रुग्णालयाचा मार्ग बंद होऊ शकतो (संभाव्य अडथळा — जागेवर पडताळणी करा)."

**Verified on Wayanad (179 kept, 8 rejected):** HTML report ~131 KB (EN),
~133 KB (HI/MR, a bit larger — Devanagari text). PDF: 5 pages, ~113 KB
(EN), ~124 KB (HI/MR). Map snapshot shows all 179 severity-colored
polygon outlines correctly positioned over the after image. Devanagari
renders correctly in both the browser (HTML) and WeasyPrint's PDF output
(verified visually, not just "the bytes didn't error") — both Hindi and
Marathi titles are legible, not tofu boxes. Table rows no longer split
across PDF page breaks (`page-break-inside: avoid`, found and fixed
during testing — the first PDF render split row #1 awkwardly across
pages 1 and 2).

**New system dependency:** WeasyPrint needs Pango/Cairo system libraries
(`brew install pango` on macOS) — not installable via `pip` alone; the
HTML report works without it, only PDF export needs it. Documented in
the README prerequisites.

7 new unit tests (`backend/tests/test_field_report.py`) covering the
localized-reason builder (EN/HI/MR, detour phrasing, hazard-zone prefix,
no-route-impact case) and `build_context`'s ranking/rounding/missing-
snapshot handling. 84/84 backend tests pass (77 + 7 new). Frontend:
`tsc -b` + `vite build` clean; verified end-to-end via Playwright
(opened the Export menu, switched to Hindi, opened the mobile report in
a new tab, confirmed the rendered Devanagari text) with no console
errors. Screenshots: `05_field_report_menu.png`, `06_mobile_report_hi.png`.

### Bug found and fixed: Sentinel-2 BOA-offset radiometric mismatch in auto-fetch

**Reported symptom:** auto-fetching Pune with before `2019-01-01/2019-04-30`
and after `2024-01-01/2024-04-30` produced one ~30 km² polygon covering
most of the scene, with a nonsensical ~1.85M people estimate. The 2019
image looked visibly darker than the 2024 one.

**Root cause, confirmed from the STAC items themselves, not guessed:**
Sentinel-2 L2A processing baseline 04.00 (effective 25 Jan 2022) adds a
+1000 DN "BOA add offset" to the spectral bands. The Pune "before" scene
is baseline `02.12` (pre-offset); the "after" scene is baseline `05.10`
(post-offset) — the two are not radiometrically comparable DN-for-DN.
Band means confirmed the ~+1000 systematic shift across R/G/B/NIR/SWIR
(e.g. R: 1237.7 → 2197.2, a +960 shift) with SCL (categorical, unaffected
by reflectance scaling) staying flat.

**Fix** (`scripts/sentinel2_fetch.py::needs_boa_offset_correction` +
`save_clip`): any fetched scene with `s2:processing_baseline >= 4.0`
(falling back to acquisition date `>= 2022-01-25` if that STAC property
is ever missing) has 1000 DN subtracted from its 5 spectral bands —
clipped at 0, never wrapped — before being written. SCL is never
touched. Verified by comparing band statistics before/after the fix:
the before/after gap shrank from ~900-1200 DN (clearly systematic) to
~40-160 DN (consistent with genuine seasonal/real differences, not a
processing artifact).

**Safeguard, independent of the above fix** (`app/geo/quality.py::check_scene_dominance_warning`,
wired into `app/pipeline/run.py`): if any single candidate polygon
covers more than `RADIOMETRIC_MISMATCH_AREA_FRACTION` (25%, `app/config.py`)
of the scene's valid area, the quality report gets the warning
*"possible radiometric mismatch between dates — check imagery"* instead
of silently presenting it as a normal detection. This is defense in
depth — it would have caught this exact bug even without knowing the
BOA-offset root cause, and stays in place for any other future source of
systematic before/after mismatch.

**Real numbers, re-running Pune 2019 vs 2024** (bbox centered on Pune
city via place search, `73.8245,18.4914,73.8845,18.5514`):

| | Before fix | After fix |
|---|---|---|
| Kept / rejected | 41 / 60 | 268 / 46 |
| Largest polygon | **30,439,700 m² (30.4 km², ~70% of the scene)** | 295,100 m² (0.3 km², 0.7% of the scene) |
| People estimate | ~1,851,117 (implausible) | ~2,957,073 |
| Quality warning | none (the bug, un-flagged) | none (now correctly below the 25% threshold) |

The headline fix — the one dominant false polygon — is gone: the largest
candidate shrank **100x** and the quality-report warning correctly stays
silent (no more single-polygon-dominance artifact to flag). Reported
honestly, not cherry-picked: the *people estimate actually went up*
after the fix (more, smaller kept polygons across a dense urban scene,
each independently summing population in its own 250 m buffer — overlapping
buffers aren't deduplicated, a pre-existing simplification unrelated to
this bug, not something this fix was scoped to address), and kept-polygon
count rose sharply (41 → 268) because Engine 2 was never trained on
offset-biased input and detects more plausibly once that bias is
removed — expected, not a new regression.

**The committed Case Studies gallery's `pune_growth` entry was affected
by the same bug** (its date pair, 2019-04-25/2024-04-28, straddles the
same cutover) and has been re-fetched with the fix applied: **114 kept /
18 rejected** (was effectively untested with correct radiometry before),
largest polygon now 5,380,800 m² (17.5% of this bbox's smaller scene —
under the 25% safeguard threshold, but still large enough to flag as
"worth a closer look, not fully clean" rather than claim as a perfectly
tidy result). Still only 2 `new_construction`-labeled polygons, matching
the original claim this case study was chosen for.

**New regression tests** (`backend/tests/test_boa_offset.py`, 9 tests,
no network calls): `needs_boa_offset_correction()` at/below/above the
baseline threshold and the date fallback; the subtract-and-clip math
(spectral bands corrected, SCL untouched, clips at 0 rather than
wrapping); `check_scene_dominance_warning()` firing on the real pre-fix
Pune numbers and staying silent on the real post-fix numbers. 93/93
backend tests pass (84 + 9 new). Verified end-to-end via the live UI
(Playwright, place-search auto-fetch) and the Case Studies gallery, both
with no console errors. Screenshot: `07_pune_boa_fix.png`.

### Item B: draw-a-box for auto-fetch — DONE

**What it does:** `frontend/src/map/BboxDrawMap.tsx` is a standalone
MapLibre map (OSM raster basemap, no API key needed, attribution shown)
in the "New analysis" panel, behind an "Or draw a box on the map"
toggle. Click once for the first corner, move the mouse to preview a
live rectangle, click again for the opposite corner — the drawn bbox
then feeds `POST /api/analyses/fetch` exactly like a typed place name
(mutually exclusive: drawing a box clears the place field). The backend
already supported `bbox=west,south,east,north` since Item 1 (tested via
curl only, back then); this wires an actual UI control to it.

**A real problem found during testing, not just "it draws a rectangle":**
the first version had no size limit. Drawing a box at low zoom (easy to
do by accident — the map opens zoomed out to show all of India) produced
a ~70 km × 75 km area that **never finished fetching** — still stuck at
the `fetching` step after 5+ minutes before being killed. A box that
size means aligning and running inference on a raster orders of
magnitude larger than this pipeline is built for.

**Fix, both ends:** `app/geo/fetch.py::_check_bbox_size` (backend) and
a mirrored constant in `App.tsx` (frontend) reject/disable anything over
`FETCH_MAX_BBOX_SIDE_DEG = 0.25°` (~28 km) per side — the frontend
disables the "Fetch & analyze" button and shows the limit inline before
the request is even sent; the backend rejects it with a clear
`error_message` (not a silent hang) if a request somehow gets through
anyway. Verified both: a 70×75 km box now fails in under a second with
*"That area is too large (0.64° x 0.70°) — max 0.25° per side (~28 km).
Draw a smaller box."*; a real drawn box after zooming in on Chhindwara,
MP (0.16° × 0.15°, ~16×15 km) ran the full pipeline successfully end to
end: **981 candidates → 929 kept, 52 rejected** (took a few minutes —
expected for an area that much larger than the ~6 km demo scale, not a
bug). A Wayanad-scale box (0.06° × 0.07°) via curl: 105 → 93 kept, 12
rejected.

6 new unit tests (`backend/tests/test_fetch.py`): bbox passthrough,
the "need place or bbox" error, rejecting the real 70×75 km box that
triggered this fix, accepting Wayanad-scale and exactly-at-the-limit
boxes, rejecting a box just barely over the limit. 99/99 backend tests
pass (93 + 6 new). Frontend: `tsc -b` + `vite build` clean; both the
too-large warning and a successful small-box draw verified end-to-end
via Playwright with no console errors. Screenshots:
`08_bbox_too_large.png`, `09_bbox_drawn_small.png`.
