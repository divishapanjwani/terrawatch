# TerraWatch AI: Wayanad Landslide Case Study
## Satellite-Based Change Detection for Disaster Assessment

**Project:** TerraWatch AI  
**Study area:** Mundakkai–Chooralmala, Wayanad district, Kerala, India  
**Disaster date:** 30 July 2024  
**Application:** Pre-event and post-event satellite image analysis  
**Objective:** Evaluate how TerraWatch can identify, map and prioritise potential landscape changes following a major landslide.

---

## 1. Abstract

On 30 July 2024, catastrophic rainfall-triggered landslides and debris flows struck the Mundakkai and Chooralmala region of Wayanad district, Kerala, India. The disaster destroyed buildings, damaged infrastructure, altered the landscape and caused extensive loss of life.

This case study examines how TerraWatch AI can support post-disaster assessment by comparing satellite imagery acquired before and after an event. The application identifies candidate changes, assigns severity levels, filters potential false alarms and ranks detections to help users investigate the most important locations.

In the Wayanad demonstration run, TerraWatch reported 179 retained changes, including 19 high-severity detections, approximately 1.56 km² of detected change area and an estimated population of approximately 6,695 people associated with the affected areas.

These results demonstrate the type of information the application can produce. They do not, by themselves, establish detection accuracy or confirm that every mapped change resulted from the landslide. Independent validation against authoritative landslide boundaries and field observations is necessary before operational use.

## 2. Background and Real-World Event

### 2.1 The Wayanad landslides

Wayanad is a district in Kerala, southern India, containing steep terrain, forested slopes, plantations, settlements and river valleys. During the last week of July 2024, exceptionally heavy and persistent rainfall affected the region.

In the early hours of 30 July 2024, major landslides occurred in the vicinity of Punchirimattom, Mundakkai and Chooralmala. A large volume of earth, rock, vegetation and other debris moved downslope and along drainage channels, affecting settlements and infrastructure.

The International Consortium on Landslides' event record documents the disaster's date, location, rapid debris-flow characteristics and extensive building damage. Its record reports 251 deaths and 47 missing people at the time of that record; these figures should be understood in their reporting context rather than treated as a current official casualty count.

**Sources:**

- International Consortium on Landslides — Mundakkai Landslide, Wayanad: https://www.landslides.org/report/mundakkai-landslide-wayanad/
- National Disaster Response Force — Landslide in Wayanad, Kerala: https://www.ndrf.gov.in/en/operations/landslide-wayanad-kerala

### 2.2 Observed geographical impact

Satellite imagery released by India's National Remote Sensing Centre (NRSC) and the Indian Space Research Organisation (ISRO) documented extensive changes to the landslide source area and its downstream path.

Reporting on the satellite observations described approximately 86,000 square metres of slipped land and debris movement extending about 8 kilometres along the Iruvaiphuzha river system.

These observations illustrate why satellite-based assessment is valuable: a disaster can affect a large area, including locations that may be difficult to reach immediately because of damaged roads, unstable slopes, heavy rainfall and accumulated debris.

**Sources:**

- NRSC/ISRO, Landslide Impact Map, Charter Call 1029: https://ndem.nrsc.gov.in/documents/Disaster_Document/2024/KL/kllandslide50dsc05082024/kllandslide50dsc05082024_vap1.pdf
- The Indian Express, *Before and after satellite images document devastation from landslides in Kerala’s Wayanad*: https://indianexpress.com/article/india/satellite-images-document-devastation-from-landslides-in-kerala-wayanad-9489578/
- AGU Landslide Blog, *The 30 July 2024 Wayanad landslides in Kerala, India*: https://eos.org/thelandslideblog/wayanad-landslides

## 3. Problem Statement

Following a major landslide, response teams need to understand where the landscape has changed, which areas may be affected and where further investigation should be prioritised.

Traditional field surveys provide essential confirmation but can be time-consuming and difficult immediately after a disaster. Satellite imagery offers a broader view, although interpreting large images manually can also be challenging.

Key problems include:

1. Identifying new landslide scars, exposed soil and debris deposits.
2. Distinguishing disaster-related changes from normal changes in vegetation, land use and surface conditions.
3. Estimating the area associated with detected changes.
4. Identifying detections close to settlements and important facilities.
5. Prioritising locations for human review and field verification.
6. Communicating results in a format that can be used by disaster management teams and GIS professionals.

TerraWatch AI is designed to assist with these tasks by turning satellite-image comparisons into mapped and ranked candidate changes.

## 4. Proposed Solution: TerraWatch AI

TerraWatch AI is a satellite-based change-detection application that compares a pre-event image with a post-event image covering the same geographical area.

Its purpose is to help users locate changes and decide which locations deserve further investigation.

### 4.1 Core capabilities

**Pre-event and post-event comparison**

The application analyses two images of the same area to identify differences between the earlier and later observations.

**Change polygons**

Detected changes are represented as geographic polygons. Each polygon can include its location, area, severity and other available attributes.

**Severity classification**

Retained changes are organised into High, Medium and Low categories to help users distinguish stronger detections from less prominent ones.

**False-alarm review**

The application can flag or reject candidate changes associated with conditions such as clouds, shadows, vegetation changes or other potential sources of misleading differences, according to its implemented filtering rules.

**Priority ranking**

Detections can be ranked using the application's severity and contextual information, including estimated population exposure and proximity to hospitals, schools or roads where those data are available.

**GIS-compatible export**

Results can be exported to formats such as GeoJSON or GeoPackage for additional analysis in GIS software.

These features are intended to support decision-making, not replace expert interpretation, official damage assessments or field inspections.

## 5. Data and Methodology

### 5.1 Study area and imagery

The case study focuses on the Mundakkai–Chooralmala landslide-affected region of Wayanad, Kerala.

The analysis requires a pair of georeferenced satellite images:

- **Pre-event image:** An image acquired before the landslide.
- **Post-event image:** An image acquired after the landslide.

Both images should cover the same geographical extent and be appropriately co-registered and orthorectified. Differences in image alignment, resolution, acquisition conditions and cloud cover can affect the results.

NRSC/ISRO published a rapid-mapping product using a Cartosat-3 image acquired on 22 May 2023 and post-event imagery from KOMPSAT-5 on 3 August 2024 and Pleiades 1A on 4 August 2024.

These images demonstrate the availability of authoritative pre-event and post-event observations for the disaster. They should not automatically be assumed to be the exact inputs used in the TerraWatch demo.

**Data reference:**  
https://ndem.nrsc.gov.in/documents/Disaster_Document/2024/KL/kllandslide50dsc05082024/kllandslide50dsc05082024_vap1.pdf

### 5.2 Processing workflow

The TerraWatch demonstration follows this general workflow:

1. Load the pre-event and post-event GeoTIFF images.
2. Check that the images cover the same area and have compatible geospatial alignment.
3. Run the application's change-detection engine.
4. Generate candidate change regions.
5. Apply the application's filtering rules to identify and reject potential false alarms.
6. Assign severity levels to retained detections.
7. Calculate the mapped area of detected changes.
8. Associate detections with available contextual layers, such as population estimates, roads and facilities.
9. Rank detections in the priority queue.
10. Export the results for further investigation and validation.

The precise models, thresholds and processing settings should be recorded from the actual TerraWatch implementation if a reproducible technical evaluation is required.

### 5.3 Output metrics

The application produces several useful outputs:

| Metric | Purpose |
|---|---|
| Retained detections | Number of candidate changes remaining after the implemented filtering process |
| Severity distribution | Number of detections categorised as High, Medium or Low |
| Detected area | Sum of the mapped areas of retained change polygons |
| Population estimate | Approximate population associated with the detected locations, based on the application's population-data method |
| Facility proximity | Distance from a detection to available hospitals, schools or roads |
| Priority ranking | Relative order in which detections should be reviewed |
| Rejected detections | Candidate changes excluded by filtering rules, with reasons where available |

These metrics describe the application's analysis outputs. Their usefulness depends on the quality of the imagery, the accuracy of the processing and the reliability of the supporting datasets.

## 6. TerraWatch Wayanad Demo Results

The following values were reported by the TerraWatch application's latest Wayanad demonstration run supplied for this case study.

| Evaluation metric | Reported result |
|---|---:|
| Changes retained | 179 |
| High-severity detections | 19 |
| Total changed area (all 179 kept changes) | Approximately 3.7 km² |
| Largest detection (landslide debris path, ranked #1) | Approximately 1.56 km² (1,556,600 m²), High severity, 94% confidence |
| Estimated population associated with detected areas | Approximately 6,695 people |
| Highest-priority detection | Rank 1 |

**Important:** These figures are application outputs, not independently verified measurements of the real disaster. The retained detections and total area should be checked against the exported analysis results before publication.

### 6.1 Largest detection — approximately 1.56 km²
**Retained changes — 179**

The application's largest retained change, the landslide debris path ranked #1, covers approximately 1.56 km². All 179 retained changes together cover approximately 3.7 km².

A high or low detection count alone does not establish accuracy. Some detections may correspond to landslide-related changes, while others may represent unrelated changes or errors.

**High-severity detections — 19**

Nineteen detections were classified as High severity. These locations can provide an initial shortlist for human review, particularly when they overlap the documented landslide path or occur near settlements and critical infrastructure.

The severity category represents the application's classification and should not be interpreted as a confirmed level of physical damage.

**Total detected area — approximately 1.56 km²**

The application reported approximately 1.56 km² of retained change area.

This figure represents the area calculated from the retained polygons. It should not be described as the total official landslide footprint unless an independent spatial comparison confirms that interpretation.

The application's mapped area and the approximately 86,000 m² of slipped land reported from satellite observations may measure different geographical features or use different boundaries. They should not be directly compared as equivalent measurements without examining the source data and polygons.

**Estimated population — approximately 6,695 people**

The application reported an estimated population associated with detected locations. Such estimates can help identify areas where further investigation may be important.

Population estimates derived from gridded population data do not establish how many people were injured, displaced, rescued or killed. They also depend on how the application defines the affected area and any surrounding buffer.

**Priority ranking**

The priority queue orders detections for investigation. A high-ranked detection may be worth reviewing early because of its severity or proximity to population and facilities.

A priority rank is a decision-support indicator, not a confirmation that a location suffered the greatest real-world damage.
### 6.2 Road access

TerraWatch's blocked-route checker found that the #1 detection (the landslide path) intersects the road to the nearest hospital with **no alternative route** in the OpenStreetMap road network — flagged as a possible blockage to verify on the ground. Across all 179 retained changes, 10 were flagged "no alternative route" and 4 "detour". This is consistent with reports that the affected villages were cut off after the landslide.

## 7. Comparison with Authoritative Evidence

The real Wayanad event provides an opportunity to compare TerraWatch outputs with independently documented changes.

| Evaluation aspect | Independent reference | TerraWatch output to examine |
|---|---|---|
| Landslide location | NRSC/ISRO rapid-mapping product | Whether detections overlap the documented source area |
| Debris-flow path | Satellite observations and published event records | Whether polygons follow the affected slope and downstream corridor |
| Surface disturbance | Pre-event and post-event satellite images | Whether the application identifies new exposed surfaces |
| Built-up areas | Published damage reports and suitable reference imagery | Whether detections correspond to documented settlement changes |
| Potential false alarms | Cloud, shadow, vegetation and image-quality information | Whether rejected candidates have plausible explanations |
| Prioritisation | Location of settlements and available infrastructure | Whether ranked detections highlight useful locations for review |

This comparison is a proposed validation framework. The supplied demo metrics alone do not establish that TerraWatch successfully identified every reference feature or achieved a particular accuracy level.

### 7.1 How to perform spatial validation

For a stronger evaluation:

1. Obtain the authoritative NRSC/ISRO landslide impact map or a suitable reference polygon.
2. Export TerraWatch's retained change polygons.
3. Load both datasets into QGIS or another GIS application.
4. Ensure that both layers use compatible coordinate reference systems.
5. Overlay the detected polygons on the reference data.
6. Inspect detections inside, partially overlapping and outside the reference footprint.
7. Investigate possible causes of missed detections and false positives.
8. Calculate suitable accuracy metrics if a reliable reference mask and clearly defined evaluation procedure are available.

Possible metrics include precision, recall, F1 score and intersection over union (IoU). These should only be reported after the necessary spatial comparisons have been performed.

For example:

- **Precision** measures how many evaluated positive detections are correct.
- **Recall** measures how much of the reference landslide area is successfully detected.
- **Intersection over union** measures the overlap between the predicted and reference areas.

No numerical accuracy score is claimed in this case study because the necessary validation measurements have not been provided.

## 8. Practical Applications

TerraWatch's outputs could support several activities during disaster assessment.

### 8.1 Rapid identification of affected areas

Mapped change polygons can help analysts identify locations requiring further inspection, especially across large areas where ground access is difficult.

### 8.2 Field-team planning

Priority rankings and geographic coordinates can help response teams prepare inspection routes and investigate selected locations.

### 8.3 Infrastructure assessment

Proximity information can help identify candidate changes near roads, schools, hospitals and settlements. Proximity alone does not establish that a facility has been damaged or is inaccessible.

### 8.4 GIS reporting

GeoJSON and GeoPackage exports can allow analysts to inspect the results alongside other geographical datasets, create maps and prepare follow-up reports.

### 8.5 Future risk monitoring

Repeated satellite observations may help planners monitor landscape changes in areas susceptible to landslides. Identifying a change, however, is different from predicting when a future landslide will occur.

## 9. Limitations and Risks

### 9.1 Image quality and alignment

Differences in spatial resolution, image alignment, acquisition dates and illumination can create misleading detections. Both images should be checked before interpreting the output.

### 9.2 Cloud cover and weather conditions

Optical satellite imagery may be obscured by clouds. Radar imagery can provide useful observations under cloudy conditions, but it has different interpretation requirements and may introduce its own sources of uncertainty.

### 9.3 False positives and missed changes

Vegetation cycles, shadows, water-level changes, land preparation and image artefacts may resemble disaster-related changes. Conversely, genuine changes may be missed because of image quality, model limitations or filtering thresholds.

### 9.4 Population estimates

Population estimates are approximate and depend on the population dataset, spatial resolution and method used to associate people with detected areas. They must not be presented as casualty counts.

### 9.5 Interpretation of severity

A severity label indicates the application's assessment of a candidate change. It does not automatically represent structural damage, the depth of debris or the number of affected people.

### 9.6 Need for human verification

TerraWatch should be treated as a decision-support system. Official disaster information, expert assessment and field verification remain essential before decisions affecting people, infrastructure or public resources are made.

## 10. Recommendations for Further Evaluation

The following improvements would strengthen the Wayanad case study:

1. Record the exact acquisition dates, sensor names, spatial resolutions and data sources used in the demo.
2. Preserve the exported detection polygons and the application's quality report.
3. Include screenshots showing the pre-event image, post-event image and detected changes.
4. Compare the outputs against an authoritative reference footprint.
5. Measure precision, recall and spatial overlap where suitable reference data are available.
6. Review false positives and missed areas manually.
7. Record the population dataset and the precise method used to calculate population estimates.
8. Repeat the evaluation on additional disaster events to test whether the results generalise beyond Wayanad.
9. Document processing settings so that the evaluation can be reproduced.
10. Include a clear statement of uncertainty in reports shared with disaster response teams.

## 11. Conclusion

The Wayanad landslides of 30 July 2024 provide a relevant real-world scenario for evaluating satellite-based change detection.

TerraWatch AI's demonstration produces mapped candidate changes, severity categories, area estimates, population context and a priority queue. These outputs could help analysts organise the review of satellite observations and identify locations for further investigation.

The reported demo results—179 retained changes, 19 high-severity detections,approximately 3.7 km² of retained change area, with the largest detection (the landslide path) covering about 1.56 km² and an estimated population of approximately 6,695—describe the application's current outputs rather than independently confirmed disaster impacts.

The next important step is spatial validation against authoritative reference data, supported by careful image-quality checks and, where possible, field observations.

With transparent validation, reproducible processing and appropriate human oversight, TerraWatch could serve as a useful component of a broader disaster-assessment workflow.

## 12. References

1. **National Remote Sensing Centre (NRSC)/ISRO.** Landslide Impact Map: Chooralmala, Wayanad, Kerala, India. Charter Call 1029.  
   https://ndem.nrsc.gov.in/documents/Disaster_Document/2024/KL/kllandslide50dsc05082024/kllandslide50dsc05082024_vap1.pdf

2. **International Consortium on Landslides.** Mundakkai Landslide, Wayanad. Event record containing location, event characteristics and reported impacts.  
   https://www.landslides.org/report/mundakkai-landslide-wayanad/

3. **National Disaster Response Force (NDRF).** Landslide in Wayanad, Kerala.  
   https://www.ndrf.gov.in/en/operations/landslide-wayanad-kerala

4. **The Indian Express.** Before and after satellite images document devastation from landslides in Kerala’s Wayanad. 1 August 2024.  
   https://indianexpress.com/article/india/satellite-images-document-devastation-from-landslides-in-kerala-wayanad-9489578/

5. **American Geophysical Union (AGU), The Landslide Blog.** The 30 July 2024 Wayanad landslides in Kerala, India.  
   https://eos.org/thelandslideblog/wayanad-landslides

6. **National Remote Sensing Centre (NRSC)/ISRO.** Landslide Atlas of India.  
   https://www.nrsc.gov.in/nrscnew/resources_atlas_landslide.php

7. **Nature, Scientific Reports.** Mundakkai-Chooralmala landslide: assessment of initiation, progression, and impact.  
   https://www.nature.com/articles/s41598-025-07828-3

8. **ScienceDirect.** Preliminary analysis of the July 30, 2024, Wayanad landslide disaster in India: Causes and impacts.  
   https://doi.org/10.1016/j.nhres.2025.04.005


