import type { FeatureCollection } from "geojson";

export const API_BASE = "http://127.0.0.1:8000";

export interface Bounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

export type EngineChoice = "auto" | "tinycd" | "engine2" | "spectral";

export interface QualityReport {
  before_cloud_pct: number;
  after_cloud_pct: number;
  cloud_method: string;
  misalignment_px: number;
  resolution_m: number;
  band_count: number;
  engine: string | null;
  warnings: string[];
}

export interface AnalysisStatus {
  id: string;
  mode: string;
  status: "pending" | "ready" | "failed";
  progress_step: string;
  progress_steps: string[];
  error_message: string | null;
  bounds: Bounds | null;
  engine_choice: EngineChoice;
  engine: string | null;
  engine_key: string | null;
  engine_fell_back: boolean;
  pixel_size_m: number | null;
  polygon_count: number;
  kept_count: number;
  rejected_count: number;
  reject_reason_counts: Record<string, number>;
  summary_line: string | null;
  population_available: boolean;
  total_population_buffer_est: number | null;
  near_facility_count: number | null;
  hazard_zone_geojson: string | null;
  quality_report: QualityReport | null;
  created_at: string;
}

export async function createAnalysis(
  before: File,
  after: File,
  mode: string,
  engine: EngineChoice = "auto",
  hazardZoneGeojson?: string | null,
): Promise<{ analysis_id: string }> {
  const form = new FormData();
  form.append("before", before);
  form.append("after", after);
  form.append("mode", mode);
  form.append("engine", engine);
  if (hazardZoneGeojson) form.append("hazard_zone", hazardZoneGeojson);

  const res = await fetch(`${API_BASE}/api/analyses`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Upload failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

export async function getAnalysis(id: string): Promise<AnalysisStatus> {
  const res = await fetch(`${API_BASE}/api/analyses/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch analysis: ${res.status}`);
  }
  return res.json();
}

export function imageryUrl(id: string, which: "before" | "after" | "population"): string {
  return `${API_BASE}/api/analyses/${id}/imagery/${which}`;
}

export function polygonsUrl(id: string): string {
  return `${API_BASE}/api/analyses/${id}/polygons`;
}

export function exportUrl(id: string, format: "geojson" | "gpkg"): string {
  return `${API_BASE}/api/analyses/${id}/export?format=${format}`;
}

export interface FacilityPoint {
  lat: number;
  lon: number;
  name: string;
}

export interface RoadLine {
  name: string;
  highway: string;
  coords: [number, number][];
}

export interface FacilitiesData {
  hospitals: FacilityPoint[];
  schools: FacilityPoint[];
  shelters: FacilityPoint[];
  roads: RoadLine[];
}

export function populationOverlayUrl(id: string): string {
  return imageryUrl(id, "population");
}

export async function getFacilities(id: string): Promise<FacilitiesData> {
  const res = await fetch(`${API_BASE}/api/analyses/${id}/facilities`);
  if (!res.ok) {
    throw new Error(`Failed to fetch facilities: ${res.status}`);
  }
  return res.json();
}

export interface PriorityWeights {
  w1_severity: number;
  w2_population: number;
  w3_facility_proximity: number;
  w4_confidence: number;
  w5_route_impact: number;
}

export async function getPriorityWeights(): Promise<PriorityWeights> {
  const res = await fetch(`${API_BASE}/api/settings/weights`);
  if (!res.ok) throw new Error(`Failed to fetch weights: ${res.status}`);
  return res.json();
}

export async function setPriorityWeights(weights: Partial<PriorityWeights>): Promise<PriorityWeights> {
  const res = await fetch(`${API_BASE}/api/settings/weights`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(weights),
  });
  if (!res.ok) throw new Error(`Failed to save weights: ${res.status}`);
  return res.json();
}

export async function applyHazardZone(
  id: string,
  polygon: GeoJSON.Polygon,
): Promise<{ status: string; in_hazard_zone_count: number }> {
  const res = await fetch(`${API_BASE}/api/analyses/${id}/hazard_zone`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ geojson: polygon }),
  });
  if (!res.ok) {
    throw new Error(`Failed to apply hazard zone: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

export async function getPolygons(id: string): Promise<FeatureCollection> {
  const res = await fetch(polygonsUrl(id));
  if (!res.ok) {
    throw new Error(`Failed to fetch polygons: ${res.status}`);
  }
  return res.json();
}

export async function pollUntilReady(
  id: string,
  onProgress?: (status: AnalysisStatus) => void,
  intervalMs = 800,
  timeoutMs = 180000,
): Promise<AnalysisStatus> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const status = await getAnalysis(id);
    onProgress?.(status);
    if (status.status === "ready" || status.status === "failed") {
      return status;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Timed out waiting for analysis to complete");
}
