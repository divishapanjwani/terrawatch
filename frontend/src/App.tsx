import { useState } from "react";
import type { MapGeoJSONFeature } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import "./styles/tokens.css";
import "./App.css";
import CompareMap from "./map/CompareMap";
import FileDropSlot from "./panels/FileDropSlot";
import PolygonPanel from "./panels/PolygonPanel";
import AccuracyPage from "./pages/AccuracyPage";
import {
  createAnalysis,
  exportUrl,
  getPolygons,
  imageryUrl,
  pollUntilReady,
} from "./api/client";
import type { AnalysisStatus, EngineChoice } from "./api/client";

type AppState =
  | { phase: "empty" }
  | { phase: "uploading" }
  | { phase: "processing"; id: string; step: string; steps: string[] }
  | { phase: "ready"; analysis: AnalysisStatus; geojson: FeatureCollection }
  | { phase: "error"; message: string };

const STEP_LABELS: Record<string, string> = {
  validating: "Validating",
  quality_check: "Quality check",
  detecting: "Detecting",
  filtering: "Filtering",
  vectorizing: "Vectorizing",
  done: "Done",
};

const ENGINE_OPTIONS: { value: EngineChoice; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "tinycd", label: "TinyCD" },
  { value: "engine2", label: "Engine 2" },
  { value: "spectral", label: "Spectral baseline" },
];

const ENGINE_NAME_LABEL: Record<string, string> = {
  siamese_levir_cd: "TinyCD",
  unet_oscd: "Engine 2 (U-Net)",
  spectral_baseline: "spectral baseline",
};

export default function App() {
  const [page, setPage] = useState<"analysis" | "accuracy">("analysis");
  const [state, setState] = useState<AppState>({ phase: "empty" });
  const [beforeFile, setBeforeFile] = useState<File | null>(null);
  const [afterFile, setAfterFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"disaster" | "prevention">("disaster");
  const [engine, setEngine] = useState<EngineChoice>("auto");
  const [selected, setSelected] = useState<MapGeoJSONFeature | null>(null);
  const [showRejected, setShowRejected] = useState(false);

  async function handleSubmit() {
    if (!beforeFile || !afterFile) return;
    setSelected(null);
    setState({ phase: "uploading" });
    try {
      const { analysis_id } = await createAnalysis(beforeFile, afterFile, mode, engine);
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
      }
    } catch (err) {
      setState({ phase: "error", message: (err as Error).message });
    }
  }

  const ready = state.phase === "ready" ? state : null;

  return (
    <div style={{ display: "flex", height: "100vh", width: "100vw" }}>
      <nav
        style={{
          width: "56px",
          background: "var(--color-panel)",
          borderRight: "1px solid var(--color-border)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          paddingTop: "12px",
          gap: "16px",
        }}
      >
        <div
          style={{
            width: "28px",
            height: "28px",
            borderRadius: "var(--radius-sm)",
            background: "var(--color-accent)",
          }}
          title="TerraWatch"
        />
        <button
          onClick={() => setPage("analysis")}
          title="New Analysis"
          style={{
            width: "32px",
            height: "32px",
            border: "none",
            borderRadius: "var(--radius-sm)",
            background: page === "analysis" ? "var(--color-accent)" : "transparent",
            color: page === "analysis" ? "white" : "var(--color-text-secondary)",
            cursor: "pointer",
            fontSize: "var(--font-size-xs)",
          }}
        >
          Map
        </button>
        <button
          onClick={() => setPage("accuracy")}
          title="Accuracy"
          style={{
            width: "32px",
            height: "32px",
            border: "none",
            borderRadius: "var(--radius-sm)",
            background: page === "accuracy" ? "var(--color-accent)" : "transparent",
            color: page === "accuracy" ? "white" : "var(--color-text-secondary)",
            cursor: "pointer",
            fontSize: "var(--font-size-xs)",
          }}
        >
          Acc.
        </button>
      </nav>

      {page === "accuracy" ? (
        <AccuracyPage />
      ) : (
        <>
      <aside
        style={{
          width: "320px",
          background: "var(--color-panel)",
          borderRight: "1px solid var(--color-border)",
          padding: "16px",
          overflowY: "auto",
        }}
      >
        <h1 style={{ fontSize: "var(--font-size-lg)", margin: "0 0 4px" }}>TerraWatch</h1>
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", margin: "0 0 20px" }}>
          Satellite change intelligence
        </p>

        <section style={{ marginBottom: "20px" }}>
          <h2 style={{ fontSize: "var(--font-size-sm)", margin: "0 0 8px", color: "var(--color-text-secondary)" }}>
            New analysis
          </h2>

          <FileDropSlot label="Before image (GeoTIFF)" file={beforeFile} onChange={setBeforeFile} />
          <FileDropSlot label="After image (GeoTIFF)" file={afterFile} onChange={setAfterFile} />

          <label style={{ display: "block", fontSize: "var(--font-size-xs)", marginBottom: "4px" }}>
            Mode
          </label>
          <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
            {(["disaster", "prevention"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                style={{
                  flex: 1,
                  padding: "6px 8px",
                  fontSize: "var(--font-size-xs)",
                  borderRadius: "var(--radius-sm)",
                  border: `1px solid ${mode === m ? "var(--color-accent)" : "var(--color-border)"}`,
                  background: mode === m ? "var(--color-accent)" : "white",
                  color: mode === m ? "white" : "var(--color-text)",
                  cursor: "pointer",
                  textTransform: "capitalize",
                }}
              >
                {m}
              </button>
            ))}
          </div>

          <label style={{ display: "block", fontSize: "var(--font-size-xs)", marginBottom: "4px" }}>
            Engine
          </label>
          <select
            value={engine}
            onChange={(e) => setEngine(e.target.value as EngineChoice)}
            style={{
              width: "100%",
              padding: "6px 8px",
              fontSize: "var(--font-size-xs)",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--color-border)",
              background: "white",
              color: "var(--color-text)",
              marginBottom: "16px",
            }}
          >
            {ENGINE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>

          <button
            onClick={handleSubmit}
            disabled={!beforeFile || !afterFile || state.phase === "uploading" || state.phase === "processing"}
            style={{
              width: "100%",
              padding: "8px",
              fontSize: "var(--font-size-sm)",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "var(--color-accent)",
              color: "white",
              cursor: "pointer",
              opacity: !beforeFile || !afterFile ? 0.5 : 1,
            }}
          >
            {state.phase === "uploading" || state.phase === "processing" ? "Processing…" : "Run analysis"}
          </button>
        </section>

        {state.phase === "processing" && (
          <section style={{ marginBottom: "20px" }}>
            {(state.steps.length ? state.steps : ["validating", "detecting", "filtering", "vectorizing", "done"]).map(
              (step) => {
                const isDone =
                  (state.steps.length ? state.steps : []).indexOf(step) <
                  (state.steps.length ? state.steps : []).indexOf(state.step);
                const isCurrent = step === state.step;
                return (
                  <div
                    key={step}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      fontSize: "var(--font-size-xs)",
                      padding: "3px 0",
                      color: isCurrent ? "var(--color-text)" : "var(--color-text-secondary)",
                      fontWeight: isCurrent ? 600 : 400,
                    }}
                  >
                    <span
                      style={{
                        width: "8px",
                        height: "8px",
                        borderRadius: "50%",
                        background: isDone || isCurrent ? "var(--color-accent)" : "var(--color-border)",
                        display: "inline-block",
                      }}
                    />
                    {STEP_LABELS[step] ?? step}
                  </div>
                );
              }
            )}
          </section>
        )}

        {state.phase === "error" && (
          <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-danger)" }}>{state.message}</p>
        )}

        {ready && ready.analysis.quality_report && ready.analysis.quality_report.warnings.length > 0 && (
          <section
            style={{
              marginBottom: "16px",
              padding: "8px 10px",
              background: "rgba(184,134,11,0.08)",
              border: "1px solid var(--color-warning)",
              borderRadius: "var(--radius-sm)",
              fontSize: "var(--font-size-xs)",
              color: "var(--color-warning)",
              lineHeight: 1.5,
            }}
          >
            {ready.analysis.quality_report.warnings.map((w, i) => (
              <div key={i}>{w}</div>
            ))}
          </section>
        )}

        {ready && (
          <section>
            <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
              Analysis <span className="mono">{ready.analysis.id}</span> ready (
              {ENGINE_NAME_LABEL[ready.analysis.engine ?? ""] ?? ready.analysis.engine}).
            </p>
            {ready.analysis.summary_line && (
              <p style={{ fontSize: "var(--font-size-xs)", marginTop: "4px" }}>{ready.analysis.summary_line}</p>
            )}
            <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", marginTop: "4px" }}>
              Pixel size ~<span className="mono">{ready.analysis.pixel_size_m?.toFixed(1)}</span> m
              {ready.analysis.engine_fell_back && ready.analysis.engine_choice === "auto" && (
                <> — requested engine unavailable, fell back automatically</>
              )}
              {ready.analysis.engine_fell_back && ready.analysis.engine_choice !== "auto" && (
                <> — "{ready.analysis.engine_choice}" unavailable, fell back to spectral baseline</>
              )}
            </p>

            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                marginTop: "12px",
                fontSize: "var(--font-size-xs)",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={showRejected}
                onChange={(e) => setShowRejected(e.target.checked)}
              />
              Show rejected changes ({ready.analysis.rejected_count})
            </label>

            <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
              <a
                href={exportUrl(ready.analysis.id, "geojson")}
                style={{
                  flex: 1,
                  textAlign: "center",
                  padding: "6px 8px",
                  fontSize: "var(--font-size-xs)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                  color: "var(--color-text)",
                  textDecoration: "none",
                }}
              >
                Export GeoJSON
              </a>
              <a
                href={exportUrl(ready.analysis.id, "gpkg")}
                style={{
                  flex: 1,
                  textAlign: "center",
                  padding: "6px 8px",
                  fontSize: "var(--font-size-xs)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                  color: "var(--color-text)",
                  textDecoration: "none",
                }}
              >
                Export GPKG
              </a>
            </div>
          </section>
        )}

        {ready && ready.analysis.quality_report && (
          <section style={{ marginTop: "16px" }}>
            <h2 style={{ fontSize: "var(--font-size-sm)", margin: "0 0 8px", color: "var(--color-text-secondary)" }}>
              Quality report
            </h2>
            <QualityRow label="Cloud (before)" value={`${ready.analysis.quality_report.before_cloud_pct.toFixed(1)}%`} />
            <QualityRow label="Cloud (after)" value={`${ready.analysis.quality_report.after_cloud_pct.toFixed(1)}%`} />
            <QualityRow label="Cloud method" value={ready.analysis.quality_report.cloud_method} />
            <QualityRow label="Misalignment" value={`${ready.analysis.quality_report.misalignment_px.toFixed(1)} px`} />
            <QualityRow label="Resolution" value={`${ready.analysis.quality_report.resolution_m.toFixed(1)} m`} />
            <QualityRow label="Bands" value={String(ready.analysis.quality_report.band_count)} />
          </section>
        )}
      </aside>

      <main style={{ flex: 1, position: "relative", background: "var(--color-bg)" }}>
        {ready && ready.analysis.bounds ? (
          <CompareMap
            beforeUrl={imageryUrl(ready.analysis.id, "before")}
            afterUrl={imageryUrl(ready.analysis.id, "after")}
            bounds={ready.analysis.bounds}
            geojson={ready.geojson}
            selectedId={selected ? String(selected.properties?.id) : null}
            onPolygonClick={setSelected}
            showRejected={showRejected}
          />
        ) : (
          <div
            style={{
              height: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexDirection: "column",
              color: "var(--color-text-secondary)",
              fontSize: "var(--font-size-sm)",
            }}
          >
            <p>Upload a before/after GeoTIFF pair to begin.</p>
          </div>
        )}
        {ready && <PolygonPanel feature={selected} onClose={() => setSelected(null)} />}
      </main>
        </>
      )}
    </div>
  );
}

function QualityRow({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        padding: "3px 0",
        fontSize: "var(--font-size-xs)",
      }}
    >
      <span style={{ color: "var(--color-text-secondary)" }}>{label}</span>
      <span className="mono">{value}</span>
    </div>
  );
}
