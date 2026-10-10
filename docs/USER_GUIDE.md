# TerraWatch AI — User Guide

## 1. Introduction

TerraWatch AI is a satellite change-detection and geospatial decision-support application designed to help disaster-response teams and urban planners identify possible changes on the ground.

The application compares satellite images from two different dates, detects candidate changes, filters likely false alarms, measures the detected regions, and helps prioritize areas for further inspection.

**Primary use cases:**
- **Disaster response:** Identify and prioritize areas potentially affected by events such as landslides.
- **Prevention:** Flag possible new construction within designated hazard-prone areas for investigation.

TerraWatch supports decision-making. Its detections do not independently confirm physical damage, illegal construction, or immediate danger.

## 2. Who Can Use TerraWatch?

- Disaster-management officials who need to prioritize areas for inspection.
- Urban planners who monitor construction near hazard-prone zones.
- GIS analysts who examine and export geospatial change data.
- NGOs and field teams supporting disaster assessment and recovery.

## 3. Requirements Before Starting

Before performing an analysis, the user should have:

- A satellite image of the area from an earlier date.
- A satellite image of the same area from a later date.
- GeoTIFF files containing the required geographic information.
- Compatible imagery with suitable spatial coverage, resolution, and bands.
- A running TerraWatch frontend and backend.

The two images should cover the same geographic region and be suitable for comparison. Poor image quality, clouds, or misalignment can reduce the reliability of the results.

## 4. How to Use TerraWatch

### Step 1: Open the application

Start the TerraWatch application and open the analysis interface.

The main interface provides the controls for selecting satellite images, choosing the analysis mode and engine, and starting an analysis.


### Step 2: Upload the before image

Select the GeoTIFF image representing the area before the event or construction change.

For example, a disaster-response team investigating a landslide could select an image captured before the landslide occurred.

### Step 3: Upload the after image

Select the GeoTIFF image representing the same area at a later date.

The system compares the two images to identify possible changes.

### Step 4: Select the analysis mode

**Disaster mode**

Use this mode when investigating a possible disaster impact, such as a landslide. The goal is to identify candidate affected regions and support inspection prioritization.

**Prevention mode**

Use this mode to investigate possible new construction in designated hazard zones. A flagged structure should be treated as a candidate requiring further verification, not as automatic proof of illegal encroachment.

### Step 5: Select the detection engine

If the interface provides engine selection, choose an available engine or use automatic selection when appropriate.

The intended options include:

- **TinyCD:** A deep-learning change-detection model associated with high-resolution imagery.
- **U-Net:** A neural-network segmentation approach intended for compatible satellite imagery.
- **Spectral baseline:** A simpler image-comparison method.
- **Auto:** Allows the application to select an available engine according to its configured selection logic.

Engine compatibility depends on the model's supported resolution, bands, input format, preprocessing, and availability of trained weights.

### Step 6: Run the analysis

Click **Run analysis** to submit the image pair for processing.

The intended workflow includes image-quality checks, alignment, change detection, filtering, polygon generation, and preparation of the results.

If processing fails, check the displayed error and confirm that the backend is running, the API endpoints are correctly configured, and the input files meet the application's requirements.


### Step 7: Examine the map

After a successful analysis, use the map to inspect the before-and-after imagery and the detected regions.

Where supported by the current application, users can examine polygon boundaries and open individual detections to review their attributes.

Do not assume that every highlighted region represents confirmed damage. Some differences may be caused by clouds, shadows, vegetation, or image-quality problems.



### Step 8: Review detection details

For each available detection, examine the attributes provided by the application, such as:

- Geographic location or centroid.
- Estimated area in square metres.
- Change magnitude or severity.
- Estimated change type.
- Confidence or review status, when available.
- False-alarm or rejection reason, when available.

The exact attributes depend on the analysis result and the features implemented in the running version.

### Step 9: Examine the priority queue

Where prioritization is available, review the ranking and its explanation.

The intended priority workflow considers detected changes alongside contextual information, such as estimated population and proximity to hospitals, schools, or roads.

Use the ranking to decide which locations may deserve earlier investigation. A high ranking is a recommendation for attention, not proof of damage or danger.

Population values are estimates, and mapped infrastructure may be incomplete or outdated.

### Step 10: Export the results

Where export functionality is available, users can export geospatial results in supported formats:

- **GeoJSON:** Useful for web mapping, data exchange, and compatible GIS applications.
- **GeoPackage:** Useful for packaging geospatial data for GIS workflows.

The exported results can be opened in compatible tools such as QGIS or ArcGIS. Confirm that the exported file opens correctly and that its coordinate reference system and attributes are preserved.

## 5. Understanding False Alarms

Satellite-image differences do not always indicate real changes. TerraWatch's intended filtering stage checks for several possible sources of false alarms.

| Flag | Meaning |
|---|---|
| Cloud | Cloud contamination may obscure the ground in one of the images. |
| Seasonal vegetation | Vegetation may change between image dates. |
| Shadow or illumination | Differences in lighting or shadows may affect the imagery. |
| Too small | The detected region is below the configured minimum area. |
| Misalignment edge | Image misalignment may create misleading boundary detections. |

A rejection reason explains why the system flagged a region. It does not guarantee that the region is genuinely unchanged. Important detections and uncertain cases should be reviewed before action is taken.

## 6. Interpreting Results Responsibly

Users should remember the following limitations:

1. **Change does not equal damage.** A detected difference does not establish the cause or physical impact.
2. **Resolution matters.** Small structures may be difficult to detect in coarse-resolution imagery.
3. **Clouds can hide information.** Missing observations should not be interpreted as evidence that no change occurred.
4. **Population is estimated.** Gridded population data may not reflect the number of people actually present during an event.
5. **Infrastructure data may be incomplete.** A missing mapped hospital or road does not prove that the facility or road does not exist.
6. **Human verification remains necessary.** Critical decisions should use independent observations and field assessment wherever possible.

## 7. Troubleshooting

### Upload failed: 404 Not Found

A 404 response usually indicates that the requested API route does not exist on the running backend.

Check that the frontend and backend use matching API endpoints and that the backend version corresponds to the frontend version.

### Backend is unavailable

Confirm that the backend server is running and that the configured API address and port are correct.

### Analysis produces unexpected detections

Check the imagery's geographic alignment, resolution, cloud cover, band configuration, and quality warnings. Review the selected engine and its compatibility with the input data.

### No detections appear

This does not necessarily mean no real changes occurred. The model may have missed changes, the input quality may be poor, or filtering thresholds may have removed candidate regions.

### Export fails

Confirm that processing completed successfully and that the selected export format is supported for the current analysis.

## 8. Recommended Workflow for Disaster Response

1. Obtain suitable before-and-after imagery for the affected region.
2. Run the analysis and review image-quality warnings.
3. Examine the detected regions and their rejection reasons.
4. Review the priority queue and available population and infrastructure context.
5. Select candidate locations for field inspection.
6. Verify important detections using independent evidence.
7. Export the results for GIS analysis and reporting.
8. Record field findings to support subsequent review and improvement.

## 9. Conclusion

TerraWatch AI aims to make satellite change detection more interpretable and actionable by combining AI-based detection, geospatial measurements, false-alarm explanations, and contextual prioritization.

Its role is to help users identify candidate changes and decide where to investigate first. Reliable operational decisions still require suitable imagery, validated analysis, and human verification.
