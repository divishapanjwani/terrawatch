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

export interface SceneMeta {
  date: string;
  cloud_cover: number;
  item_id?: string;
}

export interface FetchMeta {
  bbox: [number, number, number, number];
  before_scene: SceneMeta;
  after_scene: SceneMeta;
  place: string | null;
}

export interface AnalysisStatus {
  id: string;
  mode: string;
  status: "pending" | "ready" | "failed";
  progress_step: string;
  progress_steps: string[];
  is_auto_fetch: boolean;
  fetch_meta: FetchMeta | null;
  case_study_slug: string | null;
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

export interface FetchParams {
  place?: string;
  bbox?: [number, number, number, number];
  beforeDateRange: string;
  afterDateRange: string;
  maxCloud?: number;
  mode: string;
  engine?: EngineChoice;
}

export async function fetchAnalysis(params: FetchParams): Promise<{ analysis_id: string }> {
  const form = new FormData();
  if (params.place) form.append("place", params.place);
  if (params.bbox) form.append("bbox", params.bbox.join(","));
  form.append("before_date_range", params.beforeDateRange);
  form.append("after_date_range", params.afterDateRange);
  form.append("max_cloud", String(params.maxCloud ?? 20));
  form.append("mode", params.mode);
  form.append("engine", params.engine ?? "auto");

  const res = await fetch(`${API_BASE}/api/analyses/fetch`, { method: "POST", body: form });
  if (!res.ok) {
    throw new Error(`Fetch failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

export interface CaseStudy {
  slug: string;
  name: string;
  location: string;
  event_date: string;
  category: string;
  description: string;
  bbox: [number, number, number, number] | null;
  known_scenes: { before: SceneMeta; after: SceneMeta } | null;
  thumbnail_url: string;
  cached: boolean;
}

export async function listCaseStudies(): Promise<CaseStudy[]> {
  const res = await fetch(`${API_BASE}/api/case_studies`);
  if (!res.ok) throw new Error(`Failed to list case studies: ${res.status}`);
  return res.json();
}

export async function loadCaseStudy(
  slug: string,
  mode: string,
  engine: EngineChoice = "auto",
): Promise<{ analysis_id: string }> {
  const res = await fetch(
    `${API_BASE}/api/case_studies/${slug}/load?mode=${mode}&engine=${engine}`,
    { method: "POST" },
  );
  if (!res.ok) {
    throw new Error(`Failed to load case study: ${res.status} ${await res.text()}`);
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

export type ReportLang = "en" | "hi" | "mr";

export function reportUrl(id: string, format: "pdf" | "html", lang: ReportLang): string {
  return `${API_BASE}/api/analyses/${id}/report?format=${format}&lang=${lang}`;
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

export interface PolygonRoute {
  status: "ok" | "unknown";
  route_impact: "none" | "detour" | "no_alternative" | "unknown";
  detour_m: number | null;
  hospital_name?: string;
  original_path: [number, number][] | null;
  detour_path: [number, number][] | null;
  reason?: string;
}

export async function getPolygonRoute(id: string, polygonId: string): Promise<PolygonRoute> {
  const res = await fetch(`${API_BASE}/api/analyses/${id}/polygons/${polygonId}/route`);
  if (!res.ok) {
    throw new Error(`Failed to fetch route: ${res.status} ${await res.text()}`);
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
