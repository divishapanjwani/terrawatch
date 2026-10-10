import { useEffect, useRef, useState } from "react";
import type { MapGeoJSONFeature } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import { AlertTriangle, Cpu, Hospital, Landmark, MapPin, Route, X } from "lucide-react";
import "./styles/tokens.css";
import "./styles/design-system.css";
import "./App.css";
import CompareMap from "./map/CompareMap";
import FileDropSlot from "./panels/FileDropSlot";
import PolygonPanel from "./panels/PolygonPanel";
import PriorityPanel from "./panels/PriorityPanel";
import AccuracyPage from "./pages/AccuracyPage";
import CaseStudiesPage from "./pages/CaseStudiesPage";
import SettingsPage from "./pages/SettingsPage";
import TopBar from "./components/TopBar";
import LeftRail from "./components/LeftRail";
import type { RailPage } from "./components/LeftRail";
import CollapsibleSection from "./components/CollapsibleSection";
import Switch from "./components/Switch";
import Hero from "./components/Hero";
import ProcessingCard from "./components/ProcessingCard";
import KpiStrip from "./components/KpiStrip";
import {
  applyHazardZone,
  createAnalysis,
  fetchAnalysis,
  getFacilities,
  getPolygonRoute,
  getPolygons,
  imageryUrl,
  loadCaseStudy,
  pollUntilReady,
  populationOverlayUrl,
} from "./api/client";
import type { AnalysisStatus, EngineChoice, FacilitiesData } from "./api/client";
import type { RouteDisplay } from "./map/CompareMap";
import BboxDrawMap from "./map/BboxDrawMap";
import type { Bbox } from "./map/BboxDrawMap";

const FETCH_MAX_BBOX_SIDE_DEG = 0.25; // mirrors backend/app/config.py's FETCH_MAX_BBOX_SIDE_DEG

type AppState =
  | { phase: "empty" }
  | { phase: "uploading" }
  | { phase: "processing"; id: string; step: string; steps: string[] }
  | { phase: "ready"; analysis: AnalysisStatus; geojson: FeatureCollection }
  | { phase: "error"; message: string };

const ENGINE_OPTIONS: { value: EngineChoice; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "tinycd", label: "TinyCD" },
  { value: "engine2", label: "Engine 2" },
  { value: "spectral", label: "Spectral baseline" },
];

export default function App() {
  const [page, setPage] = useState<RailPage>("analysis");
  const [state, setState] = useState<AppState>({ phase: "empty" });
  const [beforeFile, setBeforeFile] = useState<File | null>(null);
  const [afterFile, setAfterFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"disaster" | "prevention">("disaster");
  const [engine, setEngine] = useState<EngineChoice>("auto");
  const [selected, setSelected] = useState<MapGeoJSONFeature | null>(null);
  const [showRejected, setShowRejected] = useState(false);
  const [zoomToId, setZoomToId] = useState<string | null>(null);
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [rightPanelTab, setRightPanelTab] = useState<"priority" | "details">("priority");
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [showPopulation, setShowPopulation] = useState(false);
  const [showFacilities, setShowFacilities] = useState(false);
  const [showRoads, setShowRoads] = useState(false);
  const [facilities, setFacilities] = useState<FacilitiesData | null>(null);
  const [drawMode, setDrawMode] = useState(false);
  const [hazardZone, setHazardZone] = useState<GeoJSON.Polygon | null>(null);
  const [hazardZoneStatus, setHazardZoneStatus] = useState<string | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);
  const [fetchPlace, setFetchPlace] = useState("");
  const [fetchBeforeRange, setFetchBeforeRange] = useState("2024-01-01/2024-04-30");
  const [fetchAfterRange, setFetchAfterRange] = useState("2024-07-01/2024-12-31");
  const [fetchMaxCloud, setFetchMaxCloud] = useState(20);
  const [fetchLoading, setFetchLoading] = useState(false);
  const [fetchBbox, setFetchBbox] = useState<Bbox | null>(null);
  const [showBboxDraw, setShowBboxDraw] = useState(false);
  const [caseStudyLoadingSlug, setCaseStudyLoadingSlug] = useState<string | null>(null);
  const [routeDisplay, setRouteDisplay] = useState<RouteDisplay | null>(null);

  const [openSections, setOpenSections] = useState({
    analysis: true,
    engine: true,
    layers: true,
    quality: true,
  });
  function toggleSection(key: keyof typeof openSections) {
    setOpenSections((s) => ({ ...s, [key]: !s[key] }));
  }
  const analysisSectionRef = useRef<HTMLDivElement>(null);
  const layersSectionRef = useRef<HTMLDivElement>(null);
  const leftPanelRef = useRef<HTMLDivElement>(null);

  async function handleDrawComplete(polygon: GeoJSON.Polygon | null) {
    setDrawMode(false);
    if (!polygon || state.phase !== "ready") return;
    setHazardZone(polygon);
    setHazardZoneStatus("Applying hazard zone…");
    try {
      const { in_hazard_zone_count } = await applyHazardZone(state.analysis.id, polygon);
      const geojson = await getPolygons(state.analysis.id);
      setState({ phase: "ready", analysis: state.analysis, geojson });
      setSelected((prev) => {
        if (!prev) return prev;
        const updated = geojson.features.find(
          (f) => String(f.properties?.id) === String(prev.properties?.id),
        );
        return (updated as unknown as MapGeoJSONFeature) ?? prev;
      });
      setHazardZoneStatus(
        in_hazard_zone_count > 0
          ? `${in_hazard_zone_count} new-construction polygon(s) flagged in the hazard zone.`
          : "No new-construction polygons fall inside this zone.",
      );
    } catch (err) {
      setHazardZoneStatus(`Failed to apply hazard zone: ${(err as Error).message}`);
    }
  }

  function handleSelectFromPriority(id: string) {
    if (state.phase !== "ready") return;
    const feature = state.geojson.features.find((f) => String(f.properties?.id) === id);
    if (!feature) return;
    setSelected(feature as unknown as MapGeoJSONFeature);
    setZoomToId(id);
    setRightPanelTab("details");
  }

  async function trackAnalysis(start: () => Promise<{ analysis_id: string }>) {
    setSelected(null);
    setFacilities(null);
    setHazardZone(null);
    setHazardZoneStatus(null);
    setDrawMode(false);
    setRightPanelTab("priority");
    setState({ phase: "uploading" });
    try {
      const { analysis_id } = await start();
      setState({ phase: "processing", id: analysis_id, step: "validating", steps: [] });
      const analysis = await pollUntilReady(analysis_id, (status) => {
        setState({
          phase: "processing",
          id: analysis_id,
          step: status.progress_step,
          steps: status.progress_steps,
        });
      });
      if (analysis.status === "failed") {
        setState({ phase: "error", message: analysis.error_message ?? "Analysis failed" });
      } else {
        const geojson = await getPolygons(analysis_id);
        setState({ phase: "ready", analysis, geojson });
        getFacilities(analysis_id)
          .then(setFacilities)
          .catch(() => setFacilities(null));
      }
    } catch (err) {
      setState({ phase: "error", message: (err as Error).message });
    }
  }

  async function runAnalysis(before: File, after: File) {
    await trackAnalysis(() => createAnalysis(before, after, mode, engine));
  }

  async function handleSubmit() {
    if (!beforeFile || !afterFile) return;
    await runAnalysis(beforeFile, afterFile);
  }

  async function handleFetchSubmit() {
    if (!fetchBbox && !fetchPlace.trim()) return;
    if (
      fetchBbox &&
      (fetchBbox[2] - fetchBbox[0] > FETCH_MAX_BBOX_SIDE_DEG ||
        fetchBbox[3] - fetchBbox[1] > FETCH_MAX_BBOX_SIDE_DEG)
    )
      return;
    setFetchLoading(true);
    try {
      await trackAnalysis(() =>
        fetchAnalysis({
          ...(fetchBbox ? { bbox: fetchBbox } : { place: fetchPlace.trim() }),
          beforeDateRange: fetchBeforeRange,
          afterDateRange: fetchAfterRange,
          maxCloud: fetchMaxCloud,
          mode,
          engine,
        }),
      );
    } finally {
      setFetchLoading(false);
    }
  }

  async function handleLoadCaseStudy(slug: string) {
    setCaseStudyLoadingSlug(slug);
    setPage("analysis");
    await trackAnalysis(() => loadCaseStudy(slug, mode, engine));
    setCaseStudyLoadingSlug(null);
  }

  async function handleLoadDemo() {
    setDemoError(null);
    setDemoLoading(true);
    try {
      const [beforeRes, afterRes] = await Promise.all([
        fetch("/demo/wayanad_before.tif"),
        fetch("/demo/wayanad_after.tif"),
      ]);
      if (!beforeRes.ok || !afterRes.ok) {
        throw new Error("Demo imagery not found on this machine.");
      }
      const [beforeBlob, afterBlob] = await Promise.all([beforeRes.blob(), afterRes.blob()]);
      const before = new File([beforeBlob], "wayanad_before.tif", { type: "image/tiff" });
      const after = new File([afterBlob], "wayanad_after.tif", { type: "image/tiff" });
      setBeforeFile(before);
      setAfterFile(after);
      setDemoLoading(false);
      await runAnalysis(before, after);
    } catch (err) {
      setDemoLoading(false);
      setDemoError(
        `${(err as Error).message} Place wayanad_before.tif/wayanad_after.tif in frontend/public/demo/, or use "Upload your own GeoTIFFs".`,
      );
    }
  }

  function handleUploadOwnClick() {
    setOpenSections((s) => ({ ...s, analysis: true }));
    leftPanelRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handleNavigate(p: RailPage) {
    setPage(p);
    if (p === "analysis") {
      setOpenSections((s) => ({ ...s, analysis: true }));
      requestAnimationFrame(() =>
        analysisSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
      );
    }
  }

  function handleJumpToLayers() {
    setPage("analysis");
    setOpenSections((s) => ({ ...s, layers: true }));
    requestAnimationFrame(() =>
      layersSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );
  }

  const ready = state.phase === "ready" ? state : null;
  const bboxTooLarge = fetchBbox
    ? fetchBbox[2] - fetchBbox[0] > FETCH_MAX_BBOX_SIDE_DEG ||
      fetchBbox[3] - fetchBbox[1] > FETCH_MAX_BBOX_SIDE_DEG
    : false;

  useEffect(() => {
    const routeImpact = selected?.properties?.route_impact as string | undefined;
    const analysisId = ready?.analysis.id;
    const polygonId = selected?.properties?.id != null ? String(selected.properties.id) : null;
    if (!analysisId || !polygonId || !routeImpact || routeImpact === "null") {
      setRouteDisplay(null);
      return;
    }
    let cancelled = false;
    getPolygonRoute(analysisId, polygonId)
      .then((r) => {
        if (cancelled) return;
        setRouteDisplay({
          routeImpact: r.route_impact,
          originalPath: r.original_path,
          detourPath: r.detour_path,
        });
      })
      .catch(() => {
        if (!cancelled) setRouteDisplay(null);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, ready?.analysis.id]);

  const analysisName = ready
    ? beforeFile?.name.toLowerCase().includes("wayanad")
      ? "Wayanad · Jul 2024"
      : `Analysis ${ready.analysis.id.slice(0, 8)}`
    : null;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        width: "100vw",
        background: "var(--color-bg)",
      }}
    >
      <TopBar
        analysisName={analysisName}
        analysis={ready?.analysis ?? null}
        mode={mode}
        onModeChange={setMode}
        onOpenSettings={() => setPage("settings")}
      />

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <LeftRail page={page} onNavigate={handleNavigate} onJumpToLayers={handleJumpToLayers} />

        {page === "accuracy" ? (
          <AccuracyPage />
        ) : page === "settings" ? (
          <SettingsPage />
        ) : page === "case_studies" ? (
          <CaseStudiesPage onLoad={handleLoadCaseStudy} loadingSlug={caseStudyLoadingSlug} />
        ) : (
          <>
            <aside
              ref={leftPanelRef}
              className="ts-scroll"
              style={{
                width: "300px",
                flexShrink: 0,
                background: "var(--color-panel)",
                borderRight: "1px solid var(--color-border)",
                padding: "4px 16px",
                overflowY: "auto",
              }}
            >
              <CollapsibleSection
                ref={analysisSectionRef}
                title="New analysis"
                open={openSections.analysis}
                onToggle={() => toggleSection("analysis")}
              >
                <FileDropSlot label="Before image (GeoTIFF)" file={beforeFile} onChange={setBeforeFile} />
                <FileDropSlot label="After image (GeoTIFF)" file={afterFile} onChange={setAfterFile} />

                <button
                  className="ts-btn ts-btn-primary"
                  onClick={handleSubmit}
                  disabled={
                    !beforeFile || !afterFile || state.phase === "uploading" || state.phase === "processing"
                  }
                  style={{ width: "100%", marginTop: "4px" }}
                >
                  {state.phase === "uploading" || state.phase === "processing"
                    ? "Processing…"
                    : "Run analysis"}
                </button>

                {state.phase === "error" && (
                  <p
                    style={{
                      fontSize: "var(--font-size-xs)",
                      color: "var(--color-danger)",
                      marginTop: "10px",
                    }}
                  >
                    {state.message}
                  </p>
                )}

                {ready && (
                  <div style={{ marginTop: "12px" }}>
                    <p
                      style={{
                        fontSize: "var(--font-size-xs)",
                        color: "var(--color-text-secondary)",
                        margin: 0,
                      }}
                    >
                      {ready.analysis.summary_line}
                    </p>
                    <p
                      style={{
                        fontSize: "var(--font-size-xs)",
                        color: "var(--color-text-faint)",
                        marginTop: "4px",
                      }}
                    >
                      Pixel size ~<span className="mono">{ready.analysis.pixel_size_m?.toFixed(1)}</span> m
                      {ready.analysis.engine_fell_back && <> — fell back to spectral baseline</>}
                    </p>
                    {ready.analysis.fetch_meta && (
                      <p
                        style={{
                          fontSize: "11px",
                          color: "var(--color-text-faint)",
                          marginTop: "4px",
                          lineHeight: 1.4,
                        }}
                      >
                        Auto-fetched: before {ready.analysis.fetch_meta.before_scene.date.slice(0, 10)} (
                        {ready.analysis.fetch_meta.before_scene.cloud_cover.toFixed(1)}% cloud) → after{" "}
                        {ready.analysis.fetch_meta.after_scene.date.slice(0, 10)} (
                        {ready.analysis.fetch_meta.after_scene.cloud_cover.toFixed(1)}% cloud)
                      </p>
                    )}
                  </div>
                )}

                <div
                  style={{
                    marginTop: "16px",
                    paddingTop: "14px",
                    borderTop: "1px solid var(--color-border)",
                  }}
                >
                  <p
                    style={{
                      fontSize: "11px",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                      color: "var(--color-text-faint)",
                      margin: "0 0 8px",
                    }}
                  >
                    Or fetch imagery by place
                  </p>
                  <input
                    className="ts-input"
                    style={{ width: "100%", marginBottom: "6px" }}
                    placeholder="Place name, e.g. Wayanad, Kerala"
                    value={fetchPlace}
                    disabled={Boolean(fetchBbox)}
                    onChange={(e) => setFetchPlace(e.target.value)}
                  />
                  <button
                    className="ts-btn-ghost"
                    style={{
                      width: "100%",
                      fontSize: "11px",
                      padding: "4px 0",
                      marginBottom: "8px",
                      textAlign: "left",
                      color: "var(--color-accent)",
                    }}
                    onClick={() => setShowBboxDraw((s) => !s)}
                  >
                    {showBboxDraw ? "Hide map" : "Or draw a box on the map"}
                  </button>
                  {showBboxDraw && (
                    <div style={{ marginBottom: "8px" }}>
                      <BboxDrawMap
                        onBboxChange={(bbox) => {
                          setFetchBbox(bbox);
                          if (bbox) setFetchPlace("");
                        }}
                      />
                      {fetchBbox && (
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginTop: "6px",
                          }}
                        >
                          <span
                            className="mono"
                            style={{ fontSize: "10px", color: "var(--color-text-faint)" }}
                          >
                            {fetchBbox.map((v) => v.toFixed(3)).join(", ")}
                          </span>
                          <button
                            className="ts-btn-ghost"
                            style={{ fontSize: "11px", padding: "2px 6px" }}
                            onClick={() => setFetchBbox(null)}
                          >
                            Clear
                          </button>
                        </div>
                      )}
                      {bboxTooLarge && (
                        <p
                          style={{
                            fontSize: "11px",
                            color: "var(--color-danger)",
                            marginTop: "4px",
                          }}
                        >
                          That box is too large (max {FETCH_MAX_BBOX_SIDE_DEG}° per side, ~
                          {Math.round(FETCH_MAX_BBOX_SIDE_DEG * 111)} km) — draw a smaller area.
                        </p>
                      )}
                    </div>
                  )}
                  <div style={{ display: "flex", gap: "6px", marginBottom: "6px" }}>
                    <input
                      className="ts-input"
                      style={{ flex: 1, fontSize: "11px" }}
                      placeholder="before YYYY-MM-DD/YYYY-MM-DD"
                      value={fetchBeforeRange}
                      onChange={(e) => setFetchBeforeRange(e.target.value)}
                    />
                    <input
                      className="ts-input"
                      style={{ flex: 1, fontSize: "11px" }}
                      placeholder="after YYYY-MM-DD/YYYY-MM-DD"
                      value={fetchAfterRange}
                      onChange={(e) => setFetchAfterRange(e.target.value)}
                    />
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                    <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
                      Max cloud %
                    </span>
                    <input
                      type="number"
                      className="ts-input"
                      style={{ width: "64px" }}
                      value={fetchMaxCloud}
                      min={0}
                      max={100}
                      onChange={(e) => setFetchMaxCloud(Number(e.target.value))}
                    />
                  </div>
                  <button
                    className="ts-btn"
                    style={{ width: "100%" }}
                    disabled={
                      (!fetchBbox && !fetchPlace.trim()) ||
                      bboxTooLarge ||
                      fetchLoading ||
                      state.phase === "uploading" ||
                      state.phase === "processing"
                    }
                    onClick={handleFetchSubmit}
                  >
                    {fetchLoading ? "Fetching…" : "Fetch & analyze"}
                  </button>
                </div>
              </CollapsibleSection>

              <CollapsibleSection
                title="Engine"
                open={openSections.engine}
                onToggle={() => toggleSection("engine")}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: "8px",
                    color: "var(--color-text-secondary)",
                  }}
                >
                  <Cpu size={13} />
                  <span style={{ fontSize: "var(--font-size-xs)" }}>Detection engine</span>
                </div>
                <select
                  className="ts-select"
                  value={engine}
                  onChange={(e) => setEngine(e.target.value as EngineChoice)}
                >
                  {ENGINE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </CollapsibleSection>

              {ready && (
                <CollapsibleSection
                  ref={layersSectionRef}
                  title="Map layers"
                  open={openSections.layers}
                  onToggle={() => toggleSection("layers")}
                >
                  <LayerRow
                    label="Rejected changes"
                    count={ready.analysis.rejected_count}
                    checked={showRejected}
                    onChange={setShowRejected}
                  />
                  <LayerRow
                    label="Population"
                    checked={showPopulation}
                    onChange={setShowPopulation}
                    disabled={!ready.analysis.population_available}
                    note={!ready.analysis.population_available ? "no data" : undefined}
                    color="var(--color-severity-medium)"
                  />
                  <LayerRow
                    label="Facilities"
                    checked={showFacilities}
                    onChange={setShowFacilities}
                    color="var(--color-severity-high)"
                  />
                  <LayerRow
                    label="Roads"
                    checked={showRoads}
                    onChange={setShowRoads}
                    color="var(--color-text-secondary)"
                  />

                  {mode === "prevention" && (
                    <div style={{ marginTop: "14px" }}>
                      <button
                        className={drawMode ? "ts-btn ts-btn-primary" : "ts-btn"}
                        onClick={() => setDrawMode((d) => !d)}
                        style={{ width: "100%" }}
                      >
                        {drawMode ? "Cancel drawing" : hazardZone ? "Redraw hazard zone" : "Draw hazard zone"}
                      </button>
                      {hazardZoneStatus && (
                        <p
                          style={{
                            fontSize: "var(--font-size-xs)",
                            color: "var(--color-text-secondary)",
                            marginTop: "8px",
                            lineHeight: 1.4,
                          }}
                        >
                          {hazardZoneStatus}
                        </p>
                      )}
                    </div>
                  )}
                </CollapsibleSection>
              )}

              {ready?.analysis.quality_report && (
                <CollapsibleSection
                  title="Quality report"
                  open={openSections.quality}
                  onToggle={() => toggleSection("quality")}
                >
                  {ready.analysis.quality_report.warnings.length > 0 && (
                    <div
                      style={{
                        display: "flex",
                        gap: "8px",
                        padding: "8px 10px",
                        marginBottom: "10px",
                        background: "var(--color-warning-soft)",
                        border: "1px solid rgba(245,165,36,0.3)",
                        borderRadius: "var(--radius-sm)",
                        fontSize: "var(--font-size-xs)",
                        color: "var(--color-warning)",
                        lineHeight: 1.4,
                      }}
                    >
                      <AlertTriangle size={13} style={{ flexShrink: 0, marginTop: "1px" }} />
                      <div>
                        {ready.analysis.quality_report.warnings.map((w, i) => (
                          <div key={i}>{w}</div>
                        ))}
                      </div>
                    </div>
                  )}
                  <QualityRow
                    label="Cloud (before)"
                    value={`${ready.analysis.quality_report.before_cloud_pct.toFixed(1)}%`}
                    warn={ready.analysis.quality_report.before_cloud_pct > 20}
                  />
                  <QualityRow
                    label="Cloud (after)"
                    value={`${ready.analysis.quality_report.after_cloud_pct.toFixed(1)}%`}
                    warn={ready.analysis.quality_report.after_cloud_pct > 20}
                  />
                  <QualityRow label="Cloud method" value={ready.analysis.quality_report.cloud_method} />
                  <QualityRow
                    label="Misalignment"
                    value={`${ready.analysis.quality_report.misalignment_px.toFixed(1)} px`}
                    warn={ready.analysis.quality_report.misalignment_px > 1}
                  />
                  <QualityRow
                    label="Resolution"
                    value={`${ready.analysis.quality_report.resolution_m.toFixed(1)} m`}
                  />
                  <QualityRow label="Bands" value={String(ready.analysis.quality_report.band_count)} />
                </CollapsibleSection>
              )}
            </aside>

            <main
              style={{
                flex: 1,
                position: "relative",
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
              }}
            >
              {state.phase === "empty" && (
                <Hero
                  onLoadDemo={handleLoadDemo}
                  onUploadOwn={handleUploadOwnClick}
                  demoLoading={demoLoading}
                  demoError={demoError}
                />
              )}
              {(state.phase === "uploading" || state.phase === "processing") && (
                <ProcessingCard
                  step={state.phase === "processing" ? state.step : "validating"}
                  steps={state.phase === "processing" ? state.steps : []}
                />
              )}
              {state.phase === "error" && (
                <div
                  style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}
                >
                  <div
                    className="ts-card"
                    style={{ padding: "24px", maxWidth: "400px", textAlign: "center" }}
                  >
                    <AlertTriangle size={20} color="var(--color-danger)" style={{ marginBottom: "8px" }} />
                    <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text)" }}>
                      {state.message}
                    </p>
                  </div>
                </div>
              )}

              {ready && (
                <>
                  <KpiStrip analysis={ready.analysis} geojson={ready.geojson} />
                  <div style={{ flex: 1, display: "flex", minHeight: 0, padding: "0 16px 16px" }}>
                    <div
                      style={{
                        flex: 1,
                        position: "relative",
                        minWidth: 0,
                        borderRadius: "var(--radius-md)",
                        overflow: "hidden",
                        border: "1px solid var(--color-border)",
                      }}
                    >
                      {ready.analysis.bounds && (
                        <CompareMap
                          beforeUrl={imageryUrl(ready.analysis.id, "before")}
                          afterUrl={imageryUrl(ready.analysis.id, "after")}
                          bounds={ready.analysis.bounds}
                          geojson={ready.geojson}
                          selectedId={selected ? String(selected.properties?.id) : null}
                          zoomToId={zoomToId}
                          hoveredId={hoveredId}
                          onPolygonClick={(f) => {
                            setSelected(f);
                            setRightPanelOpen(true);
                            setRightPanelTab("details");
                          }}
                          onPolygonHover={setHoveredId}
                          showRejected={showRejected}
                          facilities={facilities}
                          showFacilities={showFacilities}
                          showRoads={showRoads}
                          populationUrl={
                            ready.analysis.population_available
                              ? populationOverlayUrl(ready.analysis.id)
                              : null
                          }
                          showPopulation={showPopulation}
                          drawMode={drawMode}
                          onDrawComplete={handleDrawComplete}
                          hazardZone={hazardZone}
                          route={routeDisplay}
                        />
                      )}
                    </div>

                    <div style={{ display: "flex", flexShrink: 0 }}>
                      <button
                        onClick={() => setRightPanelOpen((o) => !o)}
                        className="ts-btn-ghost"
                        style={{
                          width: "28px",
                          border: "none",
                          background: "transparent",
                          cursor: "pointer",
                          fontSize: "var(--font-size-xs)",
                          color: "var(--color-text-secondary)",
                          writingMode: "vertical-rl",
                          textOrientation: "mixed",
                          padding: "12px 0",
                          whiteSpace: "nowrap",
                          marginLeft: "8px",
                        }}
                        title={rightPanelOpen ? "Collapse panel" : "Expand panel"}
                      >
                        {rightPanelOpen ? "Close" : `Priority (${ready.analysis.kept_count})`}
                      </button>

                      {rightPanelOpen && (
                        <div
                          className="ts-card ts-slide-in-right"
                          style={{
                            width: "340px",
                            marginLeft: "8px",
                            display: "flex",
                            flexDirection: "column",
                            overflow: "hidden",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              borderBottom: "1px solid var(--color-border)",
                              flexShrink: 0,
                            }}
                          >
                            <TabButton
                              active={rightPanelTab === "priority"}
                              onClick={() => setRightPanelTab("priority")}
                            >
                              Priority queue
                            </TabButton>
                            <TabButton
                              active={rightPanelTab === "details"}
                              onClick={() => setRightPanelTab("details")}
                            >
                              Change details
                            </TabButton>
                          </div>
                          <div className="ts-scroll" style={{ flex: 1, overflowY: "auto" }}>
                            {rightPanelTab === "details" ? (
                              selected ? (
                                <PolygonPanel
                                  feature={selected}
                                  onClose={() => {
                                    setSelected(null);
                                    setZoomToId(null);
                                    setRightPanelTab("priority");
                                  }}
                                />
                              ) : (
                                <div
                                  style={{
                                    padding: "32px 16px",
                                    textAlign: "center",
                                    color: "var(--color-text-faint)",
                                    fontSize: "var(--font-size-xs)",
                                  }}
                                >
                                  Select a change on the map or priority list.
                                </div>
                              )
                            ) : (
                              <PriorityPanel
                                geojson={ready.geojson}
                                onSelect={handleSelectFromPriority}
                                hoveredId={hoveredId}
                                onHoverRow={setHoveredId}
                                selectedId={selected ? String(selected.properties?.id) : null}
                              />
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </main>
          </>
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1,
        border: "none",
        borderBottom: active ? "2px solid var(--color-accent)" : "2px solid transparent",
        background: "transparent",
        color: active ? "var(--color-text)" : "var(--color-text-secondary)",
        fontWeight: active ? 600 : 500,
        fontSize: "var(--font-size-xs)",
        padding: "11px 0",
        cursor: "pointer",
        transition: "color var(--transition-fast), border-color var(--transition-fast)",
      }}
    >
      {children}
    </button>
  );
}

const LAYER_ICONS: Record<string, React.ComponentType<{ size?: number; color?: string }>> = {
  "Rejected changes": X,
  Population: Landmark,
  Facilities: Hospital,
  Roads: Route,
};

function LayerRow({
  label,
  count,
  checked,
  onChange,
  disabled,
  note,
  color,
}: {
  label: string;
  count?: number;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  note?: string;
  color?: string;
}) {
  const Icon = LAYER_ICONS[label] ?? MapPin;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "7px 0",
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <Icon size={13} color={color ?? "var(--color-text-secondary)"} />
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text)" }}>
          {label}
          {count != null && <span style={{ color: "var(--color-text-faint)" }}> ({count})</span>}
          {note && <span style={{ color: "var(--color-text-faint)" }}> · {note}</span>}
        </span>
      </div>
      <Switch checked={checked} onChange={onChange} disabled={disabled} />
    </div>
  );
}

function QualityRow({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 0" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        <span className={`ts-status-dot ${warn ? "warn" : "ok"}`} />
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>{label}</span>
      </div>
      <span className="mono" style={{ fontSize: "var(--font-size-xs)" }}>
        {value}
      </span>
    </div>
  );
}
