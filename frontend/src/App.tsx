import { useState } from "react";
import type { MapGeoJSONFeature } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import "./styles/tokens.css";
import "./App.css";
import CompareMap from "./map/CompareMap";
import FileDropSlot from "./panels/FileDropSlot";
import PolygonPanel from "./panels/PolygonPanel";
import {
  createAnalysis,
  exportUrl,
  getPolygons,
  imageryUrl,
  pollUntilReady,
} from "./api/client";
import type { AnalysisStatus } from "./api/client";

type AppState =
  | { phase: "empty" }
  | { phase: "uploading" }
  | { phase: "processing"; id: string; step: string; steps: string[] }
  | { phase: "ready"; analysis: AnalysisStatus; geojson: FeatureCollection }
  | { phase: "error"; message: string };

const STEP_LABELS: Record<string, string> = {
  validating: "Validating",
  detecting: "Detecting",
  filtering: "Filtering",
  vectorizing: "Vectorizing",
  done: "Done",
};

export default function App() {
  const [state, setState] = useState<AppState>({ phase: "empty" });
  const [beforeFile, setBeforeFile] = useState<File | null>(null);
  const [afterFile, setAfterFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"disaster" | "prevention">("disaster");
  const [selected, setSelected] = useState<MapGeoJSONFeature | null>(null);

  async function handleSubmit() {
    if (!beforeFile || !afterFile) return;
    setSelected(null);
    setState({ phase: "uploading" });
    try {
      const { analysis_id } = await createAnalysis(beforeFile, afterFile, mode);
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
      </nav>

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

        {ready && (
          <section>
            <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
              Analysis <span className="mono">{ready.analysis.id}</span> ready — {ready.analysis.polygon_count}{" "}
              change{ready.analysis.polygon_count === 1 ? "" : "s"} found ({ready.analysis.engine}).
            </p>
            <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
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
    </div>
  );
}
