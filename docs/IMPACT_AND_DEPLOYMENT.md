# Impact and Deployment Plan

## 1. The Problem in India

India faces recurring landslides in the Western Ghats and Himalayas, monsoon flooding across multiple states, and urban expansion that can increase exposure to hazards when development occurs near rivers or on unstable slopes. After a disaster, comparing satellite imagery from before and after an event can help identify areas that have changed. Manually reviewing large areas is time-consuming, while clouds, seasonal vegetation, shadows, and differences between image dates can produce false detections.

The 30 July 2024 Mundakkai landslide in Wayanad, Kerala, illustrates the importance of timely and reliable information. The International Consortium on Landslides reports 251 deaths and 47 people missing in its event report. These are reported disaster-impact figures, not estimates produced by TerraWatch.

Source: [International Consortium on Landslides — Mundakkai Landslide, Wayanad](https://www.landslides.org/report/mundakkai-landslide-wayanad/)

TerraWatch aims to support disaster response and land monitoring by comparing before-and-after satellite imagery, identifying candidate areas of change, and presenting geospatial results for human review. Change detection alone cannot confirm damage, determine its cause, or establish the need for rescue.

## 2. Who Uses TerraWatch?

### State Disaster Management Authorities (SDMAs)

SDMAs could use TerraWatch to review candidate changes across affected districts after a disaster. Ranked results and available contextual layers could help officials identify locations for further assessment. All findings would require validation against authoritative information and field reports.

### District Disaster Management Cells

District teams could use mapped change candidates to organise verification visits, coordinate with local authorities, and share locations with response teams. Population and nearby-facility information would be treated as estimates or contextual indicators, not confirmed counts or proof of accessibility.

### Municipal Planners

Municipal planning teams, including those in Pune, could explore using TerraWatch to monitor land-use changes near mapped flood-prone areas, river corridors, and landslide-susceptible slopes. Potential encroachment or construction would be flagged for verification, not automatically labelled illegal. Planning decisions would depend on authoritative hazard maps, applicable regulations, and human review.

### NGOs and Relief Organisations

NGOs and relief organisations could use exported maps and geographic files to communicate candidate affected locations to field teams. Shared locations would support coordination only after appropriate verification and responsible handling of sensitive information.

### Researchers and Students

Researchers and students could use TerraWatch to study geospatial change detection, inspect candidate polygons, and evaluate results against reference data. Reproducible evaluations and clearly documented limitations would support transparent assessment.

## 3. Proposed Pilot and Deployment Plan

The following phases are a proposed deployment pathway, not confirmed government partnerships or completed deployments.

### Phase 1: District Pilot (Approximately 3–6 Months)

**Scope:** One landslide-prone district in Kerala, such as Wayanad, and one flood or urban-growth study area in Maharashtra, such as Pune.

**Requirements:**
- Suitable satellite imagery and relevant geographic datasets.
- A laptop or appropriately sized cloud server.
- Trained users in each pilot area.
- Baseline evaluation using suitable reference data.
- Feedback from field verification and local stakeholders.

### Phase 2: State-Level Expansion

**Scope:** Extend the system to additional high-risk districts in the two pilot states.

**Requirements:**
- Official hazard-zone and administrative maps.
- Repeatable satellite-image processing.
- Data-quality checks and monitoring.
- User training and an agreed process for reviewing alerts.
- Evaluation across different geographical and seasonal conditions.

### Phase 3: National Expansion

**Scope:** Explore integration with national disaster-management and geospatial workflows.

**Requirements:**
- Standard geographic data formats such as GeoJSON and GeoPackage.
- Documented interfaces and integration requirements.
- Security, privacy, and data-governance reviews.
- Scalable infrastructure and a technical support process.
- Training materials and ongoing performance evaluation.
## 4. Cost and Infrastructure

### Data

The project can use publicly accessible datasets, subject to their individual licences and conditions.

- **Sentinel-2:** Optical satellite imagery available through the Copernicus Data Space Ecosystem. Sentinel-2 includes bands at different spatial resolutions, including 10-metre bands. Clouds and acquisition timing can affect suitability for a particular analysis. [Copernicus Sentinel-2](https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-2)
- **OpenStreetMap:** Open geographic data covering roads, buildings, and other features. It is distributed under the Open Database License, subject to attribution and other applicable obligations. Coverage varies by location. [OpenStreetMap Copyright and Licence](https://www.openstreetmap.org/copyright)
- **WorldPop:** Gridded population datasets that can support approximate population-exposure analysis. Dataset-specific documentation, assumptions, and attribution requirements should be checked before use. [WorldPop](https://www.worldpop.org/)
- **Copernicus DEM:** Elevation data that may support terrain analysis, subject to product terms and suitability. [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/)

These data sources generally offer access without a purchase fee, but access conditions, attribution, licences, storage, processing, and service limits still apply.

### Software and Compute

TerraWatch uses an open-source-oriented technology stack, including Python, PyTorch, FastAPI, React, and MapLibre. The absence of paid software licences does not mean every deployment is cost-free.

A laptop may be sufficient for small demonstration datasets. Larger areas, frequent processing, or multiple concurrent users may require a cloud or institutional server. Costs depend on imagery volume, compute requirements, storage, network transfer, monitoring, and maintenance.

## 5. Fit With Existing GIS Workflows

TerraWatch is intended to complement existing geographic information systems rather than replace them. Where supported by the current implementation, results can be exported as GeoJSON or GeoPackage for inspection in QGIS and ArcGIS.

Depending on the available output fields, results may include candidate geometry, change area, a change-severity indicator, estimated change category, confidence information, population estimate, nearby facilities, priority, and an explanation for rejection by a filtering step.

Compatibility with a particular government GIS portal must be verified separately. Integration may require agreed schemas, coordinate reference systems, authentication, metadata, and data-sharing permissions.

## 6. Risks and Safeguards

| Risk | Safeguard |
|---|---|
| False alarms from clouds, shadows, seasonal vegetation, or image misalignment | Display image dates and quality information, explain filtering decisions where supported, and retain evidence for review. |
| Overconfidence in population or facility estimates | Label population figures as estimates, document source limitations, and avoid presenting estimates as verified counts. |
| Confusing change severity with disaster damage | Explain that severity describes the detected strength of change, not confirmed damage or human impact. |
| Decisions based solely on automated output | Include clear “verify on ground” guidance. TerraWatch supports, rather than replaces, professional judgement and official assessments. |
| Missing or incomplete data | Report unavailable imagery and relevant quality issues. Document gaps in OpenStreetMap and other datasets rather than assuming missing features do not exist. |
| Privacy and sensitive location data | Design the workflow for land-surface change analysis rather than individual identification. Avoid collecting personal information unnecessarily, restrict access where appropriate, and apply relevant privacy and data-governance requirements. |

Satellite imagery and derived maps should not be described as guaranteeing anonymity. Resolution alone is not a complete privacy safeguard, and derived outputs may still reveal sensitive information about locations or infrastructure.

## 7. Proposed Future Roadmap

The following items are proposed enhancements. Their inclusion here does not mean they are implemented or validated in the current submission.

1. **Automatic area and date selection:** Enable users to request analysis for a selected location and time period across India, with clear reporting when suitable imagery is unavailable.
2. **All-weather monitoring:** Explore Sentinel-1 radar imagery to improve monitoring during cloudy monsoon conditions and at night. Radar requires different processing and validation from optical imagery and does not guarantee detection of every type of change.
3. **Blocked-route assessment:** Explore route-network analysis to identify potentially disrupted connections between villages and facilities such as hospitals. A mapped route must not be presented as passable without current verification.
4. **Multilingual field reports:** Support field reporting in English, Hindi, and Marathi, with clear location references and verification status.
5. **Watch-area alerts:** Provide notifications when new, suitable satellite observations produce candidate changes in selected areas, with quality checks and human review.
6. **Learning from field feedback:** Establish a documented evaluation process using verified field observations to assess errors and improve the system responsibly.

Progress on these enhancements should be measured through documented tests, transparent limitations, and feedback from intended users.

## References

1. International Consortium on Landslides. “Mundakkai Landslide, Wayanad.” https://www.landslides.org/report/mundakkai-landslide-wayanad/
2. Copernicus Data Space Ecosystem. “Sentinel-2.” https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-2
3. OpenStreetMap Foundation. “Copyright and License.” https://www.openstreetmap.org/copyright
4. WorldPop. https://www.worldpop.org/
5. Copernicus Data Space Ecosystem. https://dataspace.copernicus.eu/
